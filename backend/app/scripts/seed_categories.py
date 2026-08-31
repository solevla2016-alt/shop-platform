import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    async_sessionmaker,
)

from app.core.config import settings
from app.models.category import Category


engine = create_async_engine(
    settings.async_database_url,
    echo=False,
)

async_session = async_sessionmaker(
    engine,
    expire_on_commit=False,
)


CATEGORIES = [
    {
        "name": "Комнатные растения",
        "slug": "indoor",
        "description": (
            "Филодендроны, монстеры, фикусы и другие"
        ),
        "icon": "",
        "image_url": "/images/categories/indoor.jpg",
    },
    {
        "name": "Садовые цветы",
        "slug": "garden",
        "description": (
            "Розы, пионы, гортензии и сезонные цветы"
        ),
        "icon": "🌸",
        "image_url": "/images/categories/flowering.jpg",
    },
    {
        "name": "Кустарники",
        "slug": "shrub",
        "description": (
            "Декоративные кустарники для сада "
            "и живой изгороди"
        ),
        "icon": "🌳",
        "image_url": None,
    },
    {
        "name": "Деревья",
        "slug": "tree",
        "description": (
            "Плодовые и декоративные деревья "
            "для участка"
        ),
        "icon": "🌲",
        "image_url": None,
    },
    {
        "name": "Суккуленты",
        "slug": "succulent",
        "description": (
            "Кактусы и суккуленты для дома и офиса"
        ),
        "icon": "🌵",
        "image_url": (
            "/images/categories/succulents.jpg"
        ),
    },
    {
        "name": "Другое",
        "slug": "other",
        "description": (
            "Аксессуары, удобрения, горшки и прочее"
        ),
        "icon": "🌿",
        "image_url": None,
    },
]


async def seed_categories():
    """Add default categories to database."""
    async with async_session() as session:
        for cat_data in CATEGORIES:
            result = await session.execute(
                select(Category).where(
                    Category.slug == cat_data["slug"]
                )
            )

            existing = result.scalar_one_or_none()

            if existing is None:
                category = Category(**cat_data)

                session.add(category)

                print(
                    f"✅ Создана категория: "
                    f"{cat_data['name']}"
                )
            else:
                print(
                    f"ℹ️ Категория уже существует: "
                    f"{cat_data['name']}"
                )

        await session.commit()

        print(
            "\n🎉 Категории успешно добавлены!"
        )

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed_categories())