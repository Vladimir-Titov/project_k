from decimal import ROUND_HALF_UP, Decimal


def calculate_carried_health(
    *,
    health_before_battle: Decimal,
    max_health_before_battle: Decimal,
    battle_health: Decimal,
    effective_battle_max_health: Decimal,
) -> Decimal:
    if effective_battle_max_health <= 0:
        raise ValueError('effective battle max health must be positive')
    ratio = max(
        Decimal(0),
        min(Decimal(1), battle_health / effective_battle_max_health),
    )
    carried = (max_health_before_battle * ratio).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
    return min(health_before_battle, carried)
