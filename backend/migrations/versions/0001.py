# backend/migrations/versions/0001.py
# Comptes, sessions, cles de service, documents et journal
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import app.db

revision: str = '0001'
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('events',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('created_at', app.db.UTCDateTime(), nullable=False),
    sa.Column('level', sa.Enum('info', 'warning', 'error', name='eventlevel', native_enum=False, length=10), nullable=False),
    sa.Column('category', sa.Enum('indexation', 'authentification', 'comptes', 'cles', 'documents', 'api', 'systeme', name='eventcategory', native_enum=False, length=20), nullable=False),
    sa.Column('action', sa.String(length=50), nullable=False),
    sa.Column('message', sa.Text(), nullable=False),
    sa.Column('detail', sa.Text(), nullable=True),
    sa.Column('actor', sa.String(length=254), nullable=True),
    sa.Column('ip', sa.String(length=45), nullable=True),
    sa.Column('method', sa.String(length=10), nullable=True),
    sa.Column('path', sa.String(length=255), nullable=True),
    sa.Column('status_code', sa.Integer(), nullable=True),
    sa.Column('request_id', sa.String(length=64), nullable=True),
    sa.Column('document_id', sa.String(length=36), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('events', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_events_category'), ['category'], unique=False)
        batch_op.create_index(batch_op.f('ix_events_created_at'), ['created_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_events_document_id'), ['document_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_events_level'), ['level'], unique=False)
        batch_op.create_index(batch_op.f('ix_events_request_id'), ['request_id'], unique=False)

    op.create_table('users',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('email', sa.String(length=254), nullable=False),
    sa.Column('password_hash', sa.String(length=255), nullable=False),
    sa.Column('role', sa.Enum('admin', 'client', name='role', native_enum=False, length=10), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('failed_logins', sa.Integer(), nullable=False),
    sa.Column('locked_until', app.db.UTCDateTime(), nullable=True),
    sa.Column('last_login_at', app.db.UTCDateTime(), nullable=True),
    sa.Column('created_at', app.db.UTCDateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_users_email'), ['email'], unique=True)

    op.create_table('documents',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('filename', sa.String(length=255), nullable=False),
    sa.Column('title', sa.String(length=255), nullable=False),
    sa.Column('source', sa.String(length=255), nullable=False),
    sa.Column('version', sa.String(length=50), nullable=False),
    sa.Column('document_date', sa.Date(), nullable=False),
    sa.Column('sha256', sa.String(length=64), nullable=False),
    sa.Column('size', sa.Integer(), nullable=False),
    sa.Column('storage_path', sa.String(length=500), nullable=False),
    sa.Column('status', sa.Enum('pending', 'indexing', 'indexed', 'failed', 'deleting', name='documentstatus', native_enum=False, length=10), nullable=False),
    sa.Column('error', sa.Text(), nullable=True),
    sa.Column('chunks', sa.Integer(), nullable=True),
    sa.Column('ocr_pages', sa.Integer(), nullable=True),
    sa.Column('uploaded_by', sa.String(length=36), nullable=True),
    sa.Column('created_at', app.db.UTCDateTime(), nullable=False),
    sa.Column('updated_at', app.db.UTCDateTime(), nullable=False),
    sa.Column('indexed_at', app.db.UTCDateTime(), nullable=True),
    sa.ForeignKeyConstraint(['uploaded_by'], ['users.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('documents', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_documents_sha256'), ['sha256'], unique=False)

    op.create_table('refresh_tokens',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('user_id', sa.String(length=36), nullable=False),
    sa.Column('family_id', sa.String(length=36), nullable=False),
    sa.Column('token_hash', sa.String(length=64), nullable=False),
    sa.Column('session_expires_at', app.db.UTCDateTime(), nullable=False),
    sa.Column('revoked_at', app.db.UTCDateTime(), nullable=True),
    sa.Column('created_at', app.db.UTCDateTime(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('refresh_tokens', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_refresh_tokens_family_id'), ['family_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_refresh_tokens_token_hash'), ['token_hash'], unique=True)
        batch_op.create_index(batch_op.f('ix_refresh_tokens_user_id'), ['user_id'], unique=False)

    op.create_table('service_keys',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('prefix', sa.String(length=16), nullable=False),
    sa.Column('key_hash', sa.String(length=64), nullable=False),
    sa.Column('created_by', sa.String(length=36), nullable=True),
    sa.Column('created_at', app.db.UTCDateTime(), nullable=False),
    sa.Column('last_used_at', app.db.UTCDateTime(), nullable=True),
    sa.Column('revoked_at', app.db.UTCDateTime(), nullable=True),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('name')
    )
    with op.batch_alter_table('service_keys', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_service_keys_key_hash'), ['key_hash'], unique=True)



def downgrade() -> None:
    with op.batch_alter_table('service_keys', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_service_keys_key_hash'))

    op.drop_table('service_keys')
    with op.batch_alter_table('refresh_tokens', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_refresh_tokens_user_id'))
        batch_op.drop_index(batch_op.f('ix_refresh_tokens_token_hash'))
        batch_op.drop_index(batch_op.f('ix_refresh_tokens_family_id'))

    op.drop_table('refresh_tokens')
    with op.batch_alter_table('documents', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_documents_sha256'))

    op.drop_table('documents')
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_users_email'))

    op.drop_table('users')
    with op.batch_alter_table('events', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_events_request_id'))
        batch_op.drop_index(batch_op.f('ix_events_level'))
        batch_op.drop_index(batch_op.f('ix_events_document_id'))
        batch_op.drop_index(batch_op.f('ix_events_created_at'))
        batch_op.drop_index(batch_op.f('ix_events_category'))

    op.drop_table('events')
