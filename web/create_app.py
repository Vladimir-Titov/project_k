from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from settings import (
    AppConfig,
    AuthConfig,
    DbConfig,
    LogConfig,
    get_app_config,
    get_auth_config,
    get_db_config,
    get_log_config,
)
from settings.logging import setup_logging
from web.api import create_api_router
from web.lifespans import create_lifespan


def create_app(
    app_config: AppConfig | None = None,
    auth_config: AuthConfig | None = None,
    db_config: DbConfig | None = None,
    log_config: LogConfig | None = None,
) -> FastAPI:
    resolved_app_config = app_config or get_app_config()
    resolved_auth_config = auth_config or get_auth_config()
    resolved_db_config = db_config or get_db_config()
    resolved_log_config = log_config or get_log_config()
    setup_logging(resolved_log_config)

    application = FastAPI(
        title=resolved_app_config.name,
        debug=resolved_app_config.debug,
        docs_url='/docs' if resolved_app_config.docs_enabled else None,
        redoc_url='/redoc' if resolved_app_config.docs_enabled else None,
        openapi_url='/openapi.json' if resolved_app_config.docs_enabled else None,
        lifespan=create_lifespan(resolved_db_config, resolved_auth_config),
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=resolved_app_config.cors_origins,
        allow_credentials=False,
        allow_methods=['*'],
        allow_headers=['*'],
    )
    application.include_router(create_api_router())
    return application


app = create_app()
