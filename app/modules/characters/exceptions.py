class InvalidGameSessionError(Exception):
    """Raised when server-side session context is unavailable."""


class CharacterRequiredError(Exception):
    """Raised when a game command requires an active character."""


class CharacterAlreadyExistsError(Exception):
    """Raised when an account already owns its MVP character."""


class NicknameAlreadyExistsError(Exception):
    """Raised when a character nickname is already occupied."""


class CharacterNotFoundError(Exception):
    """Raised when a selectable character is unavailable to the account."""
