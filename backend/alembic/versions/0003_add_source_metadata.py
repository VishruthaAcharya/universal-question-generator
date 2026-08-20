"""add source metadata json

Revision ID: 0003_add_source_metadata
Revises: 0002_redesign
Create Date: 2026-08-20 12:30:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = '0003_add_source_metadata'
down_revision = '0002_redesign'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('questions', sa.Column('source_metadata_json', sa.JSON(), nullable=True))

def downgrade():
    op.drop_column('questions', 'source_metadata_json')
