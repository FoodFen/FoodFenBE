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
     "https://thumb.wikimedia.org/wikipedia/commons/thumb/0/0e/Saigon_Street_Corner_Dining_%28at_noon%29.jpg/960px-Saigon_Street_Corner_Dining_%28at_noon%29.jpg", [
        ("Gỏi cuốn chay (4 cuốn)", 35000, 300, 280, 10, 46, 6, 4, "https://thumb.wikimedia.org/wikipedia/commons/thumb/0/02/G%E1%BB%8Fi_Cu%E1%BB%91n_Chay_Vietnamese_Fresh_Vegetarian_Spring_Roll_2019-1599.jpg/960px-G%E1%BB%8Fi_Cu%E1%BB%91n_Chay_Vietnamese_Fresh_Vegetarian_Spring_Roll_2019-1599.jpg", DishDiet.VEGAN),
        ("Gỏi cuốn tôm thịt (4 cuốn)", 40000, 320, 320, 22, 44, 6, 4, "https://thumb.wikimedia.org/wikipedia/commons/thumb/f/f2/Goi_cuon_Phuongnhu.JPG/960px-Goi_cuon_Phuongnhu.JPG"),
        ("Bánh mì thịt", 25000, 250, 400, 18, 50, 14, 3, "https://upload.wikimedia.org/wikipedia/commons/4/4f/Banh_mi_thit_Nhu_Lan.jpg"),
        ("Phở bò tái", 60000, 500, 440, 32, 55, 10, 2, "https://thumb.wikimedia.org/wikipedia/commons/thumb/7/75/Pho_Bo_Tai_%2824011248086%29.jpg/960px-Pho_Bo_Tai_%2824011248086%29.jpg"),
        ("Bún bò Huế", 65000, 550, 520, 30, 62, 17, 3, "https://thumb.wikimedia.org/wikipedia/commons/thumb/0/00/Bun-Bo-Hue-from-Huong-Giang-2011.jpg/960px-Bun-Bo-Hue-from-Huong-Giang-2011.jpg"),
        ("Cơm chiên dương châu", 55000, 400, 680, 18, 90, 28, 3, "https://thumb.wikimedia.org/wikipedia/commons/thumb/e/e9/Com_chien_duong_chau.jpg/960px-Com_chien_duong_chau.jpg"),
    ]),
    ("Cơm Tấm Cô Sáu (Demo)", "118 Võ Văn Tần, Quận 3, TP.HCM", 10.7760, 106.6870, "6:30-22:00",
     "https://thumb.wikimedia.org/wikipedia/commons/thumb/0/05/Broken_rice_restaurant_in_Saigon.JPG/960px-Broken_rice_restaurant_in_Saigon.JPG", [
        ("Canh chua cá lóc", 50000, 400, 255, 26, 22, 7, 3, "https://thumb.wikimedia.org/wikipedia/commons/thumb/e/ec/Canh_chua_c%C3%A1_l%C3%B3c_%E1%BB%9F_Th%E1%BB%A7y_Tr%C3%BAc_Qu%C3%A1n%2C_%C4%91%C6%B0%E1%BB%9Dng_Nguy%E1%BB%85n_Nh%E1%BB%AF_L%C3%A3m_%284%29.jpg/960px-Canh_chua_c%C3%A1_l%C3%B3c_%E1%BB%9F_Th%E1%BB%A7y_Tr%C3%BAc_Qu%C3%A1n%2C_%C4%91%C6%B0%E1%BB%9Dng_Nguy%E1%BB%85n_Nh%E1%BB%AF_L%C3%A3m_%284%29.jpg"),
        ("Salad ức gà", 60000, 300, 280, 35, 14, 9, 5, "https://thumb.wikimedia.org/wikipedia/commons/thumb/f/fb/Chicken_breast_and_salad_-_Massachusetts.jpg/960px-Chicken_breast_and_salad_-_Massachusetts.jpg"),
        ("Cá kho tộ + cơm", 55000, 450, 525, 30, 70, 14, 2, "https://thumb.wikimedia.org/wikipedia/commons/thumb/b/b4/C%C3%A1_kho_t%E1%BB%99.JPG/960px-C%C3%A1_kho_t%E1%BB%99.JPG"),
        ("Đậu hũ sốt cà chua + cơm", 40000, 450, 520, 20, 78, 14, 5, "https://thumb.wikimedia.org/wikipedia/commons/thumb/f/f1/Tomato-sauced_tofu.jpg/960px-Tomato-sauced_tofu.jpg", DishDiet.VEGAN),
        ("Cơm tấm sườn nướng", 45000, 400, 630, 32, 75, 22, 2, "https://thumb.wikimedia.org/wikipedia/commons/thumb/5/5e/C%C6%A1m_t%E1%BA%A5m_SG_%28c%C6%A1m_s%C6%B0%E1%BB%9Dn%29_ng27th9n2020_%282%29.jpg/960px-C%C6%A1m_t%E1%BA%A5m_SG_%28c%C6%A1m_s%C6%B0%E1%BB%9Dn%29_ng27th9n2020_%282%29.jpg"),
        ("Cơm tấm sườn bì chả", 55000, 450, 760, 38, 85, 30, 2, "https://thumb.wikimedia.org/wikipedia/commons/thumb/8/81/C%C6%A1m_t%E1%BA%A5m_s%C6%B0%E1%BB%9Dn_b%C3%AC_ch%E1%BA%A3.jpg/960px-C%C6%A1m_t%E1%BA%A5m_s%C6%B0%E1%BB%9Dn_b%C3%AC_ch%E1%BA%A3.jpg"),
    ]),
    ("Tiệm Bún Chả Hai Lúa (Demo)", "76 Xô Viết Nghệ Tĩnh, Bình Thạnh, TP.HCM", 10.8010, 106.7110, "10:00-20:00",
     "https://thumb.wikimedia.org/wikipedia/commons/thumb/e/e3/Vietnam_Foods_on_the_dining_table_at_a_vietnamese_restaurant_202208.jpg/960px-Vietnam_Foods_on_the_dining_table_at_a_vietnamese_restaurant_202208.jpg", [
        ("Gỏi ngó sen tôm thịt", 50000, 250, 250, 20, 22, 9, 4, "https://thumb.wikimedia.org/wikipedia/commons/thumb/5/58/Lotussalat_%285808937273%29.jpg/960px-Lotussalat_%285808937273%29.jpg"),
        ("Bánh mì ốp la", 25000, 220, 400, 16, 45, 17, 2, "https://thumb.wikimedia.org/wikipedia/commons/thumb/4/4d/M%E1%BB%99t_ph%E1%BA%A7n_b%C3%A1nh_m%C3%AC_ch%E1%BA%A3o_v%E1%BB%9Bi_tr%E1%BB%A9ng_v%C3%A0_ch%E1%BA%A3_%2838657217774%29.jpg/960px-M%E1%BB%99t_ph%E1%BA%A7n_b%C3%A1nh_m%C3%AC_ch%E1%BA%A3o_v%E1%BB%9Bi_tr%E1%BB%A9ng_v%C3%A0_ch%E1%BA%A3_%2838657217774%29.jpg"),
        ("Hủ tiếu Nam Vang", 55000, 500, 500, 28, 65, 14, 2, "https://thumb.wikimedia.org/wikipedia/commons/thumb/6/6b/H%E1%BB%A7_ti%E1%BA%BFu_Nam_vang_gi%C3%B2.jpg/960px-H%E1%BB%A7_ti%E1%BA%BFu_Nam_vang_gi%C3%B2.jpg"),
        ("Mì xào trứng rau củ (chay)", 45000, 400, 560, 18, 80, 18, 5, "https://thumb.wikimedia.org/wikipedia/commons/thumb/d/dc/M%C3%AC_x%C3%A0o_kh%C3%B4_Vi%E1%BB%87t_Nam.jpg/960px-M%C3%AC_x%C3%A0o_kh%C3%B4_Vi%E1%BB%87t_Nam.jpg", DishDiet.VEGETARIAN),
        ("Bún thịt nướng", 50000, 450, 575, 28, 75, 18, 4, "https://thumb.wikimedia.org/wikipedia/commons/thumb/4/47/Bun_thit_nuong.jpg/960px-Bun_thit_nuong.jpg"),
        ("Bún chả", 55000, 500, 615, 34, 70, 22, 3, "https://thumb.wikimedia.org/wikipedia/commons/thumb/5/56/Bun_cha_Hanoi.jpg/960px-Bun_cha_Hanoi.jpg"),
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
