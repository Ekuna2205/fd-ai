"""ai_models.preprocessing: how a registered model expects its input (crop mode, margin)

Revision ID: 0003
Revises: 0002
"""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("ai_models", sa.Column("preprocessing", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("ai_models") as batch:
        batch.drop_column("preprocessing")
