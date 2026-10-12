"""Use case: an owner buys a paid-placement package for their restaurant."""

from __future__ import annotations

from dataclasses import dataclass

from src.application.dtos.payment import CheckoutOutputDTO, CreateAdCheckoutInputDTO
from src.application.ports.ad_package_repository import AdPackageRepositoryProtocol
from src.application.ports.payment_provider import PaymentProviderProtocol
from src.application.ports.payment_repository import PaymentRepositoryProtocol
from src.application.ports.restaurant_repository import RestaurantRepositoryProtocol
from src.application.use_cases.create_checkout import start_checkout
from src.application.use_cases.restaurant_support import owned_restaurant
from src.domain.entities.payment import Payment
from src.domain.enums import ModerationStatus, PaymentProvider, PlanType
from src.domain.exceptions import (
    AdPackageNotFoundException,
    PaymentProviderUnavailableException,
    RestaurantNotApprovedException,
)


@dataclass
class CreateAdCheckoutUseCase:
    restaurants: RestaurantRepositoryProtocol
    packages: AdPackageRepositoryProtocol
    payments: PaymentRepositoryProtocol
    providers: dict[PaymentProvider, PaymentProviderProtocol]
    return_url: str  # also the cancel URL: the ads page polls the payment either way

    async def execute(self, input_dto: CreateAdCheckoutInputDTO) -> CheckoutOutputDTO:
        restaurant = await owned_restaurant(self.restaurants, input_dto.user_id)
        if restaurant.status is not ModerationStatus.APPROVED:
            raise RestaurantNotApprovedException("only an approved restaurant can buy placement")
        package = await self.packages.get(input_dto.package_id)
        if package is None or not package.active:
            raise AdPackageNotFoundException(f"ad package {input_dto.package_id} not found")
        provider = self.providers.get(input_dto.provider)
        if provider is None:
            raise PaymentProviderUnavailableException(f"payment provider {input_dto.provider} is not enabled")
        payment = Payment.create(
            input_dto.user_id, PlanType.AD_PACKAGE, package.price_vnd, input_dto.provider, ad_days=package.days
        )
        return await start_checkout(
            self.payments, provider, payment, f"FoodFen ads {package.days} days", self.return_url, self.return_url
        )
