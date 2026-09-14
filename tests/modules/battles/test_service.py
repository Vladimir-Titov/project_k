from decimal import Decimal
from uuid import UUID

from app.modules.battles.engine import (
    ActiveEffectState,
    BattleState,
    ParticipantState,
    StatState,
    effective_stats,
    resolve_action,
    resolve_timeout,
)
from app.modules.battles.outcomes import calculate_carried_health
from app.modules.stats.enums import StatKind

ATTACKER_ID = UUID(int=1)
TARGET_ID = UUID(int=2)


def participant(participant_id: UUID, *, health: int, attack: int, defense: int) -> ParticipantState:
    return ParticipantState(
        id=participant_id,
        stats={
            'max_health': StatState('max_health', StatKind.ATTRIBUTE, Decimal(health), Decimal(1)),
            'health': StatState(
                'health',
                StatKind.RESOURCE,
                Decimal(health),
                Decimal(0),
                max_stat_code='max_health',
            ),
            'attack': StatState('attack', StatKind.ATTRIBUTE, Decimal(attack), Decimal(0)),
            'defense': StatState('defense', StatKind.ATTRIBUTE, Decimal(defense), Decimal(0)),
        },
    )


def state(*, target_health: int = 100, effects: tuple[ActiveEffectState, ...] = ()) -> BattleState:
    return BattleState(
        active_participant_id=ATTACKER_ID,
        turn_number=1,
        rng_seed=42,
        rng_counter=0,
        participants={
            ATTACKER_ID: participant(ATTACKER_ID, health=100, attack=12, defense=4),
            TARGET_ID: participant(TARGET_ID, health=target_health, attack=10, defense=7),
        },
        active_effects=effects,
    )


def attack_action() -> dict[str, object]:
    return {
        'target_policy': 'enemy',
        'effects': [
            {
                'target_selector': 'enemy',
                'effect': {
                    'code': 'basic_damage',
                    'duration': 'instant',
                    'duration_turns': None,
                    'rules': [
                        {
                            'kind': 'resource_delta',
                            'operation': 'add',
                            'evaluator_type': 'expression_v1',
                            'expression': (
                                '-max(1, round_half_up(max(1, source.attack - target.defense) '
                                '* random_int(90, 110) / 100))'
                            ),
                            'priority': 0,
                            'stat_code': 'health',
                        },
                    ],
                },
            },
        ],
    }


def rage_effect() -> dict[str, object]:
    return {
        'code': 'rage_attack_bonus',
        'duration': 'turns',
        'duration_turns': 2,
        'rules': [
            {
                'kind': 'stat_modifier',
                'operation': 'multiply',
                'evaluator_type': 'expression_v1',
                'expression': '1.25',
                'priority': 0,
                'stat_code': 'attack',
            },
        ],
    }


def test_attack_is_seeded_and_records_random_value() -> None:
    first = resolve_action(
        state(),
        action_code='basic_attack',
        action_definition=attack_action(),
        initiator_participant_id=ATTACKER_ID,
        target_participant_id=TARGET_ID,
    )
    second = resolve_action(
        state(),
        action_code='basic_attack',
        action_definition=attack_action(),
        initiator_participant_id=ATTACKER_ID,
        target_participant_id=TARGET_ID,
    )

    assert first.stat_updates == second.stat_updates
    assert Decimal(94) <= first.stat_updates[(TARGET_ID, 'health')] <= Decimal(96)
    assert first.rng_counter == 1
    stat_event = next(event for event in first.events if event.event_type == 'stat.changed')
    assert len(stat_event.payload['random_values']) == 1
    assert first.next_active_participant_id == TARGET_ID


def test_rage_modifies_attack_and_expires_after_two_later_turns() -> None:
    effect = ActiveEffectState(
        id=UUID(int=3),
        source_participant_id=ATTACKER_ID,
        target_participant_id=ATTACKER_ID,
        effect_code='rage_attack_bonus',
        definition=rage_effect(),
        remaining_turns=2,
        applied_turn=0,
    )
    battle = state(effects=(effect,))

    assert effective_stats(battle, ATTACKER_ID)['attack'] == Decimal('15.00')
    first_timeout = resolve_timeout(battle)
    assert first_timeout.effect_turn_updates == {effect.id: 1}

    later = BattleState(
        active_participant_id=ATTACKER_ID,
        turn_number=3,
        rng_seed=42,
        rng_counter=0,
        participants=battle.participants,
        active_effects=(
            ActiveEffectState(
                id=effect.id,
                source_participant_id=effect.source_participant_id,
                target_participant_id=effect.target_participant_id,
                effect_code=effect.effect_code,
                definition=effect.definition,
                remaining_turns=1,
                applied_turn=effect.applied_turn,
            ),
        ),
    )
    assert effect.id in resolve_timeout(later).expired_effect_ids


def test_defeat_finishes_before_starting_another_turn() -> None:
    result = resolve_action(
        state(target_health=1),
        action_code='basic_attack',
        action_definition=attack_action(),
        initiator_participant_id=ATTACKER_ID,
        target_participant_id=TARGET_ID,
    )

    assert result.stat_updates[(TARGET_ID, 'health')] == 0
    assert result.winner_participant_id == ATTACKER_ID
    assert result.loser_participant_id == TARGET_ID
    assert result.next_active_participant_id is None


def test_health_carryover_uses_final_percentage_without_healing() -> None:
    assert calculate_carried_health(
        health_before_battle=Decimal(60),
        max_health_before_battle=Decimal(100),
        battle_health=Decimal(50),
        effective_battle_max_health=Decimal(200),
    ) == Decimal(25)
    assert calculate_carried_health(
        health_before_battle=Decimal(60),
        max_health_before_battle=Decimal(100),
        battle_health=Decimal(200),
        effective_battle_max_health=Decimal(200),
    ) == Decimal(60)
