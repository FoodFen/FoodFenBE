"""Use-case providers for every slice, in one place.

One file to open when wiring or reviewing a use case, at the cost of it
growing with the app. Split it again (e.g. by slice) if it gets unwieldy.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from src.application.use_cases.analyze_food_image import AnalyzeFoodImageUseCase
from src.application.use_cases.analyze_food_text import AnalyzeFoodTextUseCase
from src.application.use_cases.cancel_payment import CancelPaymentUseCase
from src.application.use_cases.create_activity_log import CreateActivityLogUseCase
from src.application.use_cases.create_checkout import CreateCheckoutUseCase
from src.application.use_cases.create_daily_goal import CreateDailyGoalUseCase
from src.application.use_cases.create_food_entry import CreateFoodEntryUseCase
from src.application.use_cases.delete_food_entry import DeleteFoodEntryUseCase
from src.application.use_cases.delete_water_log import DeleteWaterLogUseCase
from src.application.use_cases.get_food_entry import GetFoodEntryUseCase
from src.application.use_cases.get_my_subscription import GetMySubscriptionUseCase
from src.application.use_cases.get_payment_status import GetPaymentStatusUseCase
from src.application.use_cases.get_user import GetUserUseCase
from src.application.use_cases.handle_payment_webhook import HandlePaymentWebhookUseCase
from src.application.use_cases.list_activity_logs import ListActivityLogsUseCase
from src.application.use_cases.list_chat_messages import ListChatMessagesUseCase
from src.application.use_cases.list_daily_goals import ListDailyGoalsUseCase
from src.application.use_cases.list_food_entries import ListFoodEntriesUseCase
from src.application.use_cases.list_water_logs import ListWaterLogsUseCase
from src.application.use_cases.list_weight_logs import ListWeightLogsUseCase
from src.application.use_cases.login import LoginUseCase
from src.application.use_cases.logout import LogoutUseCase
from src.application.use_cases.refresh_token import RefreshTokenUseCase
from src.application.use_cases.register_user import RegisterUserUseCase
from src.application.use_cases.request_password_reset import RequestPasswordResetUseCase
from src.application.use_cases.resend_verification import ResendVerificationUseCase
from src.application.use_cases.reset_password import ResetPasswordUseCase
from src.application.use_cases.send_chat_message import SendChatMessageUseCase
from src.application.use_cases.create_water_log import CreateWaterLogUseCase
from src.application.use_cases.create_weight_log import CreateWeightLogUseCase
from src.application.use_cases.social_sign_in import SocialSignInUseCase
from src.application.use_cases.update_activity_log import UpdateActivityLogUseCase
from src.application.use_cases.update_food_entry import UpdateFoodEntryUseCase
from src.application.use_cases.update_user_profile import UpdateUserProfileUseCase
from src.application.use_cases.update_water_log import UpdateWaterLogUseCase
from src.application.use_cases.verify_email import VerifyEmailUseCase
from src.infrastructure.config import settings
from src.infrastructure.di.repositories import (
    ActivityLogRepositoryDep,
    ChatMessageRepositoryDep,
    DailyGoalRepositoryDep,
    FoodEntryRepositoryDep,
    PaymentRepositoryDep,
    RefreshTokenRepositoryDep,
    SocialIdentityRepositoryDep,
    SubscriptionRepositoryDep,
    UserRepositoryDep,
    WaterLogRepositoryDep,
    WeightLogRepositoryDep,
)
from src.infrastructure.di.security import (
    AiChatProviderDep,
    FoodVisionProviderDep,
    ImageStorageDep,
    PasswordHasherDep,
    PaymentProviderDep,
    SocialIdentityVerifierDep,
    TokenServiceDep,
)


def get_get_user_use_case(repo: UserRepositoryDep) -> GetUserUseCase:
    return GetUserUseCase(users=repo)


GetUserUseCaseDep = Annotated[GetUserUseCase, Depends(get_get_user_use_case)]


def get_update_user_profile_use_case(
    users: UserRepositoryDep,
) -> UpdateUserProfileUseCase:
    return UpdateUserProfileUseCase(users=users)


UpdateUserProfileUseCaseDep = Annotated[
    UpdateUserProfileUseCase, Depends(get_update_user_profile_use_case)
]


def get_register_use_case(
    users: UserRepositoryDep,
    refresh_tokens: RefreshTokenRepositoryDep,
    hasher: PasswordHasherDep,
    tokens: TokenServiceDep,
) -> RegisterUserUseCase:
    return RegisterUserUseCase(
        users=users, refresh_tokens=refresh_tokens, hasher=hasher, tokens=tokens
    )


def get_login_use_case(
    users: UserRepositoryDep,
    refresh_tokens: RefreshTokenRepositoryDep,
    hasher: PasswordHasherDep,
    tokens: TokenServiceDep,
) -> LoginUseCase:
    return LoginUseCase(
        users=users, refresh_tokens=refresh_tokens, hasher=hasher, tokens=tokens
    )


def get_refresh_use_case(
    users: UserRepositoryDep,
    refresh_tokens: RefreshTokenRepositoryDep,
    tokens: TokenServiceDep,
) -> RefreshTokenUseCase:
    return RefreshTokenUseCase(users=users, refresh_tokens=refresh_tokens, tokens=tokens)


def get_logout_use_case(
    refresh_tokens: RefreshTokenRepositoryDep, tokens: TokenServiceDep
) -> LogoutUseCase:
    return LogoutUseCase(refresh_tokens=refresh_tokens, tokens=tokens)


def get_verify_email_use_case(
    users: UserRepositoryDep, tokens: TokenServiceDep
) -> VerifyEmailUseCase:
    return VerifyEmailUseCase(users=users, tokens=tokens)


def get_resend_verification_use_case(
    users: UserRepositoryDep, tokens: TokenServiceDep
) -> ResendVerificationUseCase:
    return ResendVerificationUseCase(users=users, tokens=tokens)


def get_request_password_reset_use_case(
    users: UserRepositoryDep, tokens: TokenServiceDep
) -> RequestPasswordResetUseCase:
    return RequestPasswordResetUseCase(users=users, tokens=tokens)


def get_reset_password_use_case(
    users: UserRepositoryDep, hasher: PasswordHasherDep, tokens: TokenServiceDep
) -> ResetPasswordUseCase:
    return ResetPasswordUseCase(users=users, hasher=hasher, tokens=tokens)


def get_social_sign_in_use_case(
    users: UserRepositoryDep,
    social_identities: SocialIdentityRepositoryDep,
    refresh_tokens: RefreshTokenRepositoryDep,
    verifier: SocialIdentityVerifierDep,
    tokens: TokenServiceDep,
) -> SocialSignInUseCase:
    return SocialSignInUseCase(
        users=users,
        social_identities=social_identities,
        refresh_tokens=refresh_tokens,
        verifier=verifier,
        tokens=tokens,
    )


def get_list_chat_messages_use_case(
    chat_messages: ChatMessageRepositoryDep,
) -> ListChatMessagesUseCase:
    return ListChatMessagesUseCase(chat_messages=chat_messages)


def get_send_chat_message_use_case(
    chat_messages: ChatMessageRepositoryDep, provider: AiChatProviderDep
) -> SendChatMessageUseCase:
    return SendChatMessageUseCase(
        chat_messages=chat_messages,
        provider=provider,
        history_limit=settings.chat_history_limit,
    )


def get_analyze_food_image_use_case(
    vision: FoodVisionProviderDep, images: ImageStorageDep
) -> AnalyzeFoodImageUseCase:
    return AnalyzeFoodImageUseCase(vision=vision, images=images)


def get_analyze_food_text_use_case(vision: FoodVisionProviderDep) -> AnalyzeFoodTextUseCase:
    return AnalyzeFoodTextUseCase(vision=vision)


RegisterUseCaseDep = Annotated[RegisterUserUseCase, Depends(get_register_use_case)]
LoginUseCaseDep = Annotated[LoginUseCase, Depends(get_login_use_case)]
RefreshUseCaseDep = Annotated[RefreshTokenUseCase, Depends(get_refresh_use_case)]
LogoutUseCaseDep = Annotated[LogoutUseCase, Depends(get_logout_use_case)]
VerifyEmailUseCaseDep = Annotated[VerifyEmailUseCase, Depends(get_verify_email_use_case)]
ResendVerificationUseCaseDep = Annotated[
    ResendVerificationUseCase, Depends(get_resend_verification_use_case)
]
RequestPasswordResetUseCaseDep = Annotated[
    RequestPasswordResetUseCase, Depends(get_request_password_reset_use_case)
]
ResetPasswordUseCaseDep = Annotated[ResetPasswordUseCase, Depends(get_reset_password_use_case)]
SocialSignInUseCaseDep = Annotated[SocialSignInUseCase, Depends(get_social_sign_in_use_case)]
ListChatMessagesUseCaseDep = Annotated[
    ListChatMessagesUseCase, Depends(get_list_chat_messages_use_case)
]
SendChatMessageUseCaseDep = Annotated[
    SendChatMessageUseCase, Depends(get_send_chat_message_use_case)
]
AnalyzeFoodImageUseCaseDep = Annotated[
    AnalyzeFoodImageUseCase, Depends(get_analyze_food_image_use_case)
]
AnalyzeFoodTextUseCaseDep = Annotated[
    AnalyzeFoodTextUseCase, Depends(get_analyze_food_text_use_case)
]


def get_create_checkout_use_case(
    payments: PaymentRepositoryDep, provider: PaymentProviderDep
) -> CreateCheckoutUseCase:
    return CreateCheckoutUseCase(
        payments=payments,
        provider=provider,
        monthly_price_vnd=settings.payos_monthly_price_vnd,
        annual_price_vnd=settings.payos_annual_price_vnd,
        return_url=settings.payos_return_url,
        cancel_url=settings.payos_cancel_url,
    )


def get_handle_payment_webhook_use_case(
    payments: PaymentRepositoryDep,
    provider: PaymentProviderDep,
    subscriptions: SubscriptionRepositoryDep,
    users: UserRepositoryDep,
) -> HandlePaymentWebhookUseCase:
    return HandlePaymentWebhookUseCase(
        payments=payments, provider=provider, subscriptions=subscriptions, users=users
    )


def get_get_payment_status_use_case(
    payments: PaymentRepositoryDep,
    provider: PaymentProviderDep,
    subscriptions: SubscriptionRepositoryDep,
    users: UserRepositoryDep,
) -> GetPaymentStatusUseCase:
    return GetPaymentStatusUseCase(
        payments=payments, provider=provider, subscriptions=subscriptions, users=users
    )


def get_cancel_payment_use_case(
    payments: PaymentRepositoryDep, provider: PaymentProviderDep
) -> CancelPaymentUseCase:
    return CancelPaymentUseCase(payments=payments, provider=provider)


def get_get_my_subscription_use_case(
    subscriptions: SubscriptionRepositoryDep,
) -> GetMySubscriptionUseCase:
    return GetMySubscriptionUseCase(subscriptions=subscriptions)


CreateCheckoutUseCaseDep = Annotated[CreateCheckoutUseCase, Depends(get_create_checkout_use_case)]
HandlePaymentWebhookUseCaseDep = Annotated[
    HandlePaymentWebhookUseCase, Depends(get_handle_payment_webhook_use_case)
]
GetPaymentStatusUseCaseDep = Annotated[
    GetPaymentStatusUseCase, Depends(get_get_payment_status_use_case)
]
CancelPaymentUseCaseDep = Annotated[CancelPaymentUseCase, Depends(get_cancel_payment_use_case)]
GetMySubscriptionUseCaseDep = Annotated[
    GetMySubscriptionUseCase, Depends(get_get_my_subscription_use_case)
]


def get_create_food_entry_use_case(
    food_entries: FoodEntryRepositoryDep,
) -> CreateFoodEntryUseCase:
    return CreateFoodEntryUseCase(food_entries=food_entries)


def get_get_food_entry_use_case(food_entries: FoodEntryRepositoryDep) -> GetFoodEntryUseCase:
    return GetFoodEntryUseCase(food_entries=food_entries)


CreateFoodEntryUseCaseDep = Annotated[
    CreateFoodEntryUseCase, Depends(get_create_food_entry_use_case)
]
GetFoodEntryUseCaseDep = Annotated[GetFoodEntryUseCase, Depends(get_get_food_entry_use_case)]


def get_update_food_entry_use_case(
    food_entries: FoodEntryRepositoryDep,
) -> UpdateFoodEntryUseCase:
    return UpdateFoodEntryUseCase(food_entries=food_entries)


def get_delete_food_entry_use_case(
    food_entries: FoodEntryRepositoryDep,
) -> DeleteFoodEntryUseCase:
    return DeleteFoodEntryUseCase(food_entries=food_entries)


UpdateFoodEntryUseCaseDep = Annotated[
    UpdateFoodEntryUseCase, Depends(get_update_food_entry_use_case)
]
DeleteFoodEntryUseCaseDep = Annotated[
    DeleteFoodEntryUseCase, Depends(get_delete_food_entry_use_case)
]


def get_create_daily_goal_use_case(
    daily_goals: DailyGoalRepositoryDep,
) -> CreateDailyGoalUseCase:
    return CreateDailyGoalUseCase(daily_goals=daily_goals)


CreateDailyGoalUseCaseDep = Annotated[
    CreateDailyGoalUseCase, Depends(get_create_daily_goal_use_case)
]


def get_list_daily_goals_use_case(daily_goals: DailyGoalRepositoryDep) -> ListDailyGoalsUseCase:
    return ListDailyGoalsUseCase(daily_goals=daily_goals)


def get_list_food_entries_use_case(food_entries: FoodEntryRepositoryDep) -> ListFoodEntriesUseCase:
    return ListFoodEntriesUseCase(food_entries=food_entries)


def get_list_activity_logs_use_case(
    activity_logs: ActivityLogRepositoryDep,
) -> ListActivityLogsUseCase:
    return ListActivityLogsUseCase(activity_logs=activity_logs)


def get_list_water_logs_use_case(water_logs: WaterLogRepositoryDep) -> ListWaterLogsUseCase:
    return ListWaterLogsUseCase(water_logs=water_logs)


def get_create_water_log_use_case(water_logs: WaterLogRepositoryDep) -> CreateWaterLogUseCase:
    return CreateWaterLogUseCase(water_logs=water_logs)


def get_delete_water_log_use_case(water_logs: WaterLogRepositoryDep) -> DeleteWaterLogUseCase:
    return DeleteWaterLogUseCase(water_logs=water_logs)


def get_update_water_log_use_case(water_logs: WaterLogRepositoryDep) -> UpdateWaterLogUseCase:
    return UpdateWaterLogUseCase(water_logs=water_logs)


CreateWaterLogUseCaseDep = Annotated[
    CreateWaterLogUseCase, Depends(get_create_water_log_use_case)
]
DeleteWaterLogUseCaseDep = Annotated[
    DeleteWaterLogUseCase, Depends(get_delete_water_log_use_case)
]
UpdateWaterLogUseCaseDep = Annotated[
    UpdateWaterLogUseCase, Depends(get_update_water_log_use_case)
]


def get_list_weight_logs_use_case(weight_logs: WeightLogRepositoryDep) -> ListWeightLogsUseCase:
    return ListWeightLogsUseCase(weight_logs=weight_logs)


def get_create_weight_log_use_case(
    weight_logs: WeightLogRepositoryDep,
) -> CreateWeightLogUseCase:
    return CreateWeightLogUseCase(weight_logs=weight_logs)


CreateWeightLogUseCaseDep = Annotated[
    CreateWeightLogUseCase, Depends(get_create_weight_log_use_case)
]


def get_create_activity_log_use_case(
    activity_logs: ActivityLogRepositoryDep,
) -> CreateActivityLogUseCase:
    return CreateActivityLogUseCase(activity_logs=activity_logs)


def get_update_activity_log_use_case(
    activity_logs: ActivityLogRepositoryDep,
) -> UpdateActivityLogUseCase:
    return UpdateActivityLogUseCase(activity_logs=activity_logs)


CreateActivityLogUseCaseDep = Annotated[
    CreateActivityLogUseCase, Depends(get_create_activity_log_use_case)
]
UpdateActivityLogUseCaseDep = Annotated[
    UpdateActivityLogUseCase, Depends(get_update_activity_log_use_case)
]


ListDailyGoalsUseCaseDep = Annotated[ListDailyGoalsUseCase, Depends(get_list_daily_goals_use_case)]
ListFoodEntriesUseCaseDep = Annotated[
    ListFoodEntriesUseCase, Depends(get_list_food_entries_use_case)
]
ListActivityLogsUseCaseDep = Annotated[
    ListActivityLogsUseCase, Depends(get_list_activity_logs_use_case)
]
ListWaterLogsUseCaseDep = Annotated[ListWaterLogsUseCase, Depends(get_list_water_logs_use_case)]
ListWeightLogsUseCaseDep = Annotated[
    ListWeightLogsUseCase, Depends(get_list_weight_logs_use_case)
]
