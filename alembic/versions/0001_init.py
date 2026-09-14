"""Initial auth, dynamic content, characters, and PvP battle schema.

Revision ID: 0001
Revises:
"""

from collections.abc import Sequence
from uuid import UUID

import sqlalchemy as sa
from alembic import op

revision: str = '0001'
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NUMERIC = sa.Numeric(18, 4)


def uid(value: int) -> UUID:
    return UUID(int=value)


def base_columns() -> list[sa.Column]:
    return [
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('is_archived', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    ]


def create_content_tables() -> None:
    op.create_table(
        'stat_definitions',
        *base_columns(),
        sa.Column('code', sa.String(length=64), nullable=False),
        sa.Column('title', sa.String(length=128), nullable=False),
        sa.Column('description', sa.String(length=512), nullable=True),
        sa.Column('kind', sa.Enum('attribute', 'resource', name='stat_kind', native_enum=False), nullable=False),
        sa.Column('min_value', NUMERIC, nullable=True),
        sa.Column('max_value', NUMERIC, nullable=True),
        sa.Column('max_stat_definition_id', sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(['max_stat_definition_id'], ['frontiers.stat_definitions.id']),
        sa.PrimaryKeyConstraint('id'),
        schema='frontiers',
    )
    op.create_index('ix_frontiers_stat_definitions_code', 'stat_definitions', ['code'], unique=True, schema='frontiers')
    op.create_table(
        'action_definitions',
        *base_columns(),
        sa.Column('code', sa.String(length=64), nullable=False),
        sa.Column('title', sa.String(length=128), nullable=False),
        sa.Column('description', sa.String(length=512), nullable=True),
        sa.Column('target_policy', sa.Enum('self', 'enemy', name='target_policy', native_enum=False), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        schema='frontiers',
    )
    op.create_index(
        'ix_frontiers_action_definitions_code', 'action_definitions', ['code'], unique=True, schema='frontiers'
    )
    op.create_table(
        'effect_definitions',
        *base_columns(),
        sa.Column('code', sa.String(length=64), nullable=False),
        sa.Column('title', sa.String(length=128), nullable=False),
        sa.Column('description', sa.String(length=512), nullable=True),
        sa.Column('duration', sa.Enum('instant', 'turns', name='effect_duration', native_enum=False), nullable=False),
        sa.Column('duration_turns', sa.Integer(), nullable=True),
        sa.Column('stacking_policy', sa.Enum('refresh', name='stacking_policy', native_enum=False), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        schema='frontiers',
    )
    op.create_index(
        'ix_frontiers_effect_definitions_code', 'effect_definitions', ['code'], unique=True, schema='frontiers'
    )
    op.create_table(
        'effect_rules',
        *base_columns(),
        sa.Column('effect_definition_id', sa.Uuid(), nullable=False),
        sa.Column('stat_definition_id', sa.Uuid(), nullable=False),
        sa.Column(
            'kind',
            sa.Enum('resource_delta', 'stat_modifier', name='effect_rule_kind', native_enum=False),
            nullable=False,
        ),
        sa.Column(
            'operation',
            sa.Enum('add', 'multiply', 'override', name='effect_rule_operation', native_enum=False),
            nullable=False,
        ),
        sa.Column('evaluator_type', sa.String(length=32), nullable=False),
        sa.Column('expression', sa.Text(), nullable=False),
        sa.Column('priority', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['effect_definition_id'], ['frontiers.effect_definitions.id']),
        sa.ForeignKeyConstraint(['stat_definition_id'], ['frontiers.stat_definitions.id']),
        sa.PrimaryKeyConstraint('id'),
        schema='frontiers',
    )
    op.create_index(
        'ix_frontiers_effect_rules_effect_definition_id', 'effect_rules', ['effect_definition_id'], schema='frontiers'
    )
    op.create_index(
        'ix_frontiers_effect_rules_stat_definition_id', 'effect_rules', ['stat_definition_id'], schema='frontiers'
    )
    op.create_table(
        'action_effects',
        *base_columns(),
        sa.Column('action_definition_id', sa.Uuid(), nullable=False),
        sa.Column('effect_definition_id', sa.Uuid(), nullable=False),
        sa.Column(
            'target_selector',
            sa.Enum('self', 'enemy', name='effect_target_selector', native_enum=False),
            nullable=False,
        ),
        sa.Column('order', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['action_definition_id'], ['frontiers.action_definitions.id']),
        sa.ForeignKeyConstraint(['effect_definition_id'], ['frontiers.effect_definitions.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('action_definition_id', 'effect_definition_id', name='uq_action_effect_pair'),
        schema='frontiers',
    )
    op.create_index(
        'ix_frontiers_action_effects_action_definition_id',
        'action_effects',
        ['action_definition_id'],
        schema='frontiers',
    )
    op.create_index(
        'ix_frontiers_action_effects_effect_definition_id',
        'action_effects',
        ['effect_definition_id'],
        schema='frontiers',
    )


def create_auth_and_character_tables() -> None:
    op.create_table(
        'users',
        *base_columns(),
        sa.Column('login', sa.String(length=64), nullable=False),
        sa.Column('password_hash', sa.String(length=512), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        schema='auth',
    )
    op.create_index('ix_auth_users_login', 'users', ['login'], unique=True, schema='auth')
    op.create_table(
        'character_classes',
        *base_columns(),
        sa.Column('code', sa.String(length=64), nullable=False),
        sa.Column('title', sa.String(length=128), nullable=False),
        sa.Column('description', sa.String(length=512), nullable=True),
        sa.Column('is_playable', sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        schema='frontiers',
    )
    op.create_index(
        'ix_frontiers_character_classes_code', 'character_classes', ['code'], unique=True, schema='frontiers'
    )
    op.create_table(
        'class_stats',
        *base_columns(),
        sa.Column('class_id', sa.Uuid(), nullable=False),
        sa.Column('stat_definition_id', sa.Uuid(), nullable=False),
        sa.Column('value', NUMERIC, nullable=False),
        sa.ForeignKeyConstraint(['class_id'], ['frontiers.character_classes.id']),
        sa.ForeignKeyConstraint(['stat_definition_id'], ['frontiers.stat_definitions.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('class_id', 'stat_definition_id', name='uq_class_stat_pair'),
        schema='frontiers',
    )
    op.create_index('ix_frontiers_class_stats_class_id', 'class_stats', ['class_id'], schema='frontiers')
    op.create_index(
        'ix_frontiers_class_stats_stat_definition_id', 'class_stats', ['stat_definition_id'], schema='frontiers'
    )
    op.create_table(
        'class_actions',
        *base_columns(),
        sa.Column('class_id', sa.Uuid(), nullable=False),
        sa.Column('action_definition_id', sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(['class_id'], ['frontiers.character_classes.id']),
        sa.ForeignKeyConstraint(['action_definition_id'], ['frontiers.action_definitions.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('class_id', 'action_definition_id', name='uq_class_action_pair'),
        schema='frontiers',
    )
    op.create_index('ix_frontiers_class_actions_class_id', 'class_actions', ['class_id'], schema='frontiers')
    op.create_index(
        'ix_frontiers_class_actions_action_definition_id', 'class_actions', ['action_definition_id'], schema='frontiers'
    )
    op.create_table(
        'characters',
        *base_columns(),
        sa.Column('account_id', sa.Uuid(), nullable=False),
        sa.Column('nickname', sa.String(length=64), nullable=False),
        sa.Column('class_id', sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(['account_id'], ['auth.users.id']),
        sa.ForeignKeyConstraint(['class_id'], ['frontiers.character_classes.id']),
        sa.PrimaryKeyConstraint('id'),
        schema='frontiers',
    )
    op.create_index('ix_frontiers_characters_account_id', 'characters', ['account_id'], unique=True, schema='frontiers')
    op.create_index('ix_frontiers_characters_nickname', 'characters', ['nickname'], unique=True, schema='frontiers')
    op.create_index('ix_frontiers_characters_class_id', 'characters', ['class_id'], schema='frontiers')
    op.create_table(
        'character_stats',
        *base_columns(),
        sa.Column('character_id', sa.Uuid(), nullable=False),
        sa.Column('stat_definition_id', sa.Uuid(), nullable=False),
        sa.Column('value', NUMERIC, nullable=False),
        sa.ForeignKeyConstraint(['character_id'], ['frontiers.characters.id']),
        sa.ForeignKeyConstraint(['stat_definition_id'], ['frontiers.stat_definitions.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('character_id', 'stat_definition_id', name='uq_character_stat_pair'),
        schema='frontiers',
    )
    op.create_index(
        'ix_frontiers_character_stats_character_id', 'character_stats', ['character_id'], schema='frontiers'
    )
    op.create_index(
        'ix_frontiers_character_stats_stat_definition_id', 'character_stats', ['stat_definition_id'], schema='frontiers'
    )
    op.create_table(
        'character_actions',
        *base_columns(),
        sa.Column('character_id', sa.Uuid(), nullable=False),
        sa.Column('action_definition_id', sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(['character_id'], ['frontiers.characters.id']),
        sa.ForeignKeyConstraint(['action_definition_id'], ['frontiers.action_definitions.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('character_id', 'action_definition_id', name='uq_character_action_pair'),
        schema='frontiers',
    )
    op.create_index(
        'ix_frontiers_character_actions_character_id', 'character_actions', ['character_id'], schema='frontiers'
    )
    op.create_index(
        'ix_frontiers_character_actions_action_definition_id',
        'character_actions',
        ['action_definition_id'],
        schema='frontiers',
    )
    op.create_table(
        'sessions',
        *base_columns(),
        sa.Column('account_id', sa.Uuid(), nullable=False),
        sa.Column('active_character_id', sa.Uuid(), nullable=True),
        sa.Column('refresh_token_hash', sa.String(length=64), nullable=False),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['account_id'], ['auth.users.id']),
        sa.ForeignKeyConstraint(['active_character_id'], ['frontiers.characters.id']),
        sa.PrimaryKeyConstraint('id'),
        schema='auth',
    )
    op.create_index('ix_auth_sessions_account_id', 'sessions', ['account_id'], schema='auth')
    op.create_index('ix_auth_sessions_active_character_id', 'sessions', ['active_character_id'], schema='auth')
    op.create_index(
        'ix_auth_sessions_refresh_token_hash', 'sessions', ['refresh_token_hash'], unique=True, schema='auth'
    )


def create_battle_tables() -> None:
    op.create_table(
        'fights',
        *base_columns(),
        sa.Column(
            'status',
            sa.Enum(
                'started', 'finished', 'interrupted', 'in_progress', 'canceled', name='fight_status', native_enum=False
            ),
            nullable=False,
        ),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('turn_number', sa.Integer(), nullable=False),
        sa.Column('active_participant_id', sa.Uuid(), nullable=True),
        sa.Column('turn_deadline_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('winner_participant_id', sa.Uuid(), nullable=True),
        sa.Column('finish_reason', sa.String(length=64), nullable=True),
        sa.Column('rng_seed', sa.BigInteger(), nullable=False),
        sa.Column('rng_counter', sa.Integer(), nullable=False),
        sa.Column('next_event_sequence', sa.Integer(), nullable=False),
        sa.Column('content_snapshot', sa.JSON(), nullable=False),
        sa.Column('title', sa.String(length=256), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        schema='frontiers',
    )
    op.create_table(
        'fight_participants',
        *base_columns(),
        sa.Column('fight_id', sa.Uuid(), nullable=False),
        sa.Column('source_type', sa.String(length=32), nullable=False),
        sa.Column('source_id', sa.Uuid(), nullable=False),
        sa.Column('display_name', sa.String(length=128), nullable=False),
        sa.Column('side', sa.Enum('team_a', 'team_b', name='fight_side', native_enum=False), nullable=False),
        sa.Column('turn_order', sa.Integer(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('health_before_battle', NUMERIC, nullable=False),
        sa.Column('max_health_before_battle', NUMERIC, nullable=False),
        sa.ForeignKeyConstraint(['fight_id'], ['frontiers.fights.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('fight_id', 'source_type', 'source_id', name='uq_fight_participant_source'),
        schema='frontiers',
    )
    op.create_index('ix_frontiers_fight_participants_fight_id', 'fight_participants', ['fight_id'], schema='frontiers')
    op.create_index(
        'ix_frontiers_fight_participants_source_id', 'fight_participants', ['source_id'], schema='frontiers'
    )
    op.create_index(
        'uq_active_fight_participant_source',
        'fight_participants',
        ['source_type', 'source_id'],
        unique=True,
        schema='frontiers',
        postgresql_where=sa.text('is_active = true'),
    )
    op.create_table(
        'fight_participant_stats',
        *base_columns(),
        sa.Column('participant_id', sa.Uuid(), nullable=False),
        sa.Column('stat_definition_id', sa.Uuid(), nullable=False),
        sa.Column('code', sa.String(length=64), nullable=False),
        sa.Column('kind', sa.Enum('attribute', 'resource', name='fight_stat_kind', native_enum=False), nullable=False),
        sa.Column('max_stat_code', sa.String(length=64), nullable=True),
        sa.Column('min_value', NUMERIC, nullable=True),
        sa.Column('max_value', NUMERIC, nullable=True),
        sa.Column('initial_value', NUMERIC, nullable=False),
        sa.Column('current_value', NUMERIC, nullable=False),
        sa.ForeignKeyConstraint(['participant_id'], ['frontiers.fight_participants.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('participant_id', 'code', name='uq_fight_participant_stat_code'),
        schema='frontiers',
    )
    op.create_index(
        'ix_frontiers_fight_participant_stats_participant_id',
        'fight_participant_stats',
        ['participant_id'],
        schema='frontiers',
    )
    op.create_table(
        'fight_active_effects',
        *base_columns(),
        sa.Column('fight_id', sa.Uuid(), nullable=False),
        sa.Column('source_participant_id', sa.Uuid(), nullable=False),
        sa.Column('target_participant_id', sa.Uuid(), nullable=False),
        sa.Column('effect_code', sa.String(length=64), nullable=False),
        sa.Column('definition_snapshot', sa.JSON(), nullable=False),
        sa.Column('remaining_turns', sa.Integer(), nullable=False),
        sa.Column('applied_turn', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['fight_id'], ['frontiers.fights.id']),
        sa.ForeignKeyConstraint(['source_participant_id'], ['frontiers.fight_participants.id']),
        sa.ForeignKeyConstraint(['target_participant_id'], ['frontiers.fight_participants.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('target_participant_id', 'effect_code', name='uq_fight_active_effect_target_code'),
        schema='frontiers',
    )
    op.create_index(
        'ix_frontiers_fight_active_effects_fight_id', 'fight_active_effects', ['fight_id'], schema='frontiers'
    )
    op.create_index(
        'ix_frontiers_fight_active_effects_target_participant_id',
        'fight_active_effects',
        ['target_participant_id'],
        schema='frontiers',
    )
    op.create_table(
        'fight_actions',
        *base_columns(),
        sa.Column('fight_id', sa.Uuid(), nullable=False),
        sa.Column('initiator_participant_id', sa.Uuid(), nullable=False),
        sa.Column('target_participant_id', sa.Uuid(), nullable=True),
        sa.Column('idempotency_key', sa.Uuid(), nullable=False),
        sa.Column('action_code', sa.String(length=64), nullable=False),
        sa.Column('turn_number', sa.Integer(), nullable=False),
        sa.Column('result', sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(['fight_id'], ['frontiers.fights.id']),
        sa.ForeignKeyConstraint(['initiator_participant_id'], ['frontiers.fight_participants.id']),
        sa.ForeignKeyConstraint(['target_participant_id'], ['frontiers.fight_participants.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'fight_id', 'initiator_participant_id', 'idempotency_key', name='uq_fight_action_idempotency'
        ),
        schema='frontiers',
    )
    op.create_index('ix_frontiers_fight_actions_fight_id', 'fight_actions', ['fight_id'], schema='frontiers')
    op.create_table(
        'fight_events',
        *base_columns(),
        sa.Column('fight_id', sa.Uuid(), nullable=False),
        sa.Column('fight_action_id', sa.Uuid(), nullable=True),
        sa.Column('sequence_number', sa.Integer(), nullable=False),
        sa.Column('event_type', sa.String(length=64), nullable=False),
        sa.Column('payload', sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(['fight_id'], ['frontiers.fights.id']),
        sa.ForeignKeyConstraint(['fight_action_id'], ['frontiers.fight_actions.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('fight_id', 'sequence_number', name='uq_fight_event_sequence'),
        schema='frontiers',
    )
    op.create_index('ix_frontiers_fight_events_fight_id', 'fight_events', ['fight_id'], schema='frontiers')


def seed_content() -> None:
    stats = sa.table(
        'stat_definitions',
        sa.column('id'),
        sa.column('code'),
        sa.column('title'),
        sa.column('kind'),
        sa.column('min_value'),
        sa.column('max_stat_definition_id'),
        schema='frontiers',
    )
    max_health, health, attack, defense = uid(101), uid(102), uid(103), uid(104)
    op.bulk_insert(
        stats,
        [
            {
                'id': max_health,
                'code': 'max_health',
                'title': 'Максимальное здоровье',
                'kind': 'attribute',
                'min_value': 1,
                'max_stat_definition_id': None,
            },
            {
                'id': health,
                'code': 'health',
                'title': 'Здоровье',
                'kind': 'resource',
                'min_value': 0,
                'max_stat_definition_id': max_health,
            },
            {
                'id': attack,
                'code': 'attack',
                'title': 'Атака',
                'kind': 'attribute',
                'min_value': 0,
                'max_stat_definition_id': None,
            },
            {
                'id': defense,
                'code': 'defense',
                'title': 'Защита',
                'kind': 'attribute',
                'min_value': 0,
                'max_stat_definition_id': None,
            },
        ],
    )
    classes = sa.table(
        'character_classes',
        sa.column('id'),
        sa.column('code'),
        sa.column('title'),
        sa.column('is_playable'),
        schema='frontiers',
    )
    class_rows = [
        (uid(201), 'adventurer', 'Adventurer'),
        (uid(202), 'warrior', 'Warrior'),
        (uid(203), 'magician', 'Magician'),
    ]
    op.bulk_insert(
        classes,
        [{'id': class_id, 'code': code, 'title': title, 'is_playable': True} for class_id, code, title in class_rows],
    )
    class_stats = sa.table(
        'class_stats',
        sa.column('id'),
        sa.column('class_id'),
        sa.column('stat_definition_id'),
        sa.column('value'),
        schema='frontiers',
    )
    values = {uid(201): (100, 12, 4), uid(202): (120, 10, 7), uid(203): (80, 16, 2)}
    rows = []
    next_id = 210
    for class_id, (hp, attack_value, defense_value) in values.items():
        for stat_id, value in ((max_health, hp), (health, hp), (attack, attack_value), (defense, defense_value)):
            rows.append({'id': uid(next_id), 'class_id': class_id, 'stat_definition_id': stat_id, 'value': value})
            next_id += 1
    op.bulk_insert(class_stats, rows)
    actions = sa.table(
        'action_definitions',
        sa.column('id'),
        sa.column('code'),
        sa.column('title'),
        sa.column('target_policy'),
        sa.column('is_active'),
        schema='frontiers',
    )
    basic_attack, rage = uid(301), uid(302)
    op.bulk_insert(
        actions,
        [
            {
                'id': basic_attack,
                'code': 'basic_attack',
                'title': 'Базовая атака',
                'target_policy': 'enemy',
                'is_active': True,
            },
            {'id': rage, 'code': 'rage', 'title': 'Ярость', 'target_policy': 'self', 'is_active': True},
        ],
    )
    effects = sa.table(
        'effect_definitions',
        sa.column('id'),
        sa.column('code'),
        sa.column('title'),
        sa.column('duration'),
        sa.column('duration_turns'),
        sa.column('stacking_policy'),
        sa.column('is_active'),
        schema='frontiers',
    )
    damage_effect, rage_effect = uid(401), uid(402)
    op.bulk_insert(
        effects,
        [
            {
                'id': damage_effect,
                'code': 'basic_damage',
                'title': 'Урон базовой атаки',
                'duration': 'instant',
                'duration_turns': None,
                'stacking_policy': 'refresh',
                'is_active': True,
            },
            {
                'id': rage_effect,
                'code': 'rage_attack_bonus',
                'title': 'Бонус атаки ярости',
                'duration': 'turns',
                'duration_turns': 2,
                'stacking_policy': 'refresh',
                'is_active': True,
            },
        ],
    )
    rules = sa.table(
        'effect_rules',
        sa.column('id'),
        sa.column('effect_definition_id'),
        sa.column('stat_definition_id'),
        sa.column('kind'),
        sa.column('operation'),
        sa.column('evaluator_type'),
        sa.column('expression'),
        sa.column('priority'),
        schema='frontiers',
    )
    op.bulk_insert(
        rules,
        [
            {
                'id': uid(501),
                'effect_definition_id': damage_effect,
                'stat_definition_id': health,
                'kind': 'resource_delta',
                'operation': 'add',
                'evaluator_type': 'expression_v1',
                'expression': '-max(1, round_half_up(max(1, source.attack - target.defense) * random_int(90, 110) / 100))',
                'priority': 0,
            },
            {
                'id': uid(502),
                'effect_definition_id': rage_effect,
                'stat_definition_id': attack,
                'kind': 'stat_modifier',
                'operation': 'multiply',
                'evaluator_type': 'expression_v1',
                'expression': '1.25',
                'priority': 0,
            },
        ],
    )
    action_effects = sa.table(
        'action_effects',
        sa.column('id'),
        sa.column('action_definition_id'),
        sa.column('effect_definition_id'),
        sa.column('target_selector'),
        sa.column('order'),
        schema='frontiers',
    )
    op.bulk_insert(
        action_effects,
        [
            {
                'id': uid(601),
                'action_definition_id': basic_attack,
                'effect_definition_id': damage_effect,
                'target_selector': 'enemy',
                'order': 0,
            },
            {
                'id': uid(602),
                'action_definition_id': rage,
                'effect_definition_id': rage_effect,
                'target_selector': 'self',
                'order': 0,
            },
        ],
    )
    class_actions = sa.table(
        'class_actions', sa.column('id'), sa.column('class_id'), sa.column('action_definition_id'), schema='frontiers'
    )
    rows = []
    next_id = 610
    for class_id, _, _ in class_rows:
        for action_id in (basic_attack, rage):
            rows.append({'id': uid(next_id), 'class_id': class_id, 'action_definition_id': action_id})
            next_id += 1
    op.bulk_insert(class_actions, rows)


def upgrade() -> None:
    op.execute('CREATE SCHEMA IF NOT EXISTS "auth"')
    op.execute('CREATE SCHEMA IF NOT EXISTS "frontiers"')
    create_content_tables()
    create_auth_and_character_tables()
    create_battle_tables()
    seed_content()


def downgrade() -> None:
    op.execute('DROP SCHEMA "auth" CASCADE')
    op.execute('DROP SCHEMA "frontiers" CASCADE')
