from pathlib import Path
import os
import subprocess
import threading

from django.conf import settings


class SimpleInvoicePdfConversionError(Exception):
    pass


_conversion_lock = threading.Lock()


def _get_libreoffice_path() -> str:

    return (
        os.getenv("LIBREOFFICE_PATH")
        or getattr(settings, "LIBREOFFICE_PATH", None)
        or "soffice"
    )


def _get_libreoffice_profile_dir() -> Path:
    profile_dir = (
        os.getenv("LIBREOFFICE_PROFILE_DIR")
        or getattr(settings, "LIBREOFFICE_PROFILE_DIR", None)
    )

    if profile_dir:
        return Path(profile_dir)

    if os.name == "nt":
        return Path("C:/tmp/libreoffice-profile")

    return Path("/tmp/libreoffice-profile")


def _to_file_url(path: Path) -> str:
    normalized_path = str(path).replace("\\", "/")

    if os.name == "nt":
        return f"file:///{normalized_path}"

    return f"file://{normalized_path}"


def convert_xlsx_to_pdf(*, xlsx_path: Path, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)

    profile_dir = _get_libreoffice_profile_dir()
    profile_dir.mkdir(parents=True, exist_ok=True)

    command = [
        _get_libreoffice_path(),
        "--headless",
        "--nologo",
        "--nofirststartwizard",
        "--norestore",
        "--nodefault",
        f"-env:UserInstallation={_to_file_url(profile_dir)}",
        "--convert-to",
        "pdf",
        "--outdir",
        str(output_dir),
        str(xlsx_path),
    ]

    try:
        with _conversion_lock:
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
    except FileNotFoundError as exc:
        raise SimpleInvoicePdfConversionError(
            f"LibreOffice executable was not found: {_get_libreoffice_path()}"
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