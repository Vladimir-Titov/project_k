from decimal import Decimal

import pytest

from app.modules.content.expressions import (
    InvalidExpressionError,
    RandomSource,
    evaluate_expression,
    validate_expression,
)


def test_expression_v1_uses_decimal_stats_and_seeded_random() -> None:
    random_source = RandomSource(seed=7)
    value = evaluate_expression(
        'expression_v1',
        'round_half_up(max(1, source.attack - target.defense) * random_int(90, 110) / 100)',
        source={'attack': Decimal(12)},
        target={'defense': Decimal(4)},
        random_source=random_source,
    )

    assert Decimal(7) <= value <= Decimal(9)
    assert random_source.counter == 1
    assert len(random_source.draws) == 1


@pytest.mark.parametrize(
    'expression',
    [
        '__import__("os")',
        'source.__class__',
        'source.missing + 1',
        '[value for value in source]',
    ],
)
def test_expression_v1_rejects_unsafe_or_unknown_content(expression: str) -> None:
    with pytest.raises(InvalidExpressionError):
        validate_expression('expression_v1', expression, available_stat_codes={'attack'})


def test_random_is_rejected_for_recomputed_stat_modifiers() -> None:
    with pytest.raises(InvalidExpressionError):
        validate_expression('expression_v1', 'random_int(1, 2)', allow_random=False)
