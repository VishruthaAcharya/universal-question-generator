from alembic import op
import sqlalchemy as sa
revision="0001_initial"
down_revision=None
branch_labels=None
depends_on=None

def upgrade():
    op.create_table("question_sets",
        sa.Column("id",sa.String(36),primary_key=True),
        sa.Column("name",sa.String(255),nullable=False),
        sa.Column("subject",sa.String(255),nullable=False,server_default=""),
        sa.Column("source_file",sa.String(500),nullable=False,server_default=""),
        sa.Column("generation_mode",sa.String(50),nullable=False,server_default="CET_MCQ"),
        sa.Column("created_at",sa.DateTime(),nullable=False))
    op.create_table("questions",
        sa.Column("id",sa.String(36),primary_key=True),
        sa.Column("question_set_id",sa.String(36),sa.ForeignKey("question_sets.id",ondelete="CASCADE"),nullable=False),
        sa.Column("question",sa.Text(),nullable=False),
        sa.Column("topic",sa.String(255),nullable=False,server_default=""),
        sa.Column("subtopic",sa.String(255),nullable=False,server_default=""),
        sa.Column("answer_1",sa.Text(),nullable=False), sa.Column("answer_2",sa.Text(),nullable=False),
        sa.Column("answer_3",sa.Text(),nullable=False), sa.Column("answer_4",sa.Text(),nullable=False),
        sa.Column("difficulty",sa.String(20),nullable=False),
        sa.Column("correct_answer",sa.Text(),nullable=False),
        sa.Column("score",sa.Integer(),nullable=False,server_default="1"),
        sa.Column("source_page",sa.Integer()), sa.Column("status",sa.String(20),nullable=False,server_default="GENERATED"),
        sa.Column("created_at",sa.DateTime(),nullable=False), sa.Column("updated_at",sa.DateTime(),nullable=False))
    op.create_table("templates",
        sa.Column("id",sa.String(36),primary_key=True),
        sa.Column("name",sa.String(255),nullable=False),
        sa.Column("columns",sa.JSON(),nullable=False),
        sa.Column("created_at",sa.DateTime(),nullable=False))

def downgrade():
    op.drop_table("questions"); op.drop_table("templates"); op.drop_table("question_sets")
