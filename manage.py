import os
import sys
from argparse import ArgumentParser
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent


def main() -> None:
    parser = ArgumentParser(add_help=False, allow_abbrev=False)
    parser.add_argument("--settings")
    options, remaining = parser.parse_known_args()
    settings_module = options.settings or os.environ.get("DJANGO_SETTINGS_MODULE")
    is_test_command = bool(remaining) and remaining[0] == "test"

    if is_test_command and settings_module != "config.settings.test":
        raise SystemExit(
            "Backend tests require --settings=config.settings.test "
            "or DJANGO_SETTINGS_MODULE=config.settings.test."
        )

    if settings_module == "config.settings.test":
        os.environ["DJANGO_SETTINGS_MODULE"] = settings_module
    else:
        load_dotenv(BASE_DIR / ".env")

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.base")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
