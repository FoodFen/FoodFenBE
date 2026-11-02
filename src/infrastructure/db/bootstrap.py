"""Startup bootstrap: admin account from env, optional fictional demo data. Idempotent (demo dishes are topped up per dish)."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.dish import Dish
from src.domain.entities.restaurant import Restaurant
from src.domain.entities.user import User
from src.domain.enums import DishDiet, ReviewDecision, UserRole
from src.infrastructure.config import settings
from src.infrastructure.db.repositories.restaurant_repository import SQLAlchemyRestaurantRepository
from src.infrastructure.db.repositories.user_repository import SQLAlchemyUserRepository
from src.infrastructure.db.session import SessionLocal
from src.infrastructure.logging import configure_logging
from src.infrastructure.security.password_hasher import BcryptPasswordHasher

_log = configure_logging()

SUFFIX = "@foodfen.invalid"

# (name, address, lat, lng, hours, image_url,
#  [(dish, price VND, serving_g, kcal, protein, carbs, fat, fiber, image_url[, DishDiet])])
# The optional last element is the diet tag (default NONE).
# kcal ~= 4*protein + 4*carbs + 9*fat, within 10%.
DEMO = [
    ("Bếp Ba Tèo (Demo)", "25 Nguyễn Thái Bình, Quận 1, TP.HCM", 10.7690, 106.6990, "6:00-21:00",
     "https://res.cloudinary.com/dv1zgaj5y/image/upload/v1793530187/wepvfwfz8z19f42tb3so.jpg", [
        ("Gỏi cuốn chay (4 cuốn)", 35000, 300, 280, 10, 46, 6, 4, "https://res.cloudinary.com/dv1zgaj5y/image/upload/v1793530189/yze91uzplvfqwj23gjzi.jpg", DishDiet.VEGAN),
        ("Gỏi cuốn tôm thịt (4 cuốn)", 40000, 320, 320, 22, 44, 6, 4, "https://res.cloudinary.com/dv1zgaj5y/image/upload/v1793530191/amcbl8tj1fp2dahlxqvw.jpg"),
        ("Bánh mì thịt", 25000, 250, 400, 18, 50, 14, 3, "https://res.cloudinary.com/dv1zgaj5y/image/upload/v1793530194/thr3aqdpqshhdhugvukk.jpg"),
        ("Phở bò tái", 60000, 500, 440, 32, 55, 10, 2, "https://res.cloudinary.com/dv1zgaj5y/image/upload/v1793530196/cg3q0ufennjf6iiq8ean.jpg"),
        ("Bún bò Huế", 65000, 550, 520, 30, 62, 17, 3, "https://res.cloudinary.com/dv1zgaj5y/image/upload/v1793530199/x2boo00wu9rvsbwwvhdy.jpg"),
        ("Cơm chiên dương châu", 55000, 400, 680, 18, 90, 28, 3, "https://res.cloudinary.com/dv1zgaj5y/image/upload/v1793530201/tgwqlbzdtxq21ffrccoc.jpg"),
    ]),
    ("Cơm Tấm Cô Sáu (Demo)", "118 Võ Văn Tần, Quận 3, TP.HCM", 10.7760, 106.6870, "6:30-22:00",
     "https://res.cloudinary.com/dv1zgaj5y/image/upload/v1793530205/qy0debkllukwgwqjvp16.jpg", [
        ("Canh chua cá lóc", 50000, 400, 255, 26, 22, 7, 3, "https://res.cloudinary.com/dv1zgaj5y/image/upload/v1793530208/qgvafarcqopzsmhtaqza.jpg"),
        ("Salad ức gà", 60000, 300, 280, 35, 14, 9, 5, "https://res.cloudinary.com/dv1zgaj5y/image/upload/v1793530212/gylzt4yppsena4rdpagw.jpg"),
        ("Cá kho tộ + cơm", 55000, 450, 525, 30, 70, 14, 2, "https://res.cloudinary.com/dv1zgaj5y/image/upload/v1793530215/tbuf61y47on30dazxnt1.jpg"),
        ("Đậu hũ sốt cà chua + cơm", 40000, 450, 520, 20, 78, 14, 5, "https://res.cloudinary.com/dv1zgaj5y/image/upload/v1793530219/d1l0dh1zv3wlal3uz1bs.jpg", DishDiet.VEGAN),
        ("Cơm tấm sườn nướng", 45000, 400, 630, 32, 75, 22, 2, "https://res.cloudinary.com/dv1zgaj5y/image/upload/v1793530222/fnq09ydgzsjlqthfnhkx.jpg"),
        ("Cơm tấm sườn bì chả", 55000, 450, 760, 38, 85, 30, 2, "https://res.cloudinary.com/dv1zgaj5y/image/upload/v1793530225/rzxtscbaht6yhcg1kvft.jpg"),
    ]),
    ("Tiệm Bún Chả Hai Lúa (Demo)", "76 Xô Viết Nghệ Tĩnh, Bình Thạnh, TP.HCM", 10.8010, 106.7110, "10:00-20:00",
     "https://res.cloudinary.com/dv1zgaj5y/image/upload/v1793530227/rf28gs2rlrluprvc9qsv.jpg", [
        ("Gỏi ngó sen tôm thịt", 50000, 250, 250, 20, 22, 9, 4, "https://res.cloudinary.com/dv1zgaj5y/image/upload/v1793530230/lb4qdzelw1d4dfwoivw8.jpg"),
        ("Bánh mì ốp la", 25000, 220, 400, 16, 45, 17, 2, "https://res.cloudinary.com/dv1zgaj5y/image/upload/v1793530232/uucd46qpwvoaeh8zfxng.jpg"),
        ("Hủ tiếu Nam Vang", 55000, 500, 500, 28, 65, 14, 2, "https://res.cloudinary.com/dv1zgaj5y/image/upload/v1793530235/ekuyiioxnmntgnlz0qs4.jpg"),
        ("Mì xào trứng rau củ (chay)", 45000, 400, 560, 18, 80, 18, 5, "https://res.cloudinary.com/dv1zgaj5y/image/upload/v1793530238/ivioaasmogzoddkqlbhm.jpg", DishDiet.VEGETARIAN),
        ("Bún thịt nướng", 50000, 450, 575, 28, 75, 18, 4, "https://res.cloudinary.com/dv1zgaj5y/image/upload/v1793530240/nkazg2xg4pskvpxmvyay.jpg"),
        ("Bún chả", 55000, 500, 615, 34, 70, 22, 3, "https://res.cloudinary.com/dv1zgaj5y/image/upload/v1793530243/uurvntgwermh3dg6yjvh.jpg"),
    ]),
]


async def ensure_admin(session: AsyncSession, email: str, password: str) -> None:
    """Create the admin, or promote the existing account. Never touches an existing password."""
    users = SQLAlchemyUserRepository(session)
    email = email.strip().lower()
    user = await users.get_by_email(email)
    if user is None:
        User.validate_password_strength(password)
        user = User.create(email=email, password_hash=await BcryptPasswordHasher().hash(password))
        user.role = UserRole.ADMIN
        await users.create(user)
        _log.info("bootstrap: created admin %s", email)
    elif not user.is_admin:
        user.role = UserRole.ADMIN
        await users.update(user)
        _log.info("bootstrap: promoted %s to admin", email)


async def seed_demo(session: AsyncSession) -> None:
    users, restaurants = SQLAlchemyUserRepository(session), SQLAlchemyRestaurantRepository(session)
    now = datetime.now(UTC)
    for i, (name, address, lat, lng, hours, image_url, dishes) in enumerate(DEMO, start=1):
        email = f"demo-owner-{i}{SUFFIX}"
        owner = await users.get_by_email(email)
        if owner:
            # Already seeded: top up new dishes and fill empty photos (never overwrite one).
            restaurant = await restaurants.get_by_owner(owner.id)
            if restaurant is None:
                continue
            if not restaurant.image_url:
                restaurant.image_url = image_url
                await restaurants.update(restaurant)
            have = {d.name: d for d in await restaurants.list_dishes(restaurant.id)}
        else:
            owner = await users.create(User.create(email=email, name=f"Demo Owner {i}"))
            restaurant = Restaurant.create(
                user_id=owner.id, name=name, address=address, phone=f"0909 000 00{i}",
                opening_hours=hours, latitude=lat, longitude=lng, description="Quán hư cấu, dữ liệu demo.",
                image_url=image_url,
            )
            restaurant.review(ReviewDecision.APPROVED, None, now)
            await restaurants.add(restaurant)
            have = {}
            _log.info("bootstrap: seeded demo restaurant %s", name)
        for dish_name, price, serving_g, kcal, protein, carbs, fat, fiber, dish_image, *diet in dishes:
            if existing := have.get(dish_name):
                if not existing.image_url:
                    existing.image_url = dish_image
                    await restaurants.update_dish(existing)
                continue
            dish = Dish.create(
                restaurant_id=restaurant.id, name=dish_name, price=Decimal(price), serving_g=serving_g,
                kcal=kcal, protein_g=protein, carbs_g=carbs, fat_g=fat, fiber_g=fiber, image_url=dish_image,
                diet_tag=diet[0] if diet else DishDiet.NONE,
            )
            dish.review(ReviewDecision.APPROVED, None, now)
            await restaurants.add_dish(dish)


async def bootstrap(session_factory=SessionLocal) -> None:
    """Run from ``main.lifespan`` on every start. Both steps are no-ops when already applied."""
    admin = settings.admin_email and settings.admin_password
    if not (admin or settings.seed_demo):
        return
    async with session_factory() as session:
        if admin:
            await ensure_admin(session, settings.admin_email, settings.admin_password)
        if settings.seed_demo:
            await seed_demo(session)
        await session.commit()
