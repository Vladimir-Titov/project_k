from secrets import compare_digest

from starlette.requests import Request
from starlette.responses import Response
from starlette_admin.auth import AdminUser, AuthProvider
from starlette_admin.exceptions import LoginFailed

from app.core.config import AdminPanelConfig

_SESSION_LOGIN_KEY = 'admin_login'


class AdminAuthProvider(AuthProvider):
    def __init__(self, config: AdminPanelConfig) -> None:
        super().__init__()
        self.config = config

    async def login(
        self,
        username: str,
        password: str,
        remember_me: bool,
        request: Request,
        response: Response,
    ) -> Response:
        del remember_me
        valid_login = compare_digest(username, self.config.login)
        valid_password = compare_digest(
            password,
            self.config.password.get_secret_value(),
        )
        if not valid_login or not valid_password:
            raise LoginFailed('Invalid username or password')

        request.session[_SESSION_LOGIN_KEY] = self.config.login
        return response

    async def is_authenticated(self, request: Request) -> bool:
        login = request.session.get(_SESSION_LOGIN_KEY)
        if login != self.config.login:
            return False
        request.state.user = login
        return True

    def get_admin_user(self, request: Request) -> AdminUser:
        return AdminUser(username=request.state.user)

    async def logout(self, request: Request, response: Response) -> Response:
        request.session.clear()
        return response
