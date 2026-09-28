from decimal import Decimal
from math import ceil

from app.modules.locations.exceptions import InvalidMovementSpeedError


def calculate_cooldown(base_duration_seconds: int, speed: Decimal) -> int:
    if not speed.is_finite() or speed <= 0:
        raise InvalidMovementSpeedError
    return max(1, ceil(Decimal(base_duration_seconds) * 100 / speed))
