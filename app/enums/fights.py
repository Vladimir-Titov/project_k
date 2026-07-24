from enum import StrEnum


class FightStatus(StrEnum):
    started = 'started'
    finished = 'finished'
    interrupted = 'interrupted'
    in_progress = 'in_progress'
    canceled = 'canceled'
