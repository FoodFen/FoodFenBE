"""Use case: the owner's ads page: featured-until, buyable packages, 30 days of impressions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta

from src.application.dtos.ad import AdImpressionDayDTO, AdPackageDTO, MyAdsDTO
from src.application.ports.ad_impression_repository import AdImpressionRepositoryProtocol
from src.application.ports.ad_package_repository import AdPackageRepositoryProtocol
from src.application.ports.restaurant_repository import RestaurantRepositoryProtocol
from src.application.use_cases.get_admin_dashboard import VIETNAM
from src.application.use_cases.restaurant_support import owned_restaurant

_DAYS = 30


@dataclass
class GetMyAdsUseCase:
    restaurants: RestaurantRepositoryProtocol
    packages: AdPackageRepositoryProtocol
    impressions: AdImpressionRepositoryProtocol

    async def execute(self, user_id: int, today: date | None = None) -> MyAdsDTO:
        restaurant = await owned_restaurant(self.restaurants, user_id)
        today = today or datetime.now(VIETNAM).date()
        days = [today - timedelta(days=i) for i in range(_DAYS - 1, -1, -1)]
        counts = await self.impressions.counts(restaurant.id, days[0], today)
        return MyAdsDTO(
            featured_until=restaurant.featured_until,
            packages=[AdPackageDTO.from_entity(p) for p in await self.packages.list_packages(active_only=True)],
            impressions=[AdImpressionDayDTO(date=d, count=counts.get(d, 0)) for d in days],
        )
