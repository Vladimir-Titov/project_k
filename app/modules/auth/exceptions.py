class InvalidCredentialsError(Exception):
    """Raised when login credentials cannot be authenticated."""


class LoginAlreadyExistsError(Exception):
    """Raised when a registration login is already occupied."""


class InvalidTokenError(Exception):
    """Raised when a JWT or its server-side session cannot be trusted."""


class InvalidAccessTokenError(InvalidTokenError):
    """Raised when an access token cannot be authenticated."""


class InvalidRefreshTokenError(InvalidTokenError):
    """Raised when a refresh token or its session cannot be trusted."""


class AuthenticationRequiredError(Exception):
    """Raised when an authenticated endpoint receives no bearer token."""
