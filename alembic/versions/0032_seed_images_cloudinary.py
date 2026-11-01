"""Demo seed images: Wikimedia -> our own Cloudinary

Wikimedia 403s the Android app's okhttp User-Agent, and the FE contract requires our own
Cloudinary URLs. Exact-match only, so owner-uploaded images are untouched and absent rows are a no-op.

Revision ID: 0032
Revises: 0031
Create Date: 2026-11-01
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0032"
down_revision: str | None = "0031"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_MOVED = {
    "https://thumb.wikimedia.org/wikipedia/commons/thumb/0/0e/Saigon_Street_Corner_Dining_%28at_noon%29.jpg/960px-Saigon_Street_Corner_Dining_%28at_noon%29.jpg":
        "https://res.cloudinary.com/dv1zgaj5y/image/upload/v1793530187/wepvfwfz8z19f42tb3so.jpg",
    "https://thumb.wikimedia.org/wikipedia/commons/thumb/0/02/G%E1%BB%8Fi_Cu%E1%BB%91n_Chay_Vietnamese_Fresh_Vegetarian_Spring_Roll_2019-1599.jpg/960px-G%E1%BB%8Fi_Cu%E1%BB%91n_Chay_Vietnamese_Fresh_Vegetarian_Spring_Roll_2019-1599.jpg":
        "https://res.cloudinary.com/dv1zgaj5y/image/upload/v1793530189/yze91uzplvfqwj23gjzi.jpg",
    "https://thumb.wikimedia.org/wikipedia/commons/thumb/f/f2/Goi_cuon_Phuongnhu.JPG/960px-Goi_cuon_Phuongnhu.JPG":
        "https://res.cloudinary.com/dv1zgaj5y/image/upload/v1793530191/amcbl8tj1fp2dahlxqvw.jpg",
    "https://upload.wikimedia.org/wikipedia/commons/4/4f/Banh_mi_thit_Nhu_Lan.jpg":
        "https://res.cloudinary.com/dv1zgaj5y/image/upload/v1793530194/thr3aqdpqshhdhugvukk.jpg",
    "https://thumb.wikimedia.org/wikipedia/commons/thumb/7/75/Pho_Bo_Tai_%2824011248086%29.jpg/960px-Pho_Bo_Tai_%2824011248086%29.jpg":
        "https://res.cloudinary.com/dv1zgaj5y/image/upload/v1793530196/cg3q0ufennjf6iiq8ean.jpg",
    "https://thumb.wikimedia.org/wikipedia/commons/thumb/0/00/Bun-Bo-Hue-from-Huong-Giang-2011.jpg/960px-Bun-Bo-Hue-from-Huong-Giang-2011.jpg":
        "https://res.cloudinary.com/dv1zgaj5y/image/upload/v1793530199/x2boo00wu9rvsbwwvhdy.jpg",
    "https://thumb.wikimedia.org/wikipedia/commons/thumb/e/e9/Com_chien_duong_chau.jpg/960px-Com_chien_duong_chau.jpg":
        "https://res.cloudinary.com/dv1zgaj5y/image/upload/v1793530201/tgwqlbzdtxq21ffrccoc.jpg",
    "https://thumb.wikimedia.org/wikipedia/commons/thumb/0/05/Broken_rice_restaurant_in_Saigon.JPG/960px-Broken_rice_restaurant_in_Saigon.JPG":
        "https://res.cloudinary.com/dv1zgaj5y/image/upload/v1793530205/qy0debkllukwgwqjvp16.jpg",
    "https://thumb.wikimedia.org/wikipedia/commons/thumb/e/ec/Canh_chua_c%C3%A1_l%C3%B3c_%E1%BB%9F_Th%E1%BB%A7y_Tr%C3%BAc_Qu%C3%A1n%2C_%C4%91%C6%B0%E1%BB%9Dng_Nguy%E1%BB%85n_Nh%E1%BB%AF_L%C3%A3m_%284%29.jpg/960px-Canh_chua_c%C3%A1_l%C3%B3c_%E1%BB%9F_Th%E1%BB%A7y_Tr%C3%BAc_Qu%C3%A1n%2C_%C4%91%C6%B0%E1%BB%9Dng_Nguy%E1%BB%85n_Nh%E1%BB%AF_L%C3%A3m_%284%29.jpg":
        "https://res.cloudinary.com/dv1zgaj5y/image/upload/v1793530208/qgvafarcqopzsmhtaqza.jpg",
    "https://thumb.wikimedia.org/wikipedia/commons/thumb/f/fb/Chicken_breast_and_salad_-_Massachusetts.jpg/960px-Chicken_breast_and_salad_-_Massachusetts.jpg":
        "https://res.cloudinary.com/dv1zgaj5y/image/upload/v1793530212/gylzt4yppsena4rdpagw.jpg",
    "https://thumb.wikimedia.org/wikipedia/commons/thumb/b/b4/C%C3%A1_kho_t%E1%BB%99.JPG/960px-C%C3%A1_kho_t%E1%BB%99.JPG":
        "https://res.cloudinary.com/dv1zgaj5y/image/upload/v1793530215/tbuf61y47on30dazxnt1.jpg",
    "https://thumb.wikimedia.org/wikipedia/commons/thumb/f/f1/Tomato-sauced_tofu.jpg/960px-Tomato-sauced_tofu.jpg":
        "https://res.cloudinary.com/dv1zgaj5y/image/upload/v1793530219/d1l0dh1zv3wlal3uz1bs.jpg",
    "https://thumb.wikimedia.org/wikipedia/commons/thumb/5/5e/C%C6%A1m_t%E1%BA%A5m_SG_%28c%C6%A1m_s%C6%B0%E1%BB%9Dn%29_ng27th9n2020_%282%29.jpg/960px-C%C6%A1m_t%E1%BA%A5m_SG_%28c%C6%A1m_s%C6%B0%E1%BB%9Dn%29_ng27th9n2020_%282%29.jpg":
        "https://res.cloudinary.com/dv1zgaj5y/image/upload/v1793530222/fnq09ydgzsjlqthfnhkx.jpg",
    "https://thumb.wikimedia.org/wikipedia/commons/thumb/8/81/C%C6%A1m_t%E1%BA%A5m_s%C6%B0%E1%BB%9Dn_b%C3%AC_ch%E1%BA%A3.jpg/960px-C%C6%A1m_t%E1%BA%A5m_s%C6%B0%E1%BB%9Dn_b%C3%AC_ch%E1%BA%A3.jpg":
        "https://res.cloudinary.com/dv1zgaj5y/image/upload/v1793530225/rzxtscbaht6yhcg1kvft.jpg",
    "https://thumb.wikimedia.org/wikipedia/commons/thumb/e/e3/Vietnam_Foods_on_the_dining_table_at_a_vietnamese_restaurant_202208.jpg/960px-Vietnam_Foods_on_the_dining_table_at_a_vietnamese_restaurant_202208.jpg":
        "https://res.cloudinary.com/dv1zgaj5y/image/upload/v1793530227/rf28gs2rlrluprvc9qsv.jpg",
    "https://thumb.wikimedia.org/wikipedia/commons/thumb/5/58/Lotussalat_%285808937273%29.jpg/960px-Lotussalat_%285808937273%29.jpg":
        "https://res.cloudinary.com/dv1zgaj5y/image/upload/v1793530230/lb4qdzelw1d4dfwoivw8.jpg",
    "https://thumb.wikimedia.org/wikipedia/commons/thumb/4/4d/M%E1%BB%99t_ph%E1%BA%A7n_b%C3%A1nh_m%C3%AC_ch%E1%BA%A3o_v%E1%BB%9Bi_tr%E1%BB%A9ng_v%C3%A0_ch%E1%BA%A3_%2838657217774%29.jpg/960px-M%E1%BB%99t_ph%E1%BA%A7n_b%C3%A1nh_m%C3%AC_ch%E1%BA%A3o_v%E1%BB%9Bi_tr%E1%BB%A9ng_v%C3%A0_ch%E1%BA%A3_%2838657217774%29.jpg":
        "https://res.cloudinary.com/dv1zgaj5y/image/upload/v1793530232/uucd46qpwvoaeh8zfxng.jpg",
    "https://thumb.wikimedia.org/wikipedia/commons/thumb/6/6b/H%E1%BB%A7_ti%E1%BA%BFu_Nam_vang_gi%C3%B2.jpg/960px-H%E1%BB%A7_ti%E1%BA%BFu_Nam_vang_gi%C3%B2.jpg":
        "https://res.cloudinary.com/dv1zgaj5y/image/upload/v1793530235/ekuyiioxnmntgnlz0qs4.jpg",
    "https://thumb.wikimedia.org/wikipedia/commons/thumb/d/dc/M%C3%AC_x%C3%A0o_kh%C3%B4_Vi%E1%BB%87t_Nam.jpg/960px-M%C3%AC_x%C3%A0o_kh%C3%B4_Vi%E1%BB%87t_Nam.jpg":
        "https://res.cloudinary.com/dv1zgaj5y/image/upload/v1793530238/ivioaasmogzoddkqlbhm.jpg",
    "https://thumb.wikimedia.org/wikipedia/commons/thumb/4/47/Bun_thit_nuong.jpg/960px-Bun_thit_nuong.jpg":
        "https://res.cloudinary.com/dv1zgaj5y/image/upload/v1793530240/nkazg2xg4pskvpxmvyay.jpg",
    "https://thumb.wikimedia.org/wikipedia/commons/thumb/5/56/Bun_cha_Hanoi.jpg/960px-Bun_cha_Hanoi.jpg":
        "https://res.cloudinary.com/dv1zgaj5y/image/upload/v1793530243/uurvntgwermh3dg6yjvh.jpg",
}


def _swap(pairs: dict[str, str]) -> None:
    for table in ("dishes", "restaurants"):
        stmt = sa.text(f"UPDATE {table} SET image_url = :new WHERE image_url = :old")
        for old, new in pairs.items():
            op.execute(stmt.bindparams(old=old, new=new))


def upgrade() -> None:
    _swap(_MOVED)


def downgrade() -> None:
    _swap({new: old for old, new in _MOVED.items()})
