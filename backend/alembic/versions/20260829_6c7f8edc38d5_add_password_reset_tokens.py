"""Add one-time password reset tokens."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
revision = "6c7f8edc38d5"
down_revision = "609a59b371b8"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        "password_reset_tokens",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("token_hash", sa.String(255), nullable=False),
        sa.Column("is_used", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_password_reset_tokens_id", "password_reset_tokens", ["id"])
    op.create_index("ix_password_reset_tokens_token_hash", "password_reset_tokens", ["token_hash"], unique=True)
    op.create_index("ix_password_reset_tokens_user_id", "password_reset_tokens", ["user_id"])
    op.drop_column("products", "category")
    op.execute("DROP TYPE IF EXISTS productcategory")

def downgrade() -> None:
    productcategory = postgresql.ENUM("indoor", "garden", "shrub", "tree", "succulent", "other", name="productcategory")
    productcategory.create(op.get_bind(), checkfirst=True)
    op.add_column("products", sa.Column("category", productcategory, nullable=False, server_default="other"))
    op.drop_index("ix_password_reset_tokens_user_id", table_name="password_reset_tokens")
    op.drop_index("ix_password_reset_tokens_token_hash", table_name="password_reset_tokens")
    op.drop_index("ix_password_reset_tokens_id", table_name="password_reset_tokens")
    op.drop_table("password_reset_tokens")
