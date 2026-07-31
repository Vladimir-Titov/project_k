class InvalidCredentialsError(Exception):
    """Raised when login credentials cannot be authenticated."""


class LoginAlreadyExistsError(Exception):
    """Raised when a registration login is already occupied."""


class InvalidTokenError(Exception):
    """Raised when a JWT or its server-side session cannot be trusted."""
