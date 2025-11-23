"""Initial schema with vendors, naics, contacts, and api_cache

Revision ID: 6b4ee64b05c3
Revises: 
Create Date: 2025-11-22 22:03:39.269153

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6b4ee64b05c3'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'vendors',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('source', sa.String(length=50), nullable=False),
        sa.Column('external_id', sa.String(length=255), nullable=False),
        sa.Column('uei', sa.String(length=50), nullable=True),
        sa.Column('duns', sa.String(length=50), nullable=True),
        sa.Column('cage_code', sa.String(length=20), nullable=True),
        sa.Column('legal_name', sa.String(length=500), nullable=False),
        sa.Column('dba_name', sa.String(length=500), nullable=True),
        sa.Column('website', sa.String(length=500), nullable=True),
        sa.Column('country', sa.String(length=2), nullable=True),
        sa.Column('state', sa.String(length=50), nullable=True),
        sa.Column('city', sa.String(length=200), nullable=True),
        sa.Column('address', sa.Text(), nullable=True),
        sa.Column('postal_code', sa.String(length=20), nullable=True),
        sa.Column('business_types', sa.JSON(), nullable=True),
        sa.Column('is_small_business', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('is_woman_owned', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('is_veteran_owned', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('is_minority_owned', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('is_8a', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('is_hubzone', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('metadata_json', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('last_enriched_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('source', 'external_id', name='uq_vendor_source_external_id')
    )
    op.create_index('ix_vendors_source', 'vendors', ['source'])
    op.create_index('ix_vendors_uei', 'vendors', ['uei'])
    op.create_index('ix_vendors_duns', 'vendors', ['duns'])
    op.create_index('ix_vendors_cage_code', 'vendors', ['cage_code'])
    op.create_index('ix_vendors_legal_name', 'vendors', ['legal_name'])
    op.create_index('ix_vendors_website', 'vendors', ['website'])
    op.create_index('ix_vendor_location', 'vendors', ['country', 'state', 'city'])
    op.create_index('ix_vendor_certifications', 'vendors', ['is_small_business', 'is_woman_owned', 'is_veteran_owned'])

    op.create_table(
        'vendor_naics',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('vendor_id', sa.Integer(), nullable=False),
        sa.Column('naics_code', sa.String(length=10), nullable=False),
        sa.Column('naics_description', sa.String(length=500), nullable=True),
        sa.Column('is_primary', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['vendor_id'], ['vendors.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('vendor_id', 'naics_code', name='uq_vendor_naics')
    )
    op.create_index('ix_vendor_naics_vendor_id', 'vendor_naics', ['vendor_id'])
    op.create_index('ix_vendor_naics_naics_code', 'vendor_naics', ['naics_code'])
    op.create_index('ix_vendor_naics_lookup', 'vendor_naics', ['naics_code', 'vendor_id'])

    op.create_table(
        'vendor_contacts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('vendor_id', sa.Integer(), nullable=False),
        sa.Column('source', sa.String(length=50), nullable=False),
        sa.Column('first_name', sa.String(length=200), nullable=True),
        sa.Column('last_name', sa.String(length=200), nullable=True),
        sa.Column('title', sa.String(length=200), nullable=True),
        sa.Column('email', sa.String(length=255), nullable=True),
        sa.Column('phone', sa.String(length=50), nullable=True),
        sa.Column('is_verified', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('confidence_score', sa.Integer(), nullable=True),
        sa.Column('metadata_json', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['vendor_id'], ['vendors.id'], ondelete='CASCADE')
    )
    op.create_index('ix_vendor_contacts_vendor_id', 'vendor_contacts', ['vendor_id'])
    op.create_index('ix_vendor_contacts_email', 'vendor_contacts', ['email'])
    op.create_index('ix_vendor_contact_email', 'vendor_contacts', ['vendor_id', 'email'])

    op.create_table(
        'api_cache',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('source', sa.String(length=50), nullable=False),
        sa.Column('cache_key', sa.String(length=500), nullable=False),
        sa.Column('response_data', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('hit_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_accessed_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('source', 'cache_key', name='uq_api_cache_source_key')
    )
    op.create_index('ix_api_cache_source', 'api_cache', ['source'])
    op.create_index('ix_api_cache_created_at', 'api_cache', ['created_at'])
    op.create_index('ix_api_cache_expires_at', 'api_cache', ['expires_at'])
    op.create_index('ix_api_cache_expiry', 'api_cache', ['source', 'expires_at'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('api_cache')
    op.drop_table('vendor_contacts')
    op.drop_table('vendor_naics')
    op.drop_table('vendors')
