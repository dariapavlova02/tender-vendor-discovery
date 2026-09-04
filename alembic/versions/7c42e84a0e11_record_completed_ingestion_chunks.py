"""Record completed Canada CSV chunks for repeat-import protection.

Revision ID: 7c42e84a0e11
Revises: d8dfe206ccc1
"""
from alembic import op
import sqlalchemy as sa

revision = "7c42e84a0e11"
down_revision = "d8dfe206ccc1"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "ingestion_chunks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source", sa.String(50), nullable=False),
        sa.Column("digest", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("source", "digest", name="uq_ingestion_chunk"),
    )


def downgrade():
    op.drop_table("ingestion_chunks")
