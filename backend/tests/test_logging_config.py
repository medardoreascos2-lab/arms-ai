import logging

from backend.config.logging_config import (
    configure_logging,
)


def test_configure_logging_returns_logger():
    logger = configure_logging()

    assert isinstance(
        logger,
        logging.Logger,
    )


def test_logger_has_name():
    logger = configure_logging()

    assert logger.name == "arms-ai"


def test_logger_level_is_info():
    logger = configure_logging()

    assert logger.level == logging.INFO


def test_logger_can_be_called_twice():
    first = configure_logging()
    second = configure_logging()

    assert first is second
