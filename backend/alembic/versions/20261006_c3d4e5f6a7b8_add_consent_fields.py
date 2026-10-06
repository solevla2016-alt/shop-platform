"""Add oferta and personal data consent fields to users."""
from alembic import op
import sqlalchemy as sa

revision = "c3d4e5f6a7b8"
down_revision = "b2c3d4e5f6a7"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "oferta_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "consent_pd_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "consent_pd_ip",
            sa.String(length=45),
            nullable=True,
        ),
    )

def downgrade() -> None:
    op.drop_column("users", "consent_pd_ip")
    op.drop_column("users", "consent_pd_at")
    op.drop_column("users", "oferta_at")
