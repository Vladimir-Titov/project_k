from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from settings import (
    AdminPanelConfig,
    AppConfig,
    AuthConfig,
    DbConfig,
    LogConfig,
    get_admin_panel_config,
    get_app_config,
    get_auth_config,
    get_db_config,
    get_log_config,
)
from settings.logging import setup_logging
from web.admin import create_admin
from web.api import create_api_router
from web.lifespans import create_lifespan


def create_app(
    app_config: AppConfig | None = None,
    admin_config: AdminPanelConfig | None = None,
    auth_config: AuthConfig | None = None,
    db_config: DbConfig | None = None,
    log_config: LogConfig | None = None,
) -> FastAPI:
    resolved_app_config = app_config or get_app_config()
    resolved_admin_config = admin_config or get_admin_panel_config()
    resolved_auth_config = auth_config or get_auth_config()
    resolved_db_config = db_config or get_db_config()
    resolved_log_config = log_config or get_log_config()
    setup_logging(resolved_log_config)

    admin = None
    admin_engine = None
    if resolved_admin_config.enabled:
        admin, admin_engine = create_admin(
            resolved_db_config,
            resolved_admin_config,
        )

    application = FastAPI(
        title=resolved_app_config.name,
        debug=resolved_app_config.debug,
        docs_url='/docs' if resolved_app_config.docs_enabled else None,
        redoc_url='/redoc' if resolved_app_config.docs_enabled else None,
        openapi_url='/openapi.json' if resolved_app_config.docs_enabled else None,
        lifespan=create_lifespan(
            resolved_db_config,
            resolved_auth_config,
            admin_engine,
        ),
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=resolved_app_config.cors_origins,
        allow_credentials=False,
        allow_methods=['*'],
        allow_headers=['*'],
    )
    application.include_router(create_api_router())
    if admin is not None:
        admin.mount_to(application)
    return application


app = create_app()
