from enum import StrEnum


class TargetPolicy(StrEnum):
    SELF = 'self'
    ENEMY = 'enemy'


class EffectDuration(StrEnum):
    INSTANT = 'instant'
    TURNS = 'turns'


class StackingPolicy(StrEnum):
    REFRESH = 'refresh'


class RuleKind(StrEnum):
    RESOURCE_DELTA = 'resource_delta'
    STAT_MODIFIER = 'stat_modifier'


class RuleOperation(StrEnum):
    ADD = 'add'
    MULTIPLY = 'multiply'
    OVERRIDE = 'override'
