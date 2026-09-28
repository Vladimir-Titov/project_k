from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any
from uuid import UUID

from app.modules.content.enums import EffectDuration, RuleKind, RuleOperation
from app.modules.content.expressions import RandomSource, evaluate_expression
from app.modules.stats.enums import StatKind


class InvalidBattleStateError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class StatState:
    code: str
    kind: StatKind
    current_value: Decimal
    min_value: Decimal | None = None
    max_value: Decimal | None = None
    max_stat_code: str | None = None


@dataclass(frozen=True, slots=True)
class ParticipantState:
    id: UUID
    stats: dict[str, StatState]


@dataclass(frozen=True, slots=True)
class ActiveEffectState:
    id: UUID
    source_participant_id: UUID
    target_participant_id: UUID
    effect_code: str
    definition: dict[str, Any]
    remaining_turns: int
    applied_turn: int


@dataclass(frozen=True, slots=True)
class BattleState:
    active_participant_id: UUID
    turn_number: int
    rng_seed: int
    rng_counter: int
    participants: dict[UUID, ParticipantState]
    active_effects: tuple[ActiveEffectState, ...]


@dataclass(frozen=True, slots=True)
class EffectApplication:
    source_participant_id: UUID
    target_participant_id: UUID
    definition: dict[str, Any]
    remaining_turns: int


@dataclass(frozen=True, slots=True)
class DomainEvent:
    event_type: str
    payload: dict[str, Any]


@dataclass(slots=True)
class EngineResult:
    stat_updates: dict[tuple[UUID, str], Decimal] = field(default_factory=dict)
    effect_applications: list[EffectApplication] = field(default_factory=list)
    effect_turn_updates: dict[UUID, int] = field(default_factory=dict)
    expired_effect_ids: set[UUID] = field(default_factory=set)
    events: list[DomainEvent] = field(default_factory=list)
    next_active_participant_id: UUID | None = None
    rng_counter: int = 0
    winner_participant_id: UUID | None = None
    loser_participant_id: UUID | None = None


def _clamp(value: Decimal, stat: StatState, values: dict[str, Decimal]) -> Decimal:
    if stat.min_value is not None:
        value = max(value, stat.min_value)
    if stat.max_value is not None:
        value = min(value, stat.max_value)
    if stat.max_stat_code is not None:
        value = min(value, values[stat.max_stat_code])
    return value


def effective_stats(state: BattleState, participant_id: UUID) -> dict[str, Decimal]:
    participant = state.participants[participant_id]
    values = {code: stat.current_value for code, stat in participant.stats.items()}
    rules: list[tuple[int, ActiveEffectState, dict[str, Any]]] = []
    for effect in state.active_effects:
        if effect.target_participant_id != participant_id:
            continue
        for rule in effect.definition['rules']:
            if rule['kind'] == RuleKind.STAT_MODIFIER:
                rules.append((rule['priority'], effect, rule))
    random_source = RandomSource(state.rng_seed, state.rng_counter)
    for _, effect, rule in sorted(rules, key=lambda item: item[0]):
        source_values = {
            code: stat.current_value for code, stat in state.participants[effect.source_participant_id].stats.items()
        }
        modifier = evaluate_expression(
            rule['evaluator_type'],
            rule['expression'],
            source=source_values,
            target=values,
            random_source=random_source,
        )
        code = rule['stat_code']
        operation = RuleOperation(rule['operation'])
        if operation == RuleOperation.ADD:
            values[code] += modifier
        elif operation == RuleOperation.MULTIPLY:
            values[code] *= modifier
        else:
            values[code] = modifier
        values[code] = _clamp(values[code], participant.stats[code], values)
    return values


def _current_values(state: BattleState, result: EngineResult, participant_id: UUID) -> dict[str, Decimal]:
    values = effective_stats(state, participant_id)
    for (updated_participant_id, code), value in result.stat_updates.items():
        if updated_participant_id == participant_id:
            values[code] = value
    return values


def _apply_resource_rules(
    state: BattleState,
    result: EngineResult,
    source_id: UUID,
    target_id: UUID,
    definition: dict[str, Any],
    random_source: RandomSource,
) -> None:
    for rule in definition['rules']:
        if rule['kind'] != RuleKind.RESOURCE_DELTA:
            continue
        source_values = _current_values(state, result, source_id)
        target_values = _current_values(state, result, target_id)
        draws_before = len(random_source.draws)
        value = evaluate_expression(
            rule['evaluator_type'],
            rule['expression'],
            source=source_values,
            target=target_values,
            random_source=random_source,
        )
        code = rule['stat_code']
        previous = target_values[code]
        operation = RuleOperation(rule['operation'])
        if operation == RuleOperation.ADD:
            current = previous + value
        elif operation == RuleOperation.MULTIPLY:
            current = previous * value
        else:
            current = value
        current = _clamp(current, state.participants[target_id].stats[code], target_values)
        result.stat_updates[(target_id, code)] = current
        result.events.append(
            DomainEvent(
                'stat.changed',
                {
                    'participant_id': str(target_id),
                    'stat_code': code,
                    'previous_value': str(previous),
                    'current_value': str(current),
                    'delta': str(current - previous),
                    'random_values': random_source.draws[draws_before:],
                },
            ),
        )


def _end_actor_turn(
    state: BattleState,
    result: EngineResult,
    actor_id: UUID,
    random_source: RandomSource,
) -> None:
    for effect in state.active_effects:
        if effect.target_participant_id != actor_id or effect.applied_turn >= state.turn_number:
            continue
        if any(
            application.target_participant_id == actor_id and application.definition['code'] == effect.effect_code
            for application in result.effect_applications
        ):
            continue
        _apply_resource_rules(state, result, effect.source_participant_id, actor_id, effect.definition, random_source)
        remaining = effect.remaining_turns - 1
        if remaining <= 0:
            result.expired_effect_ids.add(effect.id)
            result.events.append(
                DomainEvent(
                    'effect.expired',
                    {'participant_id': str(actor_id), 'effect_code': effect.effect_code},
                ),
            )
        else:
            result.effect_turn_updates[effect.id] = remaining


def resolve_action(
    state: BattleState,
    *,
    action_code: str,
    action_definition: dict[str, Any],
    initiator_participant_id: UUID,
    target_participant_id: UUID,
) -> EngineResult:
    if initiator_participant_id != state.active_participant_id:
        raise InvalidBattleStateError('not_your_turn')
    if target_participant_id not in state.participants:
        raise InvalidBattleStateError('invalid_target')

    result = EngineResult(rng_counter=state.rng_counter)
    random_source = RandomSource(state.rng_seed, state.rng_counter)
    result.events.append(
        DomainEvent(
            'action.performed',
            {
                'action_code': action_code,
                'initiator_participant_id': str(initiator_participant_id),
                'target_participant_id': str(target_participant_id),
            },
        ),
    )
    for link in action_definition['effects']:
        resolved_target_id = initiator_participant_id if link['target_selector'] == 'self' else target_participant_id
        definition = link['effect']
        if definition['duration'] == EffectDuration.TURNS:
            result.effect_applications.append(
                EffectApplication(
                    source_participant_id=initiator_participant_id,
                    target_participant_id=resolved_target_id,
                    definition=definition,
                    remaining_turns=definition['duration_turns'],
                ),
            )
            result.events.append(
                DomainEvent(
                    'effect.applied',
                    {
                        'source_participant_id': str(initiator_participant_id),
                        'target_participant_id': str(resolved_target_id),
                        'effect_code': definition['code'],
                        'remaining_turns': definition['duration_turns'],
                    },
                ),
            )
            continue

        _apply_resource_rules(state, result, initiator_participant_id, resolved_target_id, definition, random_source)
    _end_actor_turn(state, result, initiator_participant_id, random_source)
    result.rng_counter = random_source.counter
    _finish_or_advance_turn(state, result, initiator_participant_id)
    return result


def _finish_or_advance_turn(state: BattleState, result: EngineResult, actor_id: UUID) -> None:
    for participant_id in state.participants:
        health = _current_values(state, result, participant_id).get('health')
        if health is not None and health <= 0:
            result.loser_participant_id = participant_id
            result.winner_participant_id = next(item for item in state.participants if item != participant_id)
            result.events.append(
                DomainEvent(
                    'battle.finished',
                    {
                        'winner_participant_id': str(result.winner_participant_id),
                        'loser_participant_id': str(participant_id),
                        'finish_reason': 'defeated',
                    },
                ),
            )
            return

    result.next_active_participant_id = next(
        participant_id for participant_id in state.participants if participant_id != actor_id
    )
    result.events.append(
        DomainEvent(
            'turn.started',
            {
                'participant_id': str(result.next_active_participant_id),
                'turn_number': state.turn_number + 1,
            },
        ),
    )


def resolve_timeout(state: BattleState) -> EngineResult:
    result = EngineResult(rng_counter=state.rng_counter)
    actor_id = state.active_participant_id
    result.events.append(
        DomainEvent(
            'turn.timed_out',
            {'participant_id': str(actor_id), 'turn_number': state.turn_number},
        ),
    )
    random_source = RandomSource(state.rng_seed, state.rng_counter)
    _end_actor_turn(state, result, actor_id, random_source)
    result.rng_counter = random_source.counter
    _finish_or_advance_turn(state, result, actor_id)
    return result
