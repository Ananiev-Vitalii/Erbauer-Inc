import os
import subprocess
import tempfile
from pathlib import Path

from django.conf import settings


class SimpleInvoicePdfConversionError(Exception):
    """Expose conversion failures without command output or private paths."""

    def __init__(self, message: str, *, returncode: int | None = None) -> None:
        super().__init__(message)
        self.returncode = returncode


def _get_libreoffice_path() -> str:
    return (
        os.getenv("LIBREOFFICE_PATH")
        or getattr(settings, "LIBREOFFICE_PATH", None)
        or "soffice"
    )


def _to_file_url(path: str) -> str:
    normalized_path = path.replace("\\", "/")

    if os.name == "nt":
        return f"file:///{normalized_path}"

    return f"file://{normalized_path}"


def convert_xlsx_to_pdf(*, xlsx_path: Path, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as lo_profile_dir:
        command = [
            _get_libreoffice_path(),
            "--headless",
            "--nologo",
            "--nofirststartwizard",
            "--norestore",
            "--nodefault",
            f"-env:UserInstallation={_to_file_url(lo_profile_dir)}",
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
                f"LibreOffice PDF conversion timed out ({type(exc).__name__})."
            ) from None
        except FileNotFoundError as exc:
            raise SimpleInvoicePdfConversionError(
                f"LibreOffice executable was not found ({type(exc).__name__})."
            ) from None

    if result.returncode != 0:
        raise SimpleInvoicePdfConversionError(
            f"LibreOffice PDF conversion failed. Exit code: {result.returncode}.",
            returncode=result.returncode,
        )

    pdf_path = output_dir / f"{xlsx_path.stem}.pdf"

    if not pdf_path.exists():
        raise SimpleInvoicePdfConversionError(
            "LibreOffice PDF conversion completed without an output PDF. "
            f"Exit code: {result.returncode}.",
            returncode=result.returncode,
        )

    return pdf_path
