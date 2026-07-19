from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError

from backend.api.error_handlers import (
    register_exception_handlers,
)


def test_registers_value_error_handler():
    app = FastAPI()

    register_exception_handlers(app)

    assert ValueError in app.exception_handlers


def test_registers_type_error_handler():
    app = FastAPI()

    register_exception_handlers(app)

    assert TypeError in app.exception_handlers


def test_registers_validation_error_handler():
    app = FastAPI()

    register_exception_handlers(app)

    assert (
        RequestValidationError
        in app.exception_handlers
    )


def test_registration_is_idempotent():
    app = FastAPI()

    register_exception_handlers(app)
    register_exception_handlers(app)

    assert ValueError in app.exception_handlers
    assert TypeError in app.exception_handlers
    assert (
        RequestValidationError
        in app.exception_handlers
    )
