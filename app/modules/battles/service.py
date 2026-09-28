import secrets
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid7

import asyncpg

from app.container import Repositories
from app.core.config import BattleConfig, get_battle_config
from app.modules.battles.engine import (
    ActiveEffectState,
    BattleState,
    EngineResult,
    ParticipantState,
    StatState,
    effective_stats,
    resolve_action,
    resolve_timeout,
)
from app.modules.battles.enums import FightSide, FightStatus
from app.modules.battles.exceptions import (
    FightActionNotAvailableError,
    FightFinishedError,
    FightNotFoundError,
    FightTargetNotFoundError,
    FightUnavailableError,
    InvalidFightActionError,
    NotYourTurnError,
    StaleFightVersionError,
    TurnExpiredError,
)
from app.modules.battles.models import Fight, FightAction, FightEvent, FightParticipants
from app.modules.battles.outcomes import calculate_carried_health
from app.modules.battles.schemas import (
    BotTargetResponse,
    FightActionResponse,
    FightActiveEffectResponse,
    FightEventResponse,
    FightParticipantResponse,
    FightParticipantStatResponse,
    FightStateResponse,
    FightTargetResponse,
)
from app.modules.bots.behavior import choose_action
from app.modules.bots.models import BotTemplate
from app.modules.characters.models import Character
from app.modules.content.enums import TargetPolicy
from app.modules.content.expressions import InvalidExpressionError, validate_expression


class FightService:
    def __init__(self, repositories: Repositories, config: BattleConfig | None = None) -> None:
        self.repositories = repositories
        self.turn_duration = timedelta(seconds=(config or get_battle_config()).turn_duration_seconds)

    async def list_targets(self, character_id: UUID) -> list[FightTargetResponse]:
        result: list[FightTargetResponse] = []
        for character in await self.repositories.characters.list_active_except(character_id):
            if await self.repositories.fight_participants.get_active_for_source('character', character.id):
                continue
            stats = await self._character_stats_by_code(character.id)
            if stats.get('health', Decimal(0)) <= 0:
                continue
            character_class = await self.repositories.character_classes.get_by_id(character.class_id)
            if character_class is not None and character_class.is_playable and not character_class.is_archived:
                result.append(
                    FightTargetResponse(
                        id=character.id,
                        nickname=character.nickname,
                        class_code=character_class.code,
                    ),
                )
        return result

    async def create_fight(self, attacker_id: UUID, target_id: UUID) -> Fight:
        if attacker_id == target_id:
            raise FightTargetNotFoundError
        locked = {}
        for character_id in sorted((attacker_id, target_id)):
            locked[character_id] = await self.repositories.characters.get_for_update(character_id)
        attacker = locked[attacker_id]
        target = locked[target_id]
        if attacker is None or attacker.is_archived or target is None or target.is_archived:
            raise FightTargetNotFoundError
        if await self.repositories.fight_participants.get_active_for_source('character', target.id):
            raise FightUnavailableError
        target_stats = await self._character_snapshot(target.id)
        target_actions = await self._action_snapshot(target.id, set(target_stats))
        return await self._create_fight(
            attacker=attacker,
            target_name=target.nickname,
            target_source_type='character',
            target_source_id=target.id,
            target_stats=target_stats,
            target_actions=target_actions,
        )

    async def list_bot_targets(self, character_id: UUID) -> list[BotTargetResponse]:
        del character_id
        result: list[BotTargetResponse] = []
        for template in await self.repositories.bot_templates.list_active():
            try:
                stats = await self._bot_snapshot(template)
            except FightUnavailableError:
                continue
            result.append(
                BotTargetResponse(
                    id=template.id,
                    code=template.code,
                    title=template.title,
                    description=template.description,
                    stats={code: stat['current_value'] for code, stat in stats.items()},
                ),
            )
        return result

    async def create_bot_fight(self, *, attacker_id: UUID, bot_template_id: UUID) -> Fight:
        attacker = await self.repositories.characters.get_for_update(attacker_id)
        template = await self.repositories.bot_templates.get_by_id(bot_template_id)
        if (
            attacker is None
            or attacker.is_archived
            or template is None
            or template.is_archived
            or not template.is_active
        ):
            raise FightTargetNotFoundError
        bot_stats = await self._bot_snapshot(template)
        links = await self.repositories.bot_template_actions.list_for_template(template.id)
        bot_actions = await self._actions_snapshot(links, set(bot_stats))
        bot_priority = list(bot_actions)
        if not bot_priority:
            raise FightUnavailableError
        return await self._create_fight(
            attacker=attacker,
            target_name=template.title,
            target_source_type='bot',
            target_source_id=uuid7(),
            target_stats=bot_stats,
            target_actions=bot_actions,
            bot_template_id=template.id,
            bot_priority=bot_priority,
        )

    async def _create_fight(
        self,
        *,
        attacker: Character,
        target_name: str,
        target_source_type: str,
        target_source_id: UUID,
        target_stats: dict[str, dict[str, Any]],
        target_actions: dict[str, Any],
        bot_template_id: UUID | None = None,
        bot_priority: list[str] | None = None,
    ) -> Fight:
        if await self.repositories.fight_participants.get_active_for_source('character', attacker.id):
            raise FightUnavailableError
        attacker_stats = await self._character_snapshot(attacker.id)
        if attacker_stats['health']['current_value'] <= 0 or target_stats['health']['current_value'] <= 0:
            raise FightUnavailableError
        content_snapshot = {
            'actions': {
                str(attacker.id): await self._action_snapshot(attacker.id, set(attacker_stats)),
                str(target_source_id): target_actions,
            },
        }
        if bot_priority is not None:
            content_snapshot['bot_action_priority'] = bot_priority
        now = datetime.now(UTC)
        fight = await self.repositories.fights.create(
            status=FightStatus.started,
            version=1,
            turn_number=1,
            active_participant_id=None,
            turn_deadline_at=now + self.turn_duration,
            winner_participant_id=None,
            finish_reason=None,
            rng_seed=secrets.randbits(63),
            rng_counter=0,
            next_event_sequence=1,
            content_snapshot=content_snapshot,
            title=f'{attacker.nickname} против {target_name}',
        )
        try:
            attacker_participant = await self.repositories.fight_participants.create(
                fight_id=fight.id,
                source_type='character',
                source_id=attacker.id,
                display_name=attacker.nickname,
                side=FightSide.team_a,
                turn_order=1,
                is_active=True,
                health_before_battle=attacker_stats['health']['current_value'],
                max_health_before_battle=attacker_stats['max_health']['current_value'],
            )
            target_participant = await self.repositories.fight_participants.create(
                fight_id=fight.id,
                source_type=target_source_type,
                source_id=target_source_id,
                bot_template_id=bot_template_id,
                display_name=target_name,
                side=FightSide.team_b,
                turn_order=2,
                is_active=True,
                health_before_battle=target_stats['health']['current_value'],
                max_health_before_battle=target_stats['max_health']['current_value'],
            )
        except asyncpg.UniqueViolationError as error:
            raise FightUnavailableError from error
        await self._store_participant_stats(attacker_participant.id, attacker_stats)
        await self._store_participant_stats(target_participant.id, target_stats)
        await self.repositories.fights.update_state(
            fight.id,
            active_participant_id=attacker_participant.id,
            next_event_sequence=3,
        )
        fight.active_participant_id = attacker_participant.id
        fight.next_event_sequence = 3
        await self.repositories.fight_events.create_many(
            [
                {
                    'fight_id': fight.id,
                    'fight_action_id': None,
                    'sequence_number': 1,
                    'event_type': 'battle.started',
                    'payload': {
                        'attacker_participant_id': str(attacker_participant.id),
                        'target_participant_id': str(target_participant.id),
                    },
                },
                {
                    'fight_id': fight.id,
                    'fight_action_id': None,
                    'sequence_number': 2,
                    'event_type': 'turn.started',
                    'payload': {'participant_id': str(attacker_participant.id), 'turn_number': 1},
                },
            ],
        )
        return fight

    async def get_active_state(self, *, character_id: UUID, events_after: int = 0) -> FightStateResponse:
        participant = await self.repositories.fight_participants.get_active_for_source('character', character_id)
        if participant is None:
            raise FightNotFoundError
        return await self.get_state(fight_id=participant.fight_id, character_id=character_id, events_after=events_after)

    async def get_state(
        self,
        *,
        fight_id: UUID,
        character_id: UUID,
        events_after: int = 0,
    ) -> FightStateResponse:
        fight = await self.repositories.fights.get_for_update(fight_id)
        if fight is None or fight.is_archived:
            raise FightNotFoundError
        requester = await self.repositories.fight_participants.get_for_character(
            fight_id=fight_id,
            character_id=character_id,
        )
        if requester is None:
            raise FightNotFoundError
        if fight.status in {FightStatus.started, FightStatus.in_progress} and fight.turn_deadline_at <= datetime.now(
            UTC
        ):
            await self._resolve_timeout(fight)
            fight = await self.repositories.fights.get_for_update(fight_id)
            if fight is None:
                raise FightNotFoundError
        fight = await self._take_bot_turn(fight)
        return await self._state_response(fight, requester, events_after)

    async def perform_action(  # noqa: C901, PLR0912
        self,
        *,
        fight_id: UUID,
        character_id: UUID,
        idempotency_key: UUID,
        expected_version: int,
        action_code: str,
        target_participant_id: UUID,
    ) -> FightActionResponse:
        fight = await self.repositories.fights.get_for_update(fight_id)
        if fight is None or fight.is_archived:
            raise FightNotFoundError
        initiator = await self.repositories.fight_participants.get_for_character(
            fight_id=fight_id,
            character_id=character_id,
            for_update=True,
        )
        if initiator is None:
            raise FightNotFoundError
        existing = await self.repositories.fight_actions.get_idempotent(
            fight_id=fight_id,
            initiator_participant_id=initiator.id,
            idempotency_key=idempotency_key,
        )
        if existing is not None and existing.result is not None:
            return FightActionResponse.model_validate(existing.result)
        if fight.status not in {FightStatus.started, FightStatus.in_progress}:
            raise FightFinishedError
        if fight.version != expected_version:
            raise StaleFightVersionError
        if fight.active_participant_id != initiator.id:
            raise NotYourTurnError
        if fight.turn_deadline_at <= datetime.now(UTC):
            raise TurnExpiredError

        target = await self.repositories.fight_participants.get_in_fight(fight_id, target_participant_id)
        if target is None:
            raise InvalidFightActionError
        actions = fight.content_snapshot['actions'].get(str(character_id), {})
        action_definition = actions.get(action_code)
        if action_definition is None:
            raise FightActionNotAvailableError
        if action_definition['target_policy'] == TargetPolicy.SELF and target.id != initiator.id:
            raise InvalidFightActionError
        if action_definition['target_policy'] == TargetPolicy.ENEMY and target.id == initiator.id:
            raise InvalidFightActionError

        fight_action, was_created = await self.repositories.fight_actions.create_or_get(
            fight_id=fight.id,
            initiator_participant_id=initiator.id,
            target_participant_id=target.id,
            idempotency_key=idempotency_key,
            action_code=action_code,
            turn_number=fight.turn_number,
        )
        if not was_created:
            if fight_action.result is None:
                raise InvalidFightActionError
            return FightActionResponse.model_validate(fight_action.result)

        state = await self._engine_state(fight)
        try:
            result = resolve_action(
                state,
                action_code=action_code,
                action_definition=action_definition,
                initiator_participant_id=initiator.id,
                target_participant_id=target.id,
            )
        except (InvalidExpressionError, ValueError) as error:
            raise InvalidFightActionError from error
        first_new_event = fight.next_event_sequence - 1
        await self._persist_result(fight, result, fight_action=fight_action)
        updated = await self.repositories.fights.get_by_id(fight.id)
        if updated is None:
            raise RuntimeError('Fight disappeared after action')
        updated = await self._take_bot_turn(updated)
        events = await self.repositories.fight_events.list_after(fight.id, first_new_event)
        response = FightActionResponse(
            fight_action_id=fight_action.id,
            fight_id=fight.id,
            version=updated.version,
            turn_number=updated.turn_number,
            status=updated.status,
            events=[self._event_response(event) for event in events],
        )
        await self.repositories.fight_actions.save_result(fight_action.id, response.model_dump(mode='json'))
        return response

    async def _take_bot_turn(self, fight: Fight) -> Fight:
        if fight.status not in {FightStatus.started, FightStatus.in_progress} or fight.active_participant_id is None:
            return fight
        bot = await self.repositories.fight_participants.get_in_fight(fight.id, fight.active_participant_id)
        if bot is None or bot.source_type != 'bot':
            return fight
        participants = await self.repositories.fight_participants.list_for_fight(fight.id)
        target = next(participant for participant in participants if participant.id != bot.id)
        actions = fight.content_snapshot['actions'][str(bot.source_id)]
        try:
            action_code = choose_action(actions, fight.content_snapshot['bot_action_priority'])
            definition = actions[action_code]
            chosen_target = bot if definition['target_policy'] == TargetPolicy.SELF else target
            fight_action, _ = await self.repositories.fight_actions.create_or_get(
                fight_id=fight.id,
                initiator_participant_id=bot.id,
                target_participant_id=chosen_target.id,
                idempotency_key=uuid7(),
                action_code=action_code,
                turn_number=fight.turn_number,
            )
            result = resolve_action(
                await self._engine_state(fight),
                action_code=action_code,
                action_definition=definition,
                initiator_participant_id=bot.id,
                target_participant_id=chosen_target.id,
            )
        except (InvalidExpressionError, ValueError) as error:
            raise InvalidFightActionError from error
        events = await self._persist_result(fight, result, fight_action=fight_action)
        updated = await self.repositories.fights.get_by_id(fight.id)
        if updated is None:
            raise RuntimeError('Fight disappeared after bot action')
        await self.repositories.fight_actions.save_result(
            fight_action.id,
            FightActionResponse(
                fight_action_id=fight_action.id,
                fight_id=fight.id,
                version=updated.version,
                turn_number=updated.turn_number,
                status=updated.status,
                events=[self._event_response(event) for event in events],
            ).model_dump(mode='json'),
        )
        return updated

    async def _character_stats_by_code(self, character_id: UUID) -> dict[str, Decimal]:
        return {item['code']: item['current_value'] for item in (await self._character_snapshot(character_id)).values()}

    async def _character_snapshot(self, character_id: UUID) -> dict[str, dict[str, Any]]:
        result = await self._stats_snapshot(
            await self.repositories.character_stats.list_for_character(character_id, for_update=True),
        )
        if {'health', 'max_health', 'attack', 'defense'} - set(result):
            raise FightUnavailableError
        return result

    async def _stats_snapshot(self, values: list[Any]) -> dict[str, dict[str, Any]]:
        result: dict[str, dict[str, Any]] = {}
        for value in values:
            definition = await self.repositories.stat_definitions.get_by_id(value.stat_definition_id)
            if definition is None or definition.is_archived:
                continue
            max_stat_code = None
            if definition.max_stat_definition_id is not None:
                maximum = await self.repositories.stat_definitions.get_by_id(definition.max_stat_definition_id)
                max_stat_code = maximum.code if maximum is not None else None
            result[definition.code] = {
                'stat_definition_id': definition.id,
                'code': definition.code,
                'kind': definition.kind,
                'max_stat_code': max_stat_code,
                'min_value': definition.min_value,
                'max_value': definition.max_value,
                'initial_value': value.value,
                'current_value': value.value,
            }
        return result

    async def _bot_snapshot(self, template: BotTemplate) -> dict[str, dict[str, Any]]:
        result = await self._stats_snapshot(
            await self.repositories.bot_template_stats.list_for_template(template.id),
        )
        if {'health', 'max_health', 'attack', 'defense'} - set(result):
            raise FightUnavailableError
        if result['health']['current_value'] <= 0 or result['max_health']['current_value'] <= 0:
            raise FightUnavailableError
        if result['health']['current_value'] > result['max_health']['current_value']:
            raise FightUnavailableError
        for stat in result.values():
            value = stat['current_value']
            maximum_code = stat['max_stat_code']
            if (
                (stat['min_value'] is not None and value < stat['min_value'])
                or (stat['max_value'] is not None and value > stat['max_value'])
                or (
                    maximum_code is not None
                    and (maximum_code not in result or value > result[maximum_code]['current_value'])
                )
            ):
                raise FightUnavailableError
        return result

    async def _store_participant_stats(self, participant_id: UUID, values: dict[str, dict[str, Any]]) -> None:
        await self.repositories.fight_participant_stats.create_many(
            [{'participant_id': participant_id, **value} for value in values.values()],
        )

    async def _action_snapshot(self, character_id: UUID, stat_codes: set[str]) -> dict[str, Any]:
        return await self._actions_snapshot(
            await self.repositories.character_actions.list_for_character(character_id),
            stat_codes,
        )

    async def _actions_snapshot(self, links: list[Any], stat_codes: set[str]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for link in links:
            action = await self.repositories.action_definitions.get_by_id(link.action_definition_id)
            if action is None or action.is_archived or not action.is_active:
                continue
            effects: list[dict[str, Any]] = []
            for action_effect in await self.repositories.action_effects.list_for_action(action.id):
                effect = await self.repositories.effect_definitions.get_by_id(action_effect.effect_definition_id)
                if effect is None or effect.is_archived or not effect.is_active:
                    continue
                rules: list[dict[str, Any]] = []
                for rule in await self.repositories.effect_rules.list_for_effect(effect.id):
                    stat = await self.repositories.stat_definitions.get_by_id(rule.stat_definition_id)
                    if stat is None or stat.code not in stat_codes:
                        raise FightUnavailableError
                    validate_expression(
                        rule.evaluator_type,
                        rule.expression,
                        available_stat_codes=stat_codes,
                        allow_random=rule.kind.value != 'stat_modifier',
                    )
                    rules.append(
                        {
                            'kind': rule.kind.value,
                            'operation': rule.operation.value,
                            'evaluator_type': rule.evaluator_type,
                            'expression': rule.expression,
                            'priority': rule.priority,
                            'stat_code': stat.code,
                        },
                    )
                effects.append(
                    {
                        'target_selector': action_effect.target_selector.value,
                        'effect': {
                            'code': effect.code,
                            'image_url': effect.image_url,
                            'duration': effect.duration.value,
                            'duration_turns': effect.duration_turns,
                            'stacking_policy': effect.stacking_policy.value,
                            'rules': rules,
                        },
                    },
                )
            result[action.code] = {
                'code': action.code,
                'image_url': action.image_url,
                'target_policy': action.target_policy.value,
                'effects': effects,
            }
        return result

    async def _engine_state(self, fight: Fight) -> BattleState:
        if fight.active_participant_id is None:
            raise InvalidFightActionError
        participants: dict[UUID, ParticipantState] = {}
        for participant in await self.repositories.fight_participants.list_for_fight(fight.id, for_update=True):
            stats = {
                stat.code: StatState(
                    code=stat.code,
                    kind=stat.kind,
                    current_value=stat.current_value,
                    min_value=stat.min_value,
                    max_value=stat.max_value,
                    max_stat_code=stat.max_stat_code,
                )
                for stat in await self.repositories.fight_participant_stats.list_for_participant(
                    participant.id,
                    for_update=True,
                )
            }
            participants[participant.id] = ParticipantState(id=participant.id, stats=stats)
        active_effects = tuple(
            ActiveEffectState(
                id=effect.id,
                source_participant_id=effect.source_participant_id,
                target_participant_id=effect.target_participant_id,
                effect_code=effect.effect_code,
                definition=effect.definition_snapshot,
                remaining_turns=effect.remaining_turns,
                applied_turn=effect.applied_turn,
            )
            for effect in await self.repositories.fight_active_effects.list_for_fight(fight.id, for_update=True)
        )
        return BattleState(
            active_participant_id=fight.active_participant_id,
            turn_number=fight.turn_number,
            rng_seed=fight.rng_seed,
            rng_counter=fight.rng_counter,
            participants=participants,
            active_effects=active_effects,
        )

    async def _resolve_timeout(self, fight: Fight) -> None:
        result = resolve_timeout(await self._engine_state(fight))
        await self._persist_result(fight, result)

    async def _persist_result(
        self,
        fight: Fight,
        result: EngineResult,
        *,
        fight_action: FightAction | None = None,
    ) -> list[FightEvent]:
        participants = {item.id: item for item in await self.repositories.fight_participants.list_for_fight(fight.id)}
        stat_rows = {
            (participant.id, stat.code): stat
            for participant in participants.values()
            for stat in await self.repositories.fight_participant_stats.list_for_participant(participant.id)
        }
        for key, value in result.stat_updates.items():
            await self.repositories.fight_participant_stats.set_current_value(stat_rows[key].id, value)
        for application in result.effect_applications:
            existing = await self.repositories.fight_active_effects.get_for_target_code(
                application.target_participant_id,
                application.definition['code'],
            )
            if existing is None:
                await self.repositories.fight_active_effects.create(
                    fight_id=fight.id,
                    source_participant_id=application.source_participant_id,
                    target_participant_id=application.target_participant_id,
                    effect_code=application.definition['code'],
                    definition_snapshot=application.definition,
                    remaining_turns=application.remaining_turns,
                    applied_turn=fight.turn_number,
                )
            else:
                await self.repositories.fight_active_effects.refresh(
                    existing.id,
                    remaining_turns=application.remaining_turns,
                    applied_turn=fight.turn_number,
                )
        for effect_id, remaining in result.effect_turn_updates.items():
            await self.repositories.fight_active_effects.set_remaining_turns(effect_id, remaining)
        for effect_id in result.expired_effect_ids:
            await self.repositories.fight_active_effects.delete(effect_id)

        event_rows = await self.repositories.fight_events.create_many(
            [
                {
                    'fight_id': fight.id,
                    'fight_action_id': fight_action.id if fight_action is not None else None,
                    'sequence_number': fight.next_event_sequence + offset,
                    'event_type': event.event_type,
                    'payload': event.payload,
                }
                for offset, event in enumerate(result.events)
            ],
        )
        values: dict[str, Any] = {
            'version': fight.version + 1,
            'rng_counter': result.rng_counter,
            'next_event_sequence': fight.next_event_sequence + len(result.events),
        }
        if result.winner_participant_id is not None:
            values.update(
                status=FightStatus.finished,
                winner_participant_id=result.winner_participant_id,
                finish_reason='defeated',
                active_participant_id=None,
            )
        else:
            values.update(
                status=FightStatus.in_progress,
                turn_number=fight.turn_number + 1,
                active_participant_id=result.next_active_participant_id,
                turn_deadline_at=datetime.now(UTC) + self.turn_duration,
            )
        await self.repositories.fights.update_state(fight.id, **values)
        if result.winner_participant_id is not None:
            await self._finalize_battle(fight.id)
        return event_rows

    async def _finalize_battle(self, fight_id: UUID) -> None:
        fight = await self.repositories.fights.get_by_id(fight_id)
        if fight is None:
            raise RuntimeError('Fight disappeared during finalization')
        state = await self._engine_state_for_finished(fight)
        participants = await self.repositories.fight_participants.list_for_fight(fight_id)
        for participant in participants:
            if participant.source_type != 'character':
                continue
            persistent_stats = await self.repositories.character_stats.list_for_character(
                participant.source_id,
                for_update=True,
            )
            definitions = {
                definition.id: definition
                for definition in [
                    await self.repositories.stat_definitions.get_by_id(item.stat_definition_id)
                    for item in persistent_stats
                ]
                if definition is not None
            }
            health_row = next(
                item for item in persistent_stats if definitions[item.stat_definition_id].code == 'health'
            )
            values = effective_stats(state, participant.id)
            await self.repositories.character_stats.set_value(
                health_row.id,
                calculate_carried_health(
                    health_before_battle=participant.health_before_battle,
                    max_health_before_battle=participant.max_health_before_battle,
                    battle_health=values['health'],
                    effective_battle_max_health=values['max_health'],
                ),
            )
        await self.repositories.fight_participants.deactivate_for_fight(fight_id)

    async def _engine_state_for_finished(self, fight: Fight) -> BattleState:
        participants = await self.repositories.fight_participants.list_for_fight(fight.id)
        if not participants:
            raise RuntimeError('Finished fight has no participants')
        original_active = fight.active_participant_id
        fight.active_participant_id = original_active or participants[0].id
        try:
            return await self._engine_state(fight)
        finally:
            fight.active_participant_id = original_active

    async def _state_response(
        self,
        fight: Fight,
        requester: FightParticipants,
        events_after: int,
    ) -> FightStateResponse:
        participants = await self.repositories.fight_participants.list_for_fight(fight.id)
        state = (
            await self._engine_state_for_finished(fight)
            if fight.active_participant_id is None
            else await self._engine_state(fight)
        )
        effects = await self.repositories.fight_active_effects.list_for_fight(fight.id)
        responses: list[FightParticipantResponse] = []
        for participant in participants:
            computed = effective_stats(state, participant.id)
            stats = await self.repositories.fight_participant_stats.list_for_participant(participant.id)
            responses.append(
                FightParticipantResponse(
                    id=participant.id,
                    source_type=participant.source_type,
                    source_id=participant.source_id,
                    display_name=participant.display_name,
                    side=participant.side,
                    stats=[
                        FightParticipantStatResponse(
                            code=stat.code,
                            kind=stat.kind,
                            initial_value=stat.initial_value,
                            current_value=stat.current_value,
                            effective_value=computed[stat.code],
                        )
                        for stat in stats
                    ],
                    effects=[
                        FightActiveEffectResponse(
                            code=effect.effect_code,
                            image_url=effect.definition_snapshot.get('image_url'),
                            source_participant_id=effect.source_participant_id,
                            target_participant_id=effect.target_participant_id,
                            remaining_turns=effect.remaining_turns,
                        )
                        for effect in effects
                        if effect.target_participant_id == participant.id
                    ],
                ),
            )
        events = await self.repositories.fight_events.list_after(fight.id, events_after)
        actions = fight.content_snapshot['actions'].get(str(requester.source_id), {})
        return FightStateResponse(
            id=fight.id,
            status=fight.status,
            version=fight.version,
            turn_number=fight.turn_number,
            active_participant_id=fight.active_participant_id,
            turn_deadline_at=fight.turn_deadline_at,
            winner_participant_id=fight.winner_participant_id,
            finish_reason=fight.finish_reason,
            title=fight.title,
            participants=responses,
            available_actions=list(actions),
            events=[self._event_response(event) for event in events],
        )

    @staticmethod
    def _event_response(event: FightEvent) -> FightEventResponse:
        return FightEventResponse(
            sequence_number=event.sequence_number,
            event_type=event.event_type,
            payload=event.payload,
            created_at=event.created_at,
        )
