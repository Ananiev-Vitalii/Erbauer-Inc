import logging
import re
from types import TracebackType


class EmailErrorFormatter(logging.Formatter):
    """Keep traceback locations without provider messages, payloads, or locals."""

    def formatException(
        self,
        ei: tuple[type[BaseException], BaseException, TracebackType | None],
    ) -> str:
        exception_type, _, traceback = ei
        lines = ["Traceback (exception details redacted):"]
        while traceback is not None:
            code = traceback.tb_frame.f_code
            lines.append(
                f'  File "{code.co_filename}", line {traceback.tb_lineno}, '
                f"in {code.co_name}"
            )
            traceback = traceback.tb_next
        lines.append(exception_type.__name__)
        return "\n".join(lines)


class AccountTaskFailureFilter(logging.Filter):
    """Redact account task failures before Celery formats their log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        data = getattr(record, "data", None)
        if record.levelno < logging.ERROR or not isinstance(data, dict):
            return True
        task_name = data.get("name")
        if not isinstance(task_name, str) or not task_name.startswith("account."):
            return True

        error_type = "TaskError"
        safe_traceback = None
        cause_type = None
        exit_code = None
        if record.exc_info and record.exc_info[0] is not None:
            error_type = record.exc_info[0].__name__
            safe_traceback = EmailErrorFormatter().formatException(record.exc_info)
            error = record.exc_info[1]
            if error is not None:
                cause = error.__cause__ or error.__context__
                if cause is not None:
                    cause_type = type(cause).__name__
                returncode = error.__dict__.get("returncode")
                if isinstance(returncode, int):
                    exit_code = returncode

        invoice_id = None
        task_args = data.get("args")
        if (
            task_name == "account.tasks.process_simple_invoice_task"
            and isinstance(task_args, str)
        ):
            match = re.match(
                r"^\s*[\[(]\s*([0-9]{1,19})(?:\s*,|\s*\)|\s*\])", task_args
            )
            if match is not None:
                invoice_id = match.group(1)

        task_id = data.get("id")
        record.msg = "Task %s[%s] failed. Invoice id: %s. Error type: %s"
        record.args = (task_name, task_id, invoice_id or "n/a", error_type)
        if cause_type is not None:
            record.msg += ". Cause type: %s"
            record.args += (cause_type,)
        if exit_code is not None:
            record.msg += ". Exit code: %s"
            record.args += (exit_code,)
        record.data = {
            "name": task_name,
            "id": task_id,
            "invoice_id": invoice_id,
            "error_type": error_type,
            "cause_type": cause_type,
            "exit_code": exit_code,
        }
        # Do not leave raw exceptions, cached tracebacks, or arguments for handlers.
        record.exc_info = None
        record.exc_text = safe_traceback
        record.stack_info = None
        return True


class AccountCleanupFailureFilter(logging.Filter):
    """Redact django-cleanup errors only for account model file operations."""

    def filter(self, record: logging.LogRecord) -> bool:
        args = record.args
        if (
            record.levelno < logging.ERROR
            or not isinstance(args, tuple)
            or len(args) != 4
            or args[1] != "account"
        ):
            return True

        error_type = "StorageError"
        safe_traceback = None
        if record.exc_info and record.exc_info[0] is not None:
            error_type = record.exc_info[0].__name__
            safe_traceback = EmailErrorFormatter().formatException(record.exc_info)
        record.msg = "File cleanup failed. Model: account.%s. Field: %s. Error type: %s"
        record.args = (args[2], args[3], error_type)
        record.exc_info = None
        record.exc_text = safe_traceback
        record.stack_info = None
        return True
