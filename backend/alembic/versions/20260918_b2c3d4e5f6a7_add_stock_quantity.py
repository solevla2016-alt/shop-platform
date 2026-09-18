"""Add stock quantity to products."""
from alembic import op
import sqlalchemy as sa

revision = "b2c3d4e5f6a7"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column(
        "products",
        sa.Column(
            "stock_quantity",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )

def downgrade() -> None:
    op.drop_column("products", "stock_quantity")