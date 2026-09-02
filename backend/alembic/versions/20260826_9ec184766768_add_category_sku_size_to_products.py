import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '9ec184766768'
down_revision = '0001'
branch_labels = None
depends_on = None

# Определяем ENUM тип вручную для PostgreSQL
productcategory_enum = postgresql.ENUM(
    'indoor', 'garden', 'shrub', 'tree', 'succulent', 'other',
    name='productcategory',
    create_type=False
)


def upgrade() -> None:
    # 1. Сначала создаем ENUM тип в БД (это решает твою ошибку!)
    productcategory_enum.create(op.get_bind(), checkfirst=True)

    # 2. Затем добавляем колонки
    op.add_column('products', sa.Column('category', productcategory_enum, nullable=False, server_default='other'))
    op.add_column('products', sa.Column('sku', sa.String(length=50), nullable=False))
    op.add_column('products', sa.Column('size', sa.String(length=50), nullable=True))

    # 3. Создаем индекс для sku
    op.create_index(op.f('ix_products_sku'), 'products', ['sku'], unique=True)


def downgrade() -> None:
    # 1. Удаляем индекс
    op.drop_index(op.f('ix_products_sku'), table_name='products')
    # 2. Удаляем колонки
    op.drop_column('products', 'size')
    op.drop_column('products', 'sku')
    op.drop_column('products', 'category')
    # 3. Удаляем ENUM тип
    productcategory_enum.drop(op.get_bind(), checkfirst=True)
