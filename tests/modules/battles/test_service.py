from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID

import pytest

from app.modules.battles.engine import (
    ActiveEffectState,
    BattleState,
    ParticipantState,
    StatState,
    effective_stats,
    resolve_action,
    resolve_timeout,
)
from app.modules.battles.models import Fight
from app.modules.battles.outcomes import calculate_carried_health
from app.modules.battles.service import FightService
from app.modules.bots.models import BotTemplate
from app.modules.content.enums import EffectDuration, TargetPolicy
from app.modules.content.models import ActionDefinition, ActionEffect, EffectDefinition
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


@pytest.mark.asyncio
async def test_bot_turn_uses_snapshotted_basic_attack() -> None:
    bot = SimpleNamespace(id=TARGET_ID, source_type='bot', source_id=UUID(int=10))
    hero = SimpleNamespace(id=ATTACKER_ID, source_type='character', source_id=ATTACKER_ID)
    fight = Fight(
        title='Hero против Bot',
        active_participant_id=TARGET_ID,
        content_snapshot={
            'actions': {str(bot.source_id): {'basic_attack': attack_action()}},
            'bot_action_priority': ['basic_attack'],
        },
    )
    action = SimpleNamespace(id=UUID(int=11))
    updated = Fight(title=fight.title, active_participant_id=ATTACKER_ID)
    repositories = SimpleNamespace(
        fight_participants=SimpleNamespace(
            get_in_fight=AsyncMock(return_value=bot),
            list_for_fight=AsyncMock(return_value=[hero, bot]),
        ),
        fight_actions=SimpleNamespace(
            create_or_get=AsyncMock(return_value=(action, True)),
            save_result=AsyncMock(),
        ),
        fights=SimpleNamespace(get_by_id=AsyncMock(return_value=updated)),
    )
    service = FightService(repositories)
    service._engine_state = AsyncMock(
        return_value=BattleState(
            active_participant_id=TARGET_ID,
            turn_number=2,
            rng_seed=42,
            rng_counter=0,
            participants={
                ATTACKER_ID: participant(ATTACKER_ID, health=100, attack=12, defense=4),
                TARGET_ID: participant(TARGET_ID, health=65, attack=9, defense=2),
            },
            active_effects=(),
        )
    )
    service._persist_result = AsyncMock(return_value=[])

    result = await service._take_bot_turn(fight)

    assert result is updated
    assert repositories.fight_actions.create_or_get.await_args.kwargs['action_code'] == 'basic_attack'
    engine_result = service._persist_result.await_args.args[1]
    assert engine_result.stat_updates[(ATTACKER_ID, 'health')] < Decimal(100)
    assert engine_result.next_active_participant_id == ATTACKER_ID


@pytest.mark.asyncio
async def test_bot_fight_uses_new_spawn_id_for_each_fight() -> None:
    template = BotTemplate(
        id=UUID(int=10),
        code='bandit',
        title='Bandit',
        is_active=True,
    )
    hero = SimpleNamespace(id=ATTACKER_ID, is_archived=False)
    repositories = SimpleNamespace(
        characters=SimpleNamespace(get_by_id=AsyncMock(return_value=hero)),
        bot_templates=SimpleNamespace(get_by_id=AsyncMock(return_value=template)),
        bot_template_actions=SimpleNamespace(list_for_template=AsyncMock(return_value=[SimpleNamespace()])),
    )
    service = FightService(repositories)
    service._bot_snapshot = AsyncMock(return_value={'health': {}, 'max_health': {}, 'attack': {}, 'defense': {}})
    service._actions_snapshot = AsyncMock(return_value={'basic_attack': attack_action()})
    service._create_fight = AsyncMock(return_value=Fight(title='test'))

    await service.create_bot_fight(attacker_id=ATTACKER_ID, bot_template_id=template.id)
    first_id = service._create_fight.await_args.kwargs['target_source_id']
    await service.create_bot_fight(attacker_id=ATTACKER_ID, bot_template_id=template.id)
    second_id = service._create_fight.await_args.kwargs['target_source_id']

    assert first_id != second_id
    assert first_id != template.id
    assert service._create_fight.await_args.kwargs['bot_template_id'] == template.id


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


@pytest.mark.asyncio
async def test_definition_images_are_preserved_in_battle_snapshots() -> None:
    action = ActionDefinition(
        code='rage',
        title='Rage',
        target_policy=TargetPolicy.SELF,
        image_url='https://assets.example.com/actions/rage.png',
    )
    effect = EffectDefinition(
        code='rage_attack_bonus',
        title='Rage bonus',
        duration=EffectDuration.TURNS,
        duration_turns=2,
        image_url='https://assets.example.com/effects/rage.png',
    )
    link = ActionEffect(
        action_definition_id=action.id,
        effect_definition_id=effect.id,
        target_selector=TargetPolicy.SELF,
    )
    repositories = SimpleNamespace(
        character_actions=SimpleNamespace(list_for_character=AsyncMock(return_value=[link])),
        action_definitions=SimpleNamespace(get_by_id=AsyncMock(return_value=action)),
        action_effects=SimpleNamespace(list_for_action=AsyncMock(return_value=[link])),
        effect_definitions=SimpleNamespace(get_by_id=AsyncMock(return_value=effect)),
        effect_rules=SimpleNamespace(list_for_effect=AsyncMock(return_value=[])),
    )

    snapshot = await FightService(repositories)._action_snapshot(ATTACKER_ID, set())

    assert snapshot['rage']['image_url'] == action.image_url
    assert snapshot['rage']['effects'][0]['effect']['image_url'] == effect.image_url


@pytest.mark.parametrize('definition_snapshot', ({}, {'image_url': 'https://assets.example.com/effects/rage.png'}))
@pytest.mark.asyncio
async def test_battle_state_returns_effect_images_and_accepts_older_snapshots(definition_snapshot) -> None:
    fight = Fight(title='Test battle', active_participant_id=ATTACKER_ID, turn_deadline_at=datetime.now(UTC))
    participants = [
        SimpleNamespace(
            id=ATTACKER_ID, source_type='character', source_id=ATTACKER_ID, display_name='Hero', side='team_a'
        ),
        SimpleNamespace(
            id=TARGET_ID, source_type='character', source_id=TARGET_ID, display_name='Enemy', side='team_b'
        ),
    ]
    effect = SimpleNamespace(
        effect_code='rage_attack_bonus',
        source_participant_id=ATTACKER_ID,
        target_participant_id=ATTACKER_ID,
        definition_snapshot=definition_snapshot,
        remaining_turns=2,
    )
    fight.content_snapshot = {'actions': {str(ATTACKER_ID): {'rage': {}}}}
    repositories = SimpleNamespace(
        fight_participants=SimpleNamespace(list_for_fight=AsyncMock(return_value=participants)),
        fight_active_effects=SimpleNamespace(list_for_fight=AsyncMock(return_value=[effect])),
        fight_participant_stats=SimpleNamespace(list_for_participant=AsyncMock(return_value=[])),
        fight_events=SimpleNamespace(list_after=AsyncMock(return_value=[])),
    )
    service = FightService(repositories)
    service._engine_state = AsyncMock(return_value=state())

    response = await service._state_response(fight, participants[0], 0)

    assert response.model_dump(mode='json')['participants'][0]['effects'][0]['image_url'] == definition_snapshot.get(
        'image_url'
    )
    assert response.available_actions == ['rage']
