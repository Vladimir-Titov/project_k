class InvalidGameSessionError(Exception):
    """Raised when server-side session context is unavailable."""


class CharacterRequiredError(Exception):
    """Raised when a game command requires an active character."""
