from pathlib import Path
import subprocess
import tempfile

from django.conf import settings


class SimpleInvoicePdfConversionError(Exception):
    pass


def convert_xlsx_to_pdf(*, xlsx_path: Path, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as lo_profile_dir:
        command = [
            settings.LIBREOFFICE_PATH,
            "--headless",
            "--nologo",
            "--nofirststartwizard",
            "--norestore",
            f"-env:UserInstallation=file:///{lo_profile_dir.replace('\\', '/')}",
            "--convert-to",
            "pdf",
            "--outdir",
            str(output_dir),
            str(xlsx_path),
        ]

        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=180,
            )
        except subprocess.TimeoutExpired as exc:
            raise SimpleInvoicePdfConversionError(
                "LibreOffice PDF conversion timed out."
            ) from exc

    if result.returncode != 0:
        raise SimpleInvoicePdfConversionError(
            f"Failed to convert XLSX to PDF: {result.stderr or result.stdout}"
        )

    pdf_path = output_dir / f"{xlsx_path.stem}.pdf"

    if not pdf_path.exists():
        raise SimpleInvoicePdfConversionError(
            f"PDF file was not created: {pdf_path}"
        )

    return pdf_path