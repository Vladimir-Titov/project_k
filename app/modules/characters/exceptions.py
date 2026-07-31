class CharacterAlreadyExistsError(Exception):
    """Raised when an account already owns its MVP character."""


class NicknameAlreadyExistsError(Exception):
    """Raised when a character nickname is already occupied."""


class CharacterNotFoundError(Exception):
    """Raised when a selectable character is unavailable to the account."""
