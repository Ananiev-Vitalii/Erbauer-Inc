import os
import time

import cloudinary.uploader
import cloudinary.utils

from cloudinary_storage.storage import RawMediaCloudinaryStorage
from django.utils.deconstruct import deconstructible


@deconstructible
class PrivateInvoiceCloudinaryStorage(RawMediaCloudinaryStorage):
    DELIVERY_TYPE = "private"
    DOWNLOAD_URL_TTL_SECONDS = 300

    def _upload(self, name, content):
        return cloudinary.uploader.upload(
            content,
            public_id=name,
            resource_type="raw",
            type=self.DELIVERY_TYPE,
            overwrite=True,
            invalidate=True,
            tags=self.TAG,
            filename_override=os.path.basename(name),
        )

    def delete(self, name):
        response = cloudinary.uploader.destroy(
            name,
            resource_type="raw",
            type=self.DELIVERY_TYPE,
            invalidate=True,
        )

        return response.get("result") == "ok"

    def url(self, name):
        expires_at = int(time.time()) + self.DOWNLOAD_URL_TTL_SECONDS

        return cloudinary.utils.private_download_url(
            name,
            "pdf",
            resource_type="raw",
            type=self.DELIVERY_TYPE,
            expires_at=expires_at,
            attachment=True,
        )
