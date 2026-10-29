"""Application logging that writes to stdout and one date-named file per day."""

import logging
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def _resolve_timezone(name: str):
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError:
        return datetime.now().astimezone().tzinfo


class TimezoneFormatter(logging.Formatter):
    def __init__(self, *args, timezone_name: str, **kwargs):
        super().__init__(*args, **kwargs)
        self.timezone = _resolve_timezone(timezone_name)

    def formatTime(self, record: logging.LogRecord, datefmt: str | None = None) -> str:
        value = datetime.fromtimestamp(record.created, self.timezone)
        return value.strftime(datefmt) if datefmt else value.isoformat(timespec="milliseconds")


class DailyDateFileHandler(logging.Handler):
    """Append each record to ``helpflow_YYYY-MM-DD.log`` for its local date.

    The destination is selected for every record, so a process that remains
    running across midnight automatically starts writing to the next day's
    file without requiring a restart.
    """

    def __init__(self, log_dir: str | Path, timezone_name: str, prefix: str = "helpflow"):
        super().__init__()
        self.log_dir = Path(log_dir)
        self.timezone_name = timezone_name
        self.timezone = _resolve_timezone(timezone_name)
        self.prefix = prefix
        self._active_date: str | None = None
        self._stream = None
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def path_for_date(self, date: str) -> Path:
        return self.log_dir / f"{self.prefix}_{date}.log"

    def emit(self, record: logging.LogRecord) -> None:
        try:
            record_date = datetime.fromtimestamp(record.created, self.timezone).date().isoformat()
            if record_date != self._active_date:
                if self._stream:
                    self._stream.close()
                self._stream = self.path_for_date(record_date).open("a", encoding="utf-8")
                self._active_date = record_date
            self._stream.write(self.format(record) + "\n")
            self._stream.flush()
        except Exception:
            self.handleError(record)

    def close(self) -> None:
        if self._stream:
            self._stream.close()
            self._stream = None
        super().close()


def configure_app_logging(log_level: str, log_dir: str | Path, timezone_name: str) -> logging.Logger:
    """Configure and return the HelpFlow application logger."""

    level = getattr(logging, log_level.upper(), logging.INFO)
    formatter = TimezoneFormatter(
        "%(asctime)s %(levelname)s logger=%(name)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S%z",
        timezone_name=timezone_name,
    )
    logger = logging.getLogger("helpflow")
    logger.setLevel(level)
    logger.propagate = False

    # Avoid duplicate handlers if an ASGI test runner imports the app again.
    if not any(getattr(handler, "_helpflow_console", False) for handler in logger.handlers):
        console = logging.StreamHandler()
        console._helpflow_console = True  # type: ignore[attr-defined]
        console.setFormatter(formatter)
        logger.addHandler(console)

    resolved_log_dir = Path(log_dir).resolve()
    existing_file_handler = next(
        (handler for handler in logger.handlers if isinstance(handler, DailyDateFileHandler)),
        None,
    )
    if (
        existing_file_handler is None
        or existing_file_handler.log_dir.resolve() != resolved_log_dir
        or existing_file_handler.timezone_name != timezone_name
    ):
        if existing_file_handler is not None:
            logger.removeHandler(existing_file_handler)
            existing_file_handler.close()
        file_handler = DailyDateFileHandler(resolved_log_dir, timezone_name)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger
