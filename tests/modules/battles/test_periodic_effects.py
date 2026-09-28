from dataclasses import replace
from decimal import Decimal
from uuid import UUID

import pytest

from app.modules.battles.engine import ActiveEffectState, resolve_action, resolve_timeout
from tests.modules.battles.test_service import ATTACKER_ID, TARGET_ID, state


def periodic_state(*, health=100, turns=2, expression='-3'):
    effect = ActiveEffectState(
        id=UUID(int=99),
        source_participant_id=ATTACKER_ID,
        target_participant_id=TARGET_ID,
        effect_code='poison',
        remaining_turns=turns,
        applied_turn=1,
        definition={
            'code': 'poison',
            'duration': 'turns',
            'duration_turns': turns,
            'rules': [
                {
                    'kind': 'resource_delta',
                    'operation': 'add',
                    'evaluator_type': 'expression_v1',
                    'expression': expression,
                    'priority': 0,
                    'stat_code': 'health',
                }
            ],
        },
    )
    return replace(state(target_health=health, effects=(effect,)), active_participant_id=TARGET_ID, turn_number=2)


def pass_action(battle):
    return resolve_action(
        battle,
        action_code='pass',
        action_definition={'effects': []},
        initiator_participant_id=battle.active_participant_id,
        target_participant_id=ATTACKER_ID,
    )


@pytest.mark.parametrize('resolve', [pass_action, resolve_timeout])
def test_periodic_damage_ticks_after_action_and_timeout(resolve):
    result = resolve(periodic_state())
    assert result.stat_updates[(TARGET_ID, 'health')] == 97
    assert result.effect_turn_updates == {UUID(int=99): 1}
    assert result.next_active_participant_id == ATTACKER_ID


def test_last_tick_happens_before_effect_expires():
    result = resolve_timeout(periodic_state(turns=1))
    assert result.stat_updates[(TARGET_ID, 'health')] == 97
    assert result.expired_effect_ids == {UUID(int=99)}
    assert [event.event_type for event in result.events] == [
        'turn.timed_out',
        'stat.changed',
        'effect.expired',
        'turn.started',
    ]


@pytest.mark.parametrize('resolve', [pass_action, resolve_timeout])
def test_lethal_tick_finishes_battle_without_starting_next_turn(resolve):
    result = resolve(periodic_state(health=2))
    assert result.stat_updates[(TARGET_ID, 'health')] == 0
    assert result.winner_participant_id == ATTACKER_ID
    assert result.loser_participant_id == TARGET_ID
    assert result.next_active_participant_id is None
    assert result.events[-1].event_type == 'battle.finished'


def test_periodic_healing_is_clamped_and_does_not_tick_on_other_participants_turn():
    battle = periodic_state(expression='5')
    assert resolve_timeout(battle).stat_updates[(TARGET_ID, 'health')] == 100
    assert not resolve_timeout(replace(battle, active_participant_id=ATTACKER_ID)).stat_updates
    assert not resolve_timeout(replace(battle, turn_number=1)).stat_updates


def test_periodic_random_draws_are_reproducible_and_advance_counter():
    battle = periodic_state(expression='-random_int(2, 5)')
    first, second = resolve_timeout(battle), resolve_timeout(battle)
    assert first.stat_updates == second.stat_updates
    assert Decimal(95) <= first.stat_updates[(TARGET_ID, 'health')] <= Decimal(98)
    assert first.rng_counter == 1
    assert len(first.events[1].payload['random_values']) == 1


def test_refresh_does_not_tick_or_decrease_refreshed_effect():
    battle = periodic_state()
    result = resolve_action(
        battle,
        action_code='refresh',
        action_definition={'effects': [{'target_selector': 'self', 'effect': battle.active_effects[0].definition}]},
        initiator_participant_id=TARGET_ID,
        target_participant_id=TARGET_ID,
    )
    assert len(result.effect_applications) == 1
    assert not result.stat_updates
    assert not result.effect_turn_updates
