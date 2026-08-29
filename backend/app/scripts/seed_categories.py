import asyncio

from app.db.session import async_session
from app.models.category import Category

CATEGORIES = [
    {"name": "Комнатные растения", "slug": "indoor", "description": "Филодендроны, монстеры, фикусы и другие", "icon": "🪴", "image_url": "https://images.unsplash.com/photo-1614594965117-6c2bd6b537d8?w=400&h=300&fit=crop"},
    {"name": "Садовые цветы", "slug": "garden", "description": "Розы, пионы, гортензии и сезонные цветы", "icon": "🌸", "image_url": "https://images.unsplash.com/photo-1490750967868-88aa4486c946?w=400&h=300&fit=crop"},
    {"name": "Кустарники", "slug": "shrub", "description": "Декоративные кустарники для сада и живой изгороди", "icon": "🌳", "image_url": "https://images.unsplash.com/photo-1466692476868-aef1dfb1e735?w=400&h=300&fit=crop"},
    {"name": "Деревья", "slug": "tree", "description": "Плодовые и декоративные деревья для участка", "icon": "🌲", "image_url": "https://images.unsplash.com/photo-1542273917363-3b1817f69a2d?w=400&h=300&fit=crop"},
    {"name": "Суккуленты", "slug": "succulent", "description": "Кактусы и суккуленты для дома и офиса", "icon": "🌵", "image_url": "https://images.unsplash.com/photo-1459411621453-7b03977f4bfc?w=400&h=300&fit=crop"},
    {"name": "Другое", "slug": "other", "description": "Аксессуары, удобрения, горшки и прочее", "icon": "🌿", "image_url": "https://images.unsplash.com/photo-1463936575829-25148e12107a?w=400&h=300&fit=crop"},
]


async def seed_categories():
    async with async_session() as session:
        for cat_data in CATEGORIES:
            existing = await session.execute(
                session.query(Category).filter(Category.slug == cat_data["slug"])
            )
            if not existing.scalar_one_or_none():
                category = Category(**cat_data)
                session.add(category)
                print(f"Создана категория: {cat_data['name']}")
        await session.commit()
    print("Категории успешно добавлены!")


if __name__ == "__main__":
    asyncio.run(seed_categories())
