import os
from uuid import uuid7

import pytest

from app.container import Repositories
from app.core.config import get_db_config
from app.lifespans.db import create_db_pool
from app.modules.battles.service import FightService
from app.modules.characters.service import CharacterService
from app.modules.stats.enums import StatKind


@pytest.mark.skipif(os.getenv('RUN_BOT_INTEGRATION') != '1', reason='Requires local PostgreSQL')
@pytest.mark.asyncio
async def test_player_fight_with_bot_runs_both_turns() -> None:
    pool = await create_db_pool(get_db_config())
    try:
        async with pool.acquire() as connection:
            transaction = connection.transaction()
            await transaction.start()
            try:
                repositories = Repositories(pool, connection)
                account = await repositories.accounts.create(login=f'bot-test-{uuid7()}', password_hash='unused')
                character, _ = await CharacterService(repositories).create(
                    account_id=account.id,
                    nickname=f'Hunter-{uuid7()}',
                    class_code='adventurer',
                )
                basic_attack = (await repositories.action_definitions.search(code='basic_attack'))[0]
                known_actions = await repositories.character_actions.list_for_character(character.id)
                if basic_attack.id not in {link.action_definition_id for link in known_actions}:
                    await repositories.character_actions.create(
                        character_id=character.id,
                        action_definition_id=basic_attack.id,
                    )
                template = await repositories.bot_templates.create(
                    code=f'test_bot_{uuid7().hex}',
                    title='Test bot',
                    is_active=True,
                )
                for code, value in {'max_health': 65, 'health': 65, 'attack': 9, 'defense': 2}.items():
                    definition = (await repositories.stat_definitions.search(code=code))[0]
                    await repositories.bot_template_stats.create(
                        bot_template_id=template.id,
                        stat_definition_id=definition.id,
                        value=value,
                    )
                extra_stat = await repositories.stat_definitions.create(
                    code=f'bot_test_stat_{uuid7().hex}',
                    title='Bot test stat',
                    kind=StatKind.ATTRIBUTE,
                    min_value=0,
                )
                await repositories.bot_template_stats.create(
                    bot_template_id=template.id,
                    stat_definition_id=extra_stat.id,
                    value=15,
                )
                await repositories.bot_template_actions.create(
                    bot_template_id=template.id,
                    action_definition_id=basic_attack.id,
                    priority=0,
                )
                service = FightService(repositories)

                targets = await service.list_bot_targets(character.id)
                assert next(target.stats for target in targets if target.id == template.id) == {
                    'max_health': 65,
                    'health': 65,
                    'attack': 9,
                    'defense': 2,
                    extra_stat.code: 15,
                }

                fight = await service.create_bot_fight(attacker_id=character.id, bot_template_id=template.id)
                initial = await service.get_state(fight_id=fight.id, character_id=character.id)
                bot = next(participant for participant in initial.participants if participant.source_type == 'bot')
                assert bot.source_id != template.id
                assert initial.active_participant_id != bot.id
                assert any(stat.code == extra_stat.code for stat in bot.stats)

                response = await service.perform_action(
                    fight_id=fight.id,
                    character_id=character.id,
                    idempotency_key=uuid7(),
                    expected_version=initial.version,
                    action_code='basic_attack',
                    target_participant_id=bot.id,
                )
                assert response.version == initial.version + 2
                assert [event.event_type for event in response.events].count('action.performed') == 2
                current = await service.get_state(fight_id=fight.id, character_id=character.id)
                assert current.active_participant_id != bot.id
                assert current.turn_number == 3
            finally:
                await transaction.rollback()
    finally:
        await pool.close()
