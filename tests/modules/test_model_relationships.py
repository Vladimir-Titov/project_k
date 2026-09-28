from sqlalchemy import UniqueConstraint
from sqlalchemy.orm import configure_mappers

from app.modules.auth.models import Account, Session
from app.modules.battles.models import Fight, FightParticipants
from app.modules.bots.models import BotTemplateAction, BotTemplateStat
from app.modules.characters.models import Character


def test_model_relationships_are_configured() -> None:
    configure_mappers()

    assert set(Account.__mapper__.relationships.keys()) == {'character', 'sessions'}
    assert set(Character.__mapper__.relationships.keys()) == {'account', 'character_class', 'location'}
    assert set(Fight.__mapper__.relationships.keys()) == {'active_participant', 'winner_participant'}
    assert set(FightParticipants.__mapper__.relationships.keys()) == {'fight', 'bot_template'}
    assert set(BotTemplateAction.__mapper__.relationships.keys()) == {'bot_template', 'action_definition'}
    assert set(BotTemplateStat.__mapper__.relationships.keys()) == {'bot_template', 'stat_definition'}


def test_character_account_is_a_unique_uuid_foreign_key() -> None:
    account_id = Character.__table__.c.account_id
    assert account_id.type.python_type is not str
    assert account_id.unique
    assert next(iter(account_id.foreign_keys)).target_fullname == 'auth.users.id'


def test_auth_models_use_auth_schema_and_session_constraints() -> None:
    assert Account.__table__.fullname == 'auth.users'
    assert Session.__table__.fullname == 'auth.sessions'
    assert Session.__table__.c.refresh_token_hash.unique
    assert next(iter(Session.__table__.c.active_character_id.foreign_keys)).target_fullname == 'frontiers.characters.id'


def test_fight_participant_has_unique_source_per_fight() -> None:
    assert any(
        isinstance(constraint, UniqueConstraint)
        and {column.name for column in constraint.columns} == {'fight_id', 'source_type', 'source_id'}
        for constraint in FightParticipants.__table__.constraints
    )
    assert not FightParticipants.__table__.c.source_id.nullable
    assert any(
        index.name == 'uq_active_fight_participant_source' and index.unique
        for index in FightParticipants.__table__.indexes
    )
