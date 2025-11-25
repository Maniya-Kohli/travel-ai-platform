# platform_common/logging_config.py
import logging

def init_logging(service_name: str, level: int = logging.INFO):
    log_format = (
        "%(asctime)s | "
        + service_name + " | "
        "%(levelname)s | "
        "%(name)s | "
        "%(message)s"
    )

    root = logging.getLogger()
    if root.handlers:
        for h in root.handlers[:]:
            root.removeHandler(h)

    logging.basicConfig(
        level=level,
        format=log_format,
    )

    logging.getLogger(__name__).info("Logging initialized")
