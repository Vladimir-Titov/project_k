class FightTargetNotFoundError(Exception):
    """Raised when a requested battle target does not exist."""


class FightNotFoundError(Exception):
    """Raised when the character cannot access a fight."""


class FightUnavailableError(Exception):
    """Raised when either participant is already fighting or cannot fight."""


class FightFinishedError(Exception):
    pass


class NotYourTurnError(Exception):
    pass


class TurnExpiredError(Exception):
    pass


class StaleFightVersionError(Exception):
    pass


class FightActionNotAvailableError(Exception):
    pass


class InvalidFightActionError(Exception):
    pass
