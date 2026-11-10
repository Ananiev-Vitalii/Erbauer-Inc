import logging
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
