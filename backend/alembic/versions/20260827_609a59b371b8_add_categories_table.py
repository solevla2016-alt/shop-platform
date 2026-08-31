"""Add categories and migrate products to category foreign keys."""
from alembic import op
import sqlalchemy as sa

revision = "609a59b371b8"
down_revision = "9ec184766768"
branch_labels = None
depends_on = None

CATEGORIES = [
    ("Комнатные растения", "indoor", "Филодендроны, монстеры, фикусы и другие", "🌿"),
    ("Садовые цветы", "garden", "Розы, пионы, гортензии и сезонные цветы", "🌸"),
    ("Кустарники", "shrub", "Декоративные кустарники для сада и живой изгороди", "🌳"),
    ("Деревья", "tree", "Плодовые и декоративные деревья для участка", "🌲"),
    ("Суккуленты", "succulent", "Кактусы и суккуленты для дома и офиса", "🌵"),
    ("Другое", "other", "Аксессуары, удобрения, горшки и прочее", "🌿"),
]

def upgrade() -> None:
    op.create_table(
        "categories",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
        sa.Column("slug", sa.String(100), nullable=False, unique=True),
        sa.Column("description", sa.Text()),
        sa.Column("image_url", sa.String(500)),
        sa.Column("icon", sa.String(10)),
    )
    op.create_index("ix_categories_id", "categories", ["id"])
    op.create_index("ix_categories_slug", "categories", ["slug"], unique=True)
    op.bulk_insert(
        sa.table("categories", sa.column("name", sa.String), sa.column("slug", sa.String), sa.column("description", sa.Text), sa.column("icon", sa.String)),
        [{"name": n, "slug": s, "description": d, "icon": i} for n, s, d, i in CATEGORIES],
    )
    op.drop_index("ix_auth_tokens_id", table_name="auth_tokens")
    op.drop_index("ix_auth_tokens_token", table_name="auth_tokens")
    op.drop_table("auth_tokens")
    op.add_column("products", sa.Column("category_id", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_products_category_id", "products", "categories", ["category_id"], ["id"])
    op.execute(sa.text("UPDATE products SET category_id = (SELECT id FROM categories WHERE slug = products.category) WHERE category_id IS NULL"))
    op.alter_column("products", "category_id", nullable=False)
    op.create_index("ix_products_category_id", "products", ["category_id"])
    op.alter_column("refresh_tokens", "jti", existing_type=sa.String(255), type_=sa.String(36))
    op.drop_constraint("refresh_tokens_jti_key", "refresh_tokens", type_="unique")
    op.create_index("ix_refresh_tokens_jti", "refresh_tokens", ["jti"], unique=True)
    op.alter_column("users", "is_admin", existing_type=sa.Boolean(), server_default=None)

def downgrade() -> None:
    op.alter_column("users", "is_admin", existing_type=sa.Boolean(), server_default=sa.text("false"))
    op.drop_index("ix_refresh_tokens_jti", table_name="refresh_tokens")
    op.create_unique_constraint("refresh_tokens_jti_key", "refresh_tokens", ["jti"])
    op.alter_column("refresh_tokens", "jti", existing_type=sa.String(36), type_=sa.String(255))
    op.drop_index("ix_products_category_id", table_name="products")
    op.drop_constraint("fk_products_category_id", "products", type_="foreignkey")
    op.drop_column("products", "category_id")
    op.create_table("auth_tokens", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("user_id", sa.Integer(), nullable=False), sa.Column("token", sa.String(500), nullable=False), sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"))
    op.create_index("ix_auth_tokens_id", "auth_tokens", ["id"])
    op.create_index("ix_auth_tokens_token", "auth_tokens", ["token"], unique=True)
    op.drop_index("ix_categories_slug", table_name="categories")
    op.drop_index("ix_categories_id", table_name="categories")
    op.drop_table("categories")
