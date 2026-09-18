"""Add shipping status to orders and product sku to order items."""
from alembic import op
import sqlalchemy as sa

revision = "a1b2c3d4e5f6"
down_revision = "0d3a1e55f2c1"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column("orders", sa.Column("shipping_status", sa.String(20), nullable=True))
    op.add_column("order_items", sa.Column("product_sku", sa.String(50), nullable=True))

def downgrade() -> None:
    op.drop_column("order_items", "product_sku")
    op.drop_column("orders", "shipping_status")