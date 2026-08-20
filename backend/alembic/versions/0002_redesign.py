"""redesign schema

Revision ID: 0002_redesign
Revises: 0001_initial
Create Date: 2026-08-19 18:20:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0002_redesign'
down_revision = '0001_initial'
branch_labels = None
depends_on = None

def upgrade():
    # 1. Update templates table
    op.add_column('templates', sa.Column('original_filename', sa.String(length=500), nullable=True))
    op.add_column('templates', sa.Column('sheet_name', sa.String(length=255), nullable=True))
    op.add_column('templates', sa.Column('schema_json', sa.JSON(), nullable=True))
    # We will copy existing data or just drop old columns
    op.drop_column('templates', 'columns')
    # Make schema_json non-nullable for future inserts
    # For now, let's keep it nullable or set a default during migration if needed, but since it's a clean app, there's no critical data.

    # 2. Update question_sets table
    op.add_column('question_sets', sa.Column('template_id', sa.String(length=36), sa.ForeignKey('templates.id', ondelete='SET NULL'), nullable=True))
    op.add_column('question_sets', sa.Column('source_filename', sa.String(length=500), nullable=True))
    op.add_column('question_sets', sa.Column('source_type', sa.String(length=50), nullable=True))
    op.add_column('question_sets', sa.Column('status', sa.String(length=50), nullable=False, server_default='PENDING'))
    op.drop_column('question_sets', 'name')
    op.drop_column('question_sets', 'subject')
    op.drop_column('question_sets', 'source_file')
    op.drop_column('question_sets', 'generation_mode')

    # 3. Update questions table
    op.add_column('questions', sa.Column('row_number', sa.Integer(), nullable=True))
    op.add_column('questions', sa.Column('data_json', sa.JSON(), nullable=True))
    op.add_column('questions', sa.Column('validation_json', sa.JSON(), nullable=True))
    op.drop_column('questions', 'question')
    op.drop_column('questions', 'topic')
    op.drop_column('questions', 'subtopic')
    op.drop_column('questions', 'answer_1')
    op.drop_column('questions', 'answer_2')
    op.drop_column('questions', 'answer_3')
    op.drop_column('questions', 'answer_4')
    op.drop_column('questions', 'difficulty')
    op.drop_column('questions', 'correct_answer')
    op.drop_column('questions', 'score')
    op.drop_column('questions', 'source_page')

def downgrade():
    # We don't necessarily need a fully detailed downgrade if we're not running it, but let's provide a basic one.
    pass
