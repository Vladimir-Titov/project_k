"""Battle-related enums."""

from enum import StrEnum


class FightStatus(StrEnum):
    started = 'started'
    finished = 'finished'
    interrupted = 'interrupted'
    in_progress = 'in_progress'
    canceled = 'canceled'


class FightSide(StrEnum):
    team_a = 'team_a'
    team_b = 'team_b'
