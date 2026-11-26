"""Remember one prepared harness submission until its result is recorded."""
import sqlalchemy as sa
from alembic import op

revision = "046_harness_pending_turn"
down_revision = "045_block_close_score"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("harness_chats", sa.Column("pending_turn", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("harness_chats", "pending_turn")
