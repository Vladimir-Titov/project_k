from sqlalchemy import CheckConstraint, Enum, UniqueConstraint
from sqlalchemy.orm import configure_mappers

from app.enums.actions import ActionsType
from app.models import (
    Account,
    Actions,
    Character,
    CharacteristicsActions,
    FightActions,
    FightParticipants,
)


def test_model_relationships_are_configured() -> None:
    configure_mappers()

    assert set(Account.__mapper__.relationships.keys()) == {'character'}
    assert {'account', 'fight_participations'} <= set(Character.__mapper__.relationships.keys())
    assert {
        'fight',
        'action',
        'initiator_participant',
        'target_participant',
    } <= set(FightActions.__mapper__.relationships.keys())


def test_character_account_is_a_unique_uuid_foreign_key() -> None:
    account_id = Character.__table__.c.account_id

    assert account_id.type.python_type is not str
    assert account_id.unique
    assert next(iter(account_id.foreign_keys)).target_fullname == 'frontiers.account.id'


def test_characteristics_actions_has_unique_pair() -> None:
    constraints = CharacteristicsActions.__table__.constraints

    assert any(
        isinstance(constraint, UniqueConstraint)
        and {column.name for column in constraint.columns} == {'characteristic_id', 'action_id'}
        for constraint in constraints
    )


def test_fight_participant_requires_exactly_one_actor() -> None:
    constraints = FightParticipants.__table__.constraints

    assert any(
        isinstance(constraint, CheckConstraint) and constraint.name == 'ck_fight_participant_exactly_one_actor'
        for constraint in constraints
    )


def test_action_column_uses_action_type_enum() -> None:
    action_type = Actions.__table__.c.type.type

    assert isinstance(action_type, Enum)
    assert action_type.enums == [item.value for item in ActionsType]
