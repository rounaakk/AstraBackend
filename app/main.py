"""Astra API application."""

import logging

from fastapi import APIRouter, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import __version__
from app.config import get_settings
from app.errors import (
    AmbiguousPlaceError,
    AstraError,
    BirthDetailsRequiredError,
    ChartCalculationError,
    DuplicateEmailError,
    DuplicatePhoneError,
    FutureBirthError,
    InvalidCredentialsError,
    KundaliNotFoundError,
    PasswordReuseError,
    PlaceNotFoundError,
)
from app.routers import auth, kundali, places, users

logger = logging.getLogger(__name__)

ERROR_STATUS = {
    DuplicateEmailError: 409,
    DuplicatePhoneError: 409,
    InvalidCredentialsError: 401,
    PlaceNotFoundError: 422,
    FutureBirthError: 422,
    BirthDetailsRequiredError: 400,
    KundaliNotFoundError: 404,
    ChartCalculationError: 500,
    PasswordReuseError: 422,
}


def create_app() -> FastAPI:
    logging.basicConfig(level=logging.INFO)
    settings = get_settings()
    if settings.default_secret:
        logger.warning("SECRET_KEY is the development default. Set SECRET_KEY before deploying.")

    app = FastAPI(
        title="Astra API",
        version=__version__,
        description=(
            "Account and kundali API for the Astra astrology app. "
            "Users and charts are kept in an in-memory store for the life of this process."
        ),
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_exception_handler(AmbiguousPlaceError, _ambiguous_place_handler)
    app.add_exception_handler(AstraError, _astra_error_handler)

    api = APIRouter(prefix="/api/v1")
    api.include_router(auth.router, prefix="/auth", tags=["Auth"])
    api.include_router(users.router, prefix="/users", tags=["Users"])
    api.include_router(kundali.router, prefix="/kundali", tags=["Kundali"])
    api.include_router(places.router, prefix="/places", tags=["Places"])
    app.include_router(api)

    @app.get("/health", tags=["Health"])
    def health() -> dict[str, str]:
        return {"status": "ok", "store": "memory"}

    @app.get("/", tags=["Health"])
    def root() -> dict[str, str]:
        return {"name": "Astra API", "docs": "/docs", "health": "/health"}

    return app


async def _astra_error_handler(_request: Request, exc: AstraError) -> JSONResponse:
    status_code = 400
    for error_type in type(exc).__mro__:
        if error_type in ERROR_STATUS:
            status_code = ERROR_STATUS[error_type]
            break
    if status_code >= 500:
        logger.error("Request failed: %s", exc.message)
    return JSONResponse(status_code=status_code, content={"detail": exc.message})


async def _ambiguous_place_handler(_request: Request, exc: AmbiguousPlaceError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={"detail": exc.message, "candidates": exc.candidates},
    )


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
