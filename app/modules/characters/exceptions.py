class CharacterAlreadyExistsError(Exception):
    """Raised when an account already owns its MVP character."""


class NicknameAlreadyExistsError(Exception):
    """Raised when a character nickname is already occupied."""


class CharacterNotFoundError(Exception):
    """Raised when a selectable character is unavailable to the account."""


class CharacterClassNotFoundError(Exception):
    """Raised when a requested playable class does not exist."""


class InvalidCharacterClassError(Exception):
    """Raised when a class has incomplete or invalid content."""


class CharacterBusyError(Exception):
    """Raised when an out-of-battle operation is requested during a fight."""
