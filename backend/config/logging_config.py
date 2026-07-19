import logging


def configure_logging(
    *,
    level: int = logging.INFO,
) -> logging.Logger:
    """
    Configura y devuelve el logger principal
    de ARMS AI.
    """

    logger = logging.getLogger(
        "arms-ai"
    )
    logger.setLevel(
        level
    )

    if not logger.handlers:
        handler = logging.StreamHandler()

        formatter = logging.Formatter(
            "%(asctime)s | "
            "%(levelname)s | "
            "%(name)s | "
            "%(message)s"
        )

        handler.setFormatter(
            formatter
        )

        logger.addHandler(
            handler
        )

    logger.propagate = False

    return logger
