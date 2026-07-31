from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import NullPool
from starlette.middleware import Middleware
from starlette.middleware.sessions import SessionMiddleware
from starlette_admin.contrib.sqla import Admin

from app.admin.auth import AdminAuthProvider
from app.admin.views import create_admin_views
from app.core.config import AdminPanelConfig, DbConfig
from app.modules.auth.passwords import PasswordHasher


def create_admin(
    db_config: DbConfig,
    admin_config: AdminPanelConfig,
    password_hasher: PasswordHasher,
) -> tuple[Admin, AsyncEngine]:
    engine = create_async_engine(
        db_config.alembic_dsn,
        poolclass=NullPool,
    )
    admin = Admin(
        engine,
        title=admin_config.title,
        base_url='/admin',
        auth_provider=AdminAuthProvider(admin_config),
        middlewares=[
            Middleware(
                SessionMiddleware,
                secret_key=admin_config.session_secret.get_secret_value(),
                max_age=admin_config.session_max_age_seconds,
                same_site='lax',
                https_only=admin_config.secure_cookies,
            ),
        ],
    )
    for view in create_admin_views(password_hasher):
        admin.add_view(view)
    return admin, engine
