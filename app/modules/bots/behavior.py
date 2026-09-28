from typing import Any


def choose_action(actions: dict[str, Any], priority: list[str]) -> str:
    """Choose the first available action; future tactics belong here."""
    for code in priority:
        if code in actions:
            return code
    raise ValueError('Bot has no available actions')
