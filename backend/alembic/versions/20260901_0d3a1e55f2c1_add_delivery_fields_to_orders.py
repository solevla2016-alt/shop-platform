"""Add delivery fields to orders."""
from alembic import op
import sqlalchemy as sa

revision = "0d3a1e55f2c1"
down_revision = "6c7f8edc38d5"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column("orders", sa.Column("delivery_method", sa.String(20), nullable=True))
    op.add_column("orders", sa.Column("delivery_cost", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("orders", sa.Column("delivery_address", sa.String(500), nullable=True))
    op.add_column("orders", sa.Column("recipient_name", sa.String(255), nullable=True))

def downgrade() -> None:
    op.drop_column("orders", "recipient_name")
    op.drop_column("orders", "delivery_address")
    op.drop_column("orders", "delivery_cost")
    op.drop_column("orders", "delivery_method")