"""Load the trial class skills and their WebP icons into the configured DB and S3."""

import argparse
import asyncio
import hashlib
import json
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import update
from sqlalchemy.dialects.postgresql import insert

from app.container import Repositories
from app.core.config import get_db_config, get_storage_config
from app.core.db.entity_repository import EntityRepository
from app.core.files.images import inspect_image
from app.core.files.repository import FileRepository
from app.core.files.s3 import S3FileRepository
from app.lifespans.db import close_db_pool, create_db_pool
from app.modules.content.enums import RuleKind, RuleOperation, TargetPolicy
from app.modules.content.expressions import validate_expression

ROOT = Path(__file__).resolve().parent
STAT_CODES = {'health', 'max_health', 'attack', 'defense'}


def load_catalog(path: Path, icons_dir: Path) -> dict[str, Any]:
    catalog = json.loads(path.read_text())
    class_codes = {item['code'] for item in catalog['classes']}
    codes: set[str] = set()
    for skill in catalog['skills']:
        if skill['code'] in codes or skill['class_code'] not in class_codes:
            raise ValueError(f'Invalid or duplicate skill: {skill["code"]}')
        codes.add(skill['code'])
        TargetPolicy(skill['target_policy'])
        if inspect_image((icons_dir / skill['icon']).read_bytes())[0] != 'webp':
            raise ValueError(f'Expected WebP: {skill["icon"]}')
        if not skill['effects']:
            raise ValueError(f'Skill has no effects: {skill["code"]}')
        for effect in skill['effects']:
            TargetPolicy(effect['target_selector'])
            turns = effect['duration_turns']
            if turns is not None and (not isinstance(turns, int) or turns < 1):
                raise ValueError(f'Invalid duration: {skill["code"]}')
            for rule in effect['rules']:
                RuleOperation(rule['operation'])
                kind = RuleKind(rule['kind'])
                if rule['stat_code'] not in STAT_CODES or (kind == RuleKind.STAT_MODIFIER and turns is None):
                    raise ValueError(f'Invalid rule: {skill["code"]}')
                validate_expression(
                    'expression_v1',
                    rule['expression'],
                    available_stat_codes=STAT_CODES,
                    allow_random=kind != RuleKind.STAT_MODIFIER,
                )
    return catalog


async def upload_icons(catalog: dict[str, Any], icons_dir: Path, files: FileRepository) -> dict[str, str]:
    urls = {}
    for skill in catalog['skills']:
        path = Path(skill['icon'])
        data = (icons_dir / path).read_bytes()
        # The same asset keeps its URL on reruns; changed bytes get a new URL.
        digest = hashlib.sha256(data).hexdigest()
        key = f'images/skills/{path.parent}/{path.stem}-{digest}.webp'
        await files.put(key, data, 'image/webp')
        urls[skill['code']] = files.public_url(key)
    return urls


async def upsert(repository: EntityRepository, values: dict[str, Any], conflict: list[str]) -> UUID:
    record = repository.entity.model_validate(values).model_dump()
    query = insert(repository.table).values(record)
    query = query.on_conflict_do_update(
        index_elements=conflict,
        set_={name: query.excluded[name] for name in record if name not in {'id', 'created_at'}},
    ).returning(repository.table.c.id)
    return await repository.fetchval(query)


async def seed_catalog(repositories: Repositories, catalog: dict[str, Any], urls: dict[str, str]) -> None:
    classes = {item.code: item for item in await repositories.character_classes.list_playable()}
    stats = {item.code: item.id for item in await repositories.stat_definitions.search(is_archived=False)}
    if {item['code'] for item in catalog['classes']} - classes.keys() or STAT_CODES - stats.keys():
        raise ValueError('Required classes/stats are missing. Run uv run alembic upgrade head first.')
    for item in catalog['classes']:
        await repositories.character_classes.execute(
            update(repositories.character_classes.table)
            .where(repositories.character_classes.table.c.id == classes[item['code']].id)
            .values(title=item['title'], description=item['description']),
        )

    characters = await repositories.characters.search(
        class_id_in=[classes[item['code']].id for item in catalog['classes']],
        is_archived=False,
    )
    legacy = await repositories.action_definitions.search(code_in=['basic_attack', 'rage'])
    for repository, owner_field, owner_ids in (
        (repositories.class_actions, 'class_id', [classes[item['code']].id for item in catalog['classes']]),
        (repositories.character_actions, 'character_id', [item.id for item in characters]),
    ):
        await repository.execute(
            update(repository.table)
            .where(
                repository.table.c[owner_field].in_(owner_ids),
                repository.table.c.action_definition_id.in_([item.id for item in legacy]),
            )
            .values(is_archived=True),
        )

    for skill in catalog['skills']:
        image_url = urls[skill['code']]
        action_id = await upsert(
            repositories.action_definitions,
            {
                'code': skill['code'],
                'title': skill['title'],
                'description': skill['description'],
                'target_policy': skill['target_policy'],
                'image_url': image_url,
            },
            ['code'],
        )
        await repositories.action_effects.execute(
            update(repositories.action_effects.table)
            .where(repositories.action_effects.table.c.action_definition_id == action_id)
            .values(is_archived=True),
        )
        for order, effect in enumerate(skill['effects']):
            effect_code = f'{skill["code"]}_{order + 1}'
            effect_id = await upsert(
                repositories.effect_definitions,
                {
                    'code': effect_code,
                    'title': effect['title'],
                    'description': skill['description'],
                    'image_url': image_url,
                    'duration': 'instant' if effect['duration_turns'] is None else 'turns',
                    'duration_turns': effect['duration_turns'],
                },
                ['code'],
            )
            await repositories.effect_rules.execute(
                update(repositories.effect_rules.table)
                .where(repositories.effect_rules.table.c.effect_definition_id == effect_id)
                .values(is_archived=True),
            )
            for priority, rule in enumerate(effect['rules']):
                await upsert(
                    repositories.effect_rules,
                    {
                        'id': uuid5(NAMESPACE_URL, f'project-k/demo-skills/{effect_code}/{priority}'),
                        'effect_definition_id': effect_id,
                        'stat_definition_id': stats[rule['stat_code']],
                        'kind': rule['kind'],
                        'operation': rule['operation'],
                        'expression': rule['expression'],
                        'evaluator_type': 'expression_v1',
                        'priority': priority,
                    },
                    ['id'],
                )
            await upsert(
                repositories.action_effects,
                {
                    'action_definition_id': action_id,
                    'effect_definition_id': effect_id,
                    'target_selector': effect['target_selector'],
                    'order': order,
                },
                ['action_definition_id', 'effect_definition_id'],
            )
        class_id = classes[skill['class_code']].id
        await upsert(
            repositories.class_actions,
            {
                'class_id': class_id,
                'action_definition_id': action_id,
            },
            ['class_id', 'action_definition_id'],
        )
        for character in characters:
            if character.class_id == class_id:
                await upsert(
                    repositories.character_actions,
                    {
                        'character_id': character.id,
                        'action_definition_id': action_id,
                    },
                    ['character_id', 'action_definition_id'],
                )


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--catalog', type=Path, default=ROOT / 'content/skills.json')
    parser.add_argument('--icons-dir', type=Path, default=ROOT / 'output/skill-icons/webp-256')
    parser.add_argument('--dry-run', action='store_true', help='Validate and show content without writing to DB or S3')
    args = parser.parse_args()
    catalog = load_catalog(args.catalog, args.icons_dir)
    for item in catalog['classes']:
        names = [skill['title'] for skill in catalog['skills'] if skill['class_code'] == item['code']]
        print(f'{item["title"]}: {", ".join(names)}')
    if args.dry_run:
        return
    config = get_storage_config()
    if not config.enabled:
        raise ValueError('Enable S3_ENABLED in .env before uploading icons.')
    files = S3FileRepository(config)
    try:
        if config.initialize_local_bucket:
            await files.initialize_local_bucket()
        urls = await upload_icons(catalog, args.icons_dir, files)
        db_config = get_db_config()
        pool = await create_db_pool(db_config)
        try:
            async with Repositories(pool).transaction() as repositories:
                await seed_catalog(repositories, catalog, urls)
        finally:
            await close_db_pool(pool, db_config.pool_close_timeout)
    finally:
        await files.close()
    print(f'Loaded {len(catalog["skills"])} skills and their images. Start a new battle to use them.')


if __name__ == '__main__':
    asyncio.run(main())
