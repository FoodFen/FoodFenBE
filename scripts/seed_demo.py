"""Fictional HCMC restaurants + dishes so the dish tab and admin screens have content.

    uv run python -m scripts.seed_demo [--remove] [--env-file .env.prod]
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

SUFFIX = "@foodfen.invalid"

# (name, address, lat, lng, hours, [(dish, price VND, serving_g, kcal, protein, carbs, fat, fiber)])
# kcal ~= 4*protein + 4*carbs + 9*fat, within 10%.
DEMO = [
    ("Bếp Ba Tèo (Demo)", "25 Nguyễn Thái Bình, Quận 1, TP.HCM", 10.7690, 106.6990, "6:00-21:00", [
        ("Gỏi cuốn tôm thịt (4 cuốn)", 40000, 320, 320, 22, 44, 6, 4),
        ("Bánh mì thịt", 25000, 250, 400, 18, 50, 14, 3),
        ("Phở bò tái", 60000, 500, 440, 32, 55, 10, 2),
        ("Bún bò Huế", 65000, 550, 520, 30, 62, 17, 3),
        ("Cơm chiên dương châu", 55000, 400, 680, 18, 90, 28, 3),
    ]),
    ("Cơm Tấm Cô Sáu (Demo)", "118 Võ Văn Tần, Quận 3, TP.HCM", 10.7760, 106.6870, "6:30-22:00", [
        ("Canh chua cá lóc", 50000, 400, 255, 26, 22, 7, 3),
        ("Salad ức gà", 60000, 300, 280, 35, 14, 9, 5),
        ("Cá kho tộ + cơm", 55000, 450, 525, 30, 70, 14, 2),
        ("Cơm tấm sườn nướng", 45000, 400, 630, 32, 75, 22, 2),
        ("Cơm tấm sườn bì chả", 55000, 450, 760, 38, 85, 30, 2),
    ]),
    ("Tiệm Bún Chả Hai Lúa (Demo)", "76 Xô Viết Nghệ Tĩnh, Bình Thạnh, TP.HCM", 10.8010, 106.7110, "10:00-20:00", [
        ("Gỏi ngó sen tôm thịt", 50000, 250, 250, 20, 22, 9, 4),
        ("Bánh mì ốp la", 25000, 220, 400, 16, 45, 17, 2),
        ("Hủ tiếu Nam Vang", 55000, 500, 500, 28, 65, 14, 2),
        ("Bún thịt nướng", 50000, 450, 575, 28, 75, 18, 4),
        ("Bún chả", 55000, 500, 615, 34, 70, 22, 3),
    ]),
]


async def run(session: AsyncSession, remove: bool = False) -> list[str]:
    from src.domain.entities.dish import Dish
    from src.domain.entities.restaurant import Restaurant
    from src.domain.entities.user import User
    from src.domain.enums import ReviewDecision
    from src.infrastructure.db.models.dish_model import DishORM
    from src.infrastructure.db.models.restaurant_model import RestaurantORM
    from src.infrastructure.db.models.user_model import UserORM
    from src.infrastructure.db.repositories.restaurant_repository import SQLAlchemyRestaurantRepository
    from src.infrastructure.db.repositories.user_repository import SQLAlchemyUserRepository

    if remove:
        demo = select(UserORM.id).where(UserORM.email.like(f"%{SUFFIX}"))
        restaurants = select(RestaurantORM.id).where(RestaurantORM.user_id.in_(demo))
        n_dishes = await session.scalar(select(func.count(DishORM.id)).where(DishORM.restaurant_id.in_(restaurants)))
        n_restaurants = await session.scalar(select(func.count(RestaurantORM.id)).where(RestaurantORM.user_id.in_(demo)))
        n_users = (await session.execute(delete(UserORM).where(UserORM.email.like(f"%{SUFFIX}")))).rowcount
        return [f"removed {n_users} demo users, {n_restaurants} restaurants, {n_dishes} dishes"]

    users, restaurants = SQLAlchemyUserRepository(session), SQLAlchemyRestaurantRepository(session)
    now = datetime.now(UTC)
    lines = []
    for i, (name, address, lat, lng, hours, dishes) in enumerate(DEMO, start=1):
        email = f"demo-owner-{i}{SUFFIX}"
        if await users.get_by_email(email):
            lines.append(f"{name}: exists")
            continue
        owner = await users.create(User.create(email=email, name=f"Demo Owner {i}"))
        restaurant = Restaurant.create(
            user_id=owner.id, name=name, address=address, phone=f"0909 000 00{i}",
            opening_hours=hours, latitude=lat, longitude=lng, description="Quán hư cấu, dữ liệu demo.",
        )
        restaurant.review(ReviewDecision.APPROVED, None, now)
        await restaurants.add(restaurant)
        for dish_name, price, serving_g, kcal, protein, carbs, fat, fiber in dishes:
            dish = Dish.create(
                restaurant_id=restaurant.id, name=dish_name, price=Decimal(price), serving_g=serving_g,
                kcal=kcal, protein_g=protein, carbs_g=carbs, fat_g=fat, fiber_g=fiber,
            )
            dish.review(ReviewDecision.APPROVED, None, now)
            await restaurants.add_dish(dish)
        lines.append(f"{name}: created with {len(dishes)} dishes")
    return lines


if __name__ == "__main__":
    from scripts._cli import main

    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("--remove", action="store_true", help="delete the demo owners (and their restaurants/dishes)")
    main(p, lambda s, a: run(s, a.remove))
