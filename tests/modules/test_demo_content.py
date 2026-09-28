import os
from collections import Counter
from dataclasses import replace
from decimal import Decimal
from uuid import UUID

import pytest

from app.container import Repositories
from app.core.config import get_db_config
from app.lifespans.db import create_db_pool
from app.modules.battles.engine import ActiveEffectState, effective_stats, resolve_action, resolve_timeout
from seed_content import ROOT, load_catalog, seed_catalog
from tests.modules.battles.test_service import ATTACKER_ID, TARGET_ID, state

CATALOG = load_catalog(ROOT / 'content/skills.json', ROOT / 'output/skill-icons/webp-256')


@pytest.mark.parametrize('skill', CATALOG['skills'], ids=lambda skill: skill['code'])
def test_every_demo_skill_executes_with_existing_stats(skill):
    battle = state()
    # Leave room for healing so every skill has an observable effect.
    actor = battle.participants[ATTACKER_ID]
    battle.participants[ATTACKER_ID] = replace(
        actor,
        stats={
            **actor.stats,
            'health': replace(actor.stats['health'], current_value=Decimal(50)),
        },
    )
    definition = {
        'effects': [
            {
                'target_selector': effect['target_selector'],
                'effect': {
                    'code': f'{skill["code"]}_{index}',
                    'duration': 'instant' if effect['duration_turns'] is None else 'turns',
                    'duration_turns': effect['duration_turns'],
                    'rules': [
                        {**rule, 'evaluator_type': 'expression_v1', 'priority': index}
                        for index, rule in enumerate(effect['rules'])
                    ],
                },
            }
            for index, effect in enumerate(skill['effects'])
        ],
    }
    result = resolve_action(
        battle,
        action_code=skill['code'],
        action_definition=definition,
        initiator_participant_id=ATTACKER_ID,
        target_participant_id=ATTACKER_ID if skill['target_policy'] == 'self' else TARGET_ID,
    )
    assert result.stat_updates or result.effect_applications
    for index, application in enumerate(result.effect_applications):
        effect = ActiveEffectState(
            id=UUID(int=index + 10),
            source_participant_id=application.source_participant_id,
            target_participant_id=application.target_participant_id,
            effect_code=application.definition['code'],
            definition=application.definition,
            remaining_turns=application.remaining_turns,
            applied_turn=1,
        )
        next_turn = replace(
            battle,
            active_effects=(effect,),
            turn_number=2,
            active_participant_id=effect.target_participant_id,
        )
        stats = effective_stats(next_turn, effect.target_participant_id)
        assert all(value >= 0 for value in stats.values())
        tick = resolve_timeout(next_turn)
        assert effect.id in tick.effect_turn_updates or effect.id in tick.expired_effect_ids


@pytest.mark.skipif(os.getenv('RUN_CONTENT_INTEGRATION') != '1', reason='Requires local PostgreSQL')
@pytest.mark.asyncio
async def test_seed_is_idempotent_and_assigns_skills_to_existing_characters():
    pool = await create_db_pool(get_db_config())
    try:
        async with pool.acquire() as connection:
            transaction = connection.transaction()
            await transaction.start()
            try:
                repositories = Repositories(pool, connection)
                urls = {skill['code']: f'https://example.test/{skill["icon"]}' for skill in CATALOG['skills']}
                before_stats = await connection.fetch('SELECT * FROM frontiers.character_stats ORDER BY id')
                await seed_catalog(repositories, CATALOG, urls)
                first_ids = {
                    action.code: action.id
                    for action in await repositories.action_definitions.search(code_in=list(urls))
                }
                first_rules = await repositories.effect_rules.count()
                await seed_catalog(repositories, CATALOG, urls)
                actions = await repositories.action_definitions.search(code_in=list(urls))
                assert {action.code: action.id for action in actions} == first_ids
                assert len(actions) == len(urls)
                assert await repositories.effect_rules.count() == first_rules
                assert before_stats == await connection.fetch('SELECT * FROM frontiers.character_stats ORDER BY id')
                expected = Counter(skill['class_code'] for skill in CATALOG['skills'])
                for character_class in await repositories.character_classes.list_playable():
                    links = await repositories.class_actions.list_for_class(character_class.id)
                    owned_ids = {
                        first_ids[s['code']] for s in CATALOG['skills'] if s['class_code'] == character_class.code
                    }
                    assert len(owned_ids) == expected[character_class.code]
                    assert owned_ids <= {link.action_definition_id for link in links}
                    for character in await repositories.characters.search(
                        class_id=character_class.id, is_archived=False
                    ):
                        links = await repositories.character_actions.list_for_character(character.id)
                        assigned = {link.action_definition_id for link in links}
                        assert owned_ids <= assigned
                        assert not (set(first_ids.values()) - owned_ids) & assigned
            finally:
                await transaction.rollback()
    finally:
        await pool.close()
