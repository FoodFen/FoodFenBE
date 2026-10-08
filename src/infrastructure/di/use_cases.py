"""Use-case providers for every slice, in one place.

One file to open when wiring or reviewing a use case, at the cost of it
growing with the app. Split it again (e.g. by slice) if it gets unwieldy.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from src.application.use_cases.ai_trial import AiTrialUseCase
from src.application.use_cases.analyze_food_image import AnalyzeFoodImageUseCase
from src.application.use_cases.analyze_food_text import AnalyzeFoodTextUseCase
from src.application.use_cases.cancel_payment import CancelPaymentUseCase
from src.application.use_cases.create_activity_log import CreateActivityLogUseCase
from src.application.use_cases.create_checkout import CreateCheckoutUseCase
from src.application.use_cases.create_daily_goal import CreateDailyGoalUseCase
from src.application.use_cases.create_food_entry import CreateFoodEntryUseCase
from src.application.use_cases.create_water_log import CreateWaterLogUseCase
from src.application.use_cases.create_weight_log import CreateWeightLogUseCase
from src.application.use_cases.delete_food_entry import DeleteFoodEntryUseCase
from src.application.use_cases.delete_water_log import DeleteWaterLogUseCase
from src.application.use_cases.get_daily_quiz import GetDailyQuizUseCase
from src.application.use_cases.get_quests import GetQuestsUseCase
from src.application.use_cases.get_quiz import GetQuizUseCase
from src.application.use_cases.list_quiz_topics import ListQuizTopicsUseCase
from src.application.use_cases.quiz_support import QuizRewards
from src.application.use_cases.start_practice_quiz import StartPracticeQuizUseCase
from src.application.use_cases.submit_quiz import SubmitQuizUseCase
from src.application.use_cases.get_food_entry import GetFoodEntryUseCase
from src.application.use_cases.get_me import GetMeUseCase
from src.application.use_cases.get_my_subscription import GetMySubscriptionUseCase
from src.application.use_cases.get_payment_status import GetPaymentStatusUseCase
from src.application.use_cases.handle_payment_webhook import HandlePaymentWebhookUseCase
from src.application.use_cases.list_activity_logs import ListActivityLogsUseCase
from src.application.use_cases.list_chat_messages import ListChatMessagesUseCase
from src.application.use_cases.list_coin_bundles import ListCoinBundlesUseCase
from src.application.use_cases.list_plans import ListPlansUseCase
from src.application.use_cases.list_daily_goals import ListDailyGoalsUseCase
from src.application.use_cases.list_food_entries import ListFoodEntriesUseCase
from src.application.use_cases.list_water_logs import ListWaterLogsUseCase
from src.application.use_cases.list_weight_logs import ListWeightLogsUseCase
from src.application.use_cases.login import LoginUseCase
from src.application.use_cases.logout import LogoutUseCase
from src.application.use_cases.redeem_coins import RedeemCoinsUseCase
from src.application.use_cases.refresh_token import RefreshTokenUseCase
from src.application.use_cases.register_user import RegisterUserUseCase
from src.application.use_cases.request_password_reset import RequestPasswordResetUseCase
from src.application.use_cases.resend_verification import ResendVerificationUseCase
from src.application.use_cases.reset_password import ResetPasswordUseCase
from src.application.use_cases.send_chat_message import SendChatMessageUseCase
from src.application.use_cases.social_sign_in import SocialSignInUseCase
from src.application.use_cases.update_activity_log import UpdateActivityLogUseCase
from src.application.use_cases.update_food_entry import UpdateFoodEntryUseCase
from src.application.use_cases.update_user_profile import UpdateUserProfileUseCase
from src.application.use_cases.update_water_log import UpdateWaterLogUseCase
from src.application.use_cases.upsert_streak import UpsertStreakUseCase
from src.application.use_cases.verify_email import VerifyEmailUseCase
from src.application.use_cases.create_dish import CreateDishUseCase
from src.application.use_cases.create_restaurant import CreateRestaurantUseCase
from src.application.use_cases.delete_dish import DeleteDishUseCase
from src.application.use_cases.get_my_restaurant import GetMyRestaurantUseCase
from src.application.use_cases.list_my_dishes import ListMyDishesUseCase
from src.application.use_cases.update_dish import UpdateDishUseCase
from src.application.use_cases.update_my_restaurant import UpdateMyRestaurantUseCase
from src.application.use_cases.upload_restaurant_image import UploadRestaurantImageUseCase
from src.application.use_cases.get_admin_restaurant import GetAdminRestaurantUseCase
from src.application.use_cases.list_admin_restaurants import ListAdminRestaurantsUseCase
from src.application.use_cases.review_dish import ReviewDishUseCase
from src.application.use_cases.review_restaurant import ReviewRestaurantUseCase
from src.infrastructure.config import settings
from src.infrastructure.di.repositories import (
    AiTrialRepositoryDep,
    ActivityLogRepositoryDep,
    CoinBundleRepositoryDep,
    CoinRepositoryDep,
    QuestRepositoryDep,
    QuizRepositoryDep,
    RestaurantRepositoryDep,
    ChatMessageRepositoryDep,
    DailyGoalRepositoryDep,
    FoodEntryRepositoryDep,
    PaymentRepositoryDep,
    RefreshTokenRepositoryDep,
    SocialIdentityRepositoryDep,
    StreakRepositoryDep,
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
    PaymentProvidersDep,
    SocialIdentityVerifierDep,
    TokenServiceDep,
)


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
    users: UserRepositoryDep,
    hasher: PasswordHasherDep,
    tokens: TokenServiceDep,
    refresh_tokens: RefreshTokenRepositoryDep,
) -> ResetPasswordUseCase:
    return ResetPasswordUseCase(
        users=users, hasher=hasher, tokens=tokens, refresh_tokens=refresh_tokens
    )


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
    chat_messages: ChatMessageRepositoryDep,
    provider: AiChatProviderDep,
    users: UserRepositoryDep,
    daily_goals: DailyGoalRepositoryDep,
    food_entries: FoodEntryRepositoryDep,
) -> SendChatMessageUseCase:
    return SendChatMessageUseCase(
        chat_messages=chat_messages,
        provider=provider,
        users=users,
        daily_goals=daily_goals,
        food_entries=food_entries,
        history_limit=settings.chat_history_limit,
    )


def get_ai_trial_use_case(usage: AiTrialRepositoryDep) -> AiTrialUseCase:
    return AiTrialUseCase(usage=usage)


AiTrialUseCaseDep = Annotated[AiTrialUseCase, Depends(get_ai_trial_use_case)]


def get_analyze_food_image_use_case(
    vision: FoodVisionProviderDep, images: ImageStorageDep, trial: AiTrialUseCaseDep
) -> AnalyzeFoodImageUseCase:
    return AnalyzeFoodImageUseCase(vision=vision, images=images, trial=trial)


def get_analyze_food_text_use_case(
    vision: FoodVisionProviderDep, trial: AiTrialUseCaseDep
) -> AnalyzeFoodTextUseCase:
    return AnalyzeFoodTextUseCase(vision=vision, trial=trial)


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
    payments: PaymentRepositoryDep, providers: PaymentProvidersDep
) -> CreateCheckoutUseCase:
    return CreateCheckoutUseCase(
        payments=payments,
        providers=providers,
        monthly_price_vnd=settings.payos_monthly_price_vnd,
        annual_price_vnd=settings.payos_annual_price_vnd,
        return_url=settings.payos_return_url,
        cancel_url=settings.payos_cancel_url,
    )


def get_handle_payment_webhook_use_case(
    payments: PaymentRepositoryDep,
    providers: PaymentProvidersDep,
    subscriptions: SubscriptionRepositoryDep,
    users: UserRepositoryDep,
) -> HandlePaymentWebhookUseCase:
    return HandlePaymentWebhookUseCase(
        payments=payments, providers=providers, subscriptions=subscriptions, users=users
    )


def get_get_payment_status_use_case(
    payments: PaymentRepositoryDep,
    providers: PaymentProvidersDep,
    subscriptions: SubscriptionRepositoryDep,
    users: UserRepositoryDep,
) -> GetPaymentStatusUseCase:
    return GetPaymentStatusUseCase(
        payments=payments, providers=providers, subscriptions=subscriptions, users=users
    )


def get_cancel_payment_use_case(
    payments: PaymentRepositoryDep, providers: PaymentProvidersDep
) -> CancelPaymentUseCase:
    return CancelPaymentUseCase(payments=payments, providers=providers)


def get_get_my_subscription_use_case(
    subscriptions: SubscriptionRepositoryDep,
) -> GetMySubscriptionUseCase:
    return GetMySubscriptionUseCase(subscriptions=subscriptions)


def get_get_me_use_case(restaurants: RestaurantRepositoryDep) -> GetMeUseCase:
    return GetMeUseCase(restaurants=restaurants)


GetMeUseCaseDep = Annotated[GetMeUseCase, Depends(get_get_me_use_case)]


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


def get_upsert_streak_use_case(streaks: StreakRepositoryDep) -> UpsertStreakUseCase:
    return UpsertStreakUseCase(streaks=streaks)


UpsertStreakUseCaseDep = Annotated[UpsertStreakUseCase, Depends(get_upsert_streak_use_case)]


def get_get_quests_use_case(
    quests: QuestRepositoryDep, coins: CoinRepositoryDep
) -> GetQuestsUseCase:
    return GetQuestsUseCase(quests=quests, coins=coins)


def get_redeem_coins_use_case(
    coins: CoinRepositoryDep,
    bundles: CoinBundleRepositoryDep,
    subscriptions: SubscriptionRepositoryDep,
    users: UserRepositoryDep,
) -> RedeemCoinsUseCase:
    return RedeemCoinsUseCase(
        coins=coins, bundles=bundles, subscriptions=subscriptions, users=users
    )


def get_list_coin_bundles_use_case(bundles: CoinBundleRepositoryDep) -> ListCoinBundlesUseCase:
    return ListCoinBundlesUseCase(bundles=bundles)


def get_list_plans_use_case(providers: PaymentProvidersDep) -> ListPlansUseCase:
    return ListPlansUseCase(
        monthly_price_vnd=settings.payos_monthly_price_vnd,
        annual_price_vnd=settings.payos_annual_price_vnd,
        providers=list(providers),
    )


GetQuestsUseCaseDep = Annotated[GetQuestsUseCase, Depends(get_get_quests_use_case)]
RedeemCoinsUseCaseDep = Annotated[RedeemCoinsUseCase, Depends(get_redeem_coins_use_case)]
ListCoinBundlesUseCaseDep = Annotated[
    ListCoinBundlesUseCase, Depends(get_list_coin_bundles_use_case)
]
ListPlansUseCaseDep = Annotated[ListPlansUseCase, Depends(get_list_plans_use_case)]


def _quiz_rewards() -> QuizRewards:
    return QuizRewards(
        daily_per_correct=settings.quiz_daily_coins_per_correct,
        practice_per_correct=settings.quiz_practice_coins_per_correct,
        practice_daily_cap=settings.quiz_practice_daily_cap,
    )


def get_list_quiz_topics_use_case(quizzes: QuizRepositoryDep) -> ListQuizTopicsUseCase:
    return ListQuizTopicsUseCase(quizzes=quizzes)


def get_get_daily_quiz_use_case(
    quizzes: QuizRepositoryDep, coins: CoinRepositoryDep
) -> GetDailyQuizUseCase:
    return GetDailyQuizUseCase(quizzes=quizzes, coins=coins, rewards=_quiz_rewards())


def get_start_practice_quiz_use_case(
    quizzes: QuizRepositoryDep, coins: CoinRepositoryDep
) -> StartPracticeQuizUseCase:
    return StartPracticeQuizUseCase(quizzes=quizzes, coins=coins, rewards=_quiz_rewards())


def get_get_quiz_use_case(quizzes: QuizRepositoryDep, coins: CoinRepositoryDep) -> GetQuizUseCase:
    return GetQuizUseCase(quizzes=quizzes, coins=coins, rewards=_quiz_rewards())


ListQuizTopicsUseCaseDep = Annotated[ListQuizTopicsUseCase, Depends(get_list_quiz_topics_use_case)]
GetDailyQuizUseCaseDep = Annotated[GetDailyQuizUseCase, Depends(get_get_daily_quiz_use_case)]
StartPracticeQuizUseCaseDep = Annotated[
    StartPracticeQuizUseCase, Depends(get_start_practice_quiz_use_case)
]
GetQuizUseCaseDep = Annotated[GetQuizUseCase, Depends(get_get_quiz_use_case)]


def get_submit_quiz_use_case(
    quizzes: QuizRepositoryDep, coins: CoinRepositoryDep
) -> SubmitQuizUseCase:
    return SubmitQuizUseCase(quizzes=quizzes, coins=coins, rewards=_quiz_rewards())


SubmitQuizUseCaseDep = Annotated[SubmitQuizUseCase, Depends(get_submit_quiz_use_case)]


def get_create_restaurant_use_case(restaurants: RestaurantRepositoryDep) -> CreateRestaurantUseCase:
    return CreateRestaurantUseCase(restaurants=restaurants)


CreateRestaurantUseCaseDep = Annotated[CreateRestaurantUseCase, Depends(get_create_restaurant_use_case)]


def get_get_my_restaurant_use_case(restaurants: RestaurantRepositoryDep) -> GetMyRestaurantUseCase:
    return GetMyRestaurantUseCase(restaurants=restaurants)


GetMyRestaurantUseCaseDep = Annotated[GetMyRestaurantUseCase, Depends(get_get_my_restaurant_use_case)]


def get_update_my_restaurant_use_case(
    restaurants: RestaurantRepositoryDep,
) -> UpdateMyRestaurantUseCase:
    return UpdateMyRestaurantUseCase(restaurants=restaurants)


UpdateMyRestaurantUseCaseDep = Annotated[
    UpdateMyRestaurantUseCase, Depends(get_update_my_restaurant_use_case)
]


def get_upload_restaurant_image_use_case(images: ImageStorageDep) -> UploadRestaurantImageUseCase:
    return UploadRestaurantImageUseCase(images=images)


UploadRestaurantImageUseCaseDep = Annotated[
    UploadRestaurantImageUseCase, Depends(get_upload_restaurant_image_use_case)
]


def get_list_my_dishes_use_case(restaurants: RestaurantRepositoryDep) -> ListMyDishesUseCase:
    return ListMyDishesUseCase(restaurants=restaurants)


ListMyDishesUseCaseDep = Annotated[ListMyDishesUseCase, Depends(get_list_my_dishes_use_case)]


def get_create_dish_use_case(restaurants: RestaurantRepositoryDep) -> CreateDishUseCase:
    return CreateDishUseCase(restaurants=restaurants)


CreateDishUseCaseDep = Annotated[CreateDishUseCase, Depends(get_create_dish_use_case)]


def get_update_dish_use_case(restaurants: RestaurantRepositoryDep) -> UpdateDishUseCase:
    return UpdateDishUseCase(restaurants=restaurants)


UpdateDishUseCaseDep = Annotated[UpdateDishUseCase, Depends(get_update_dish_use_case)]


def get_delete_dish_use_case(restaurants: RestaurantRepositoryDep) -> DeleteDishUseCase:
    return DeleteDishUseCase(restaurants=restaurants)


DeleteDishUseCaseDep = Annotated[DeleteDishUseCase, Depends(get_delete_dish_use_case)]


def get_list_admin_restaurants_use_case(restaurants: RestaurantRepositoryDep) -> ListAdminRestaurantsUseCase:
    return ListAdminRestaurantsUseCase(restaurants=restaurants)


ListAdminRestaurantsUseCaseDep = Annotated[ListAdminRestaurantsUseCase, Depends(get_list_admin_restaurants_use_case)]


def get_get_admin_restaurant_use_case(restaurants: RestaurantRepositoryDep) -> GetAdminRestaurantUseCase:
    return GetAdminRestaurantUseCase(restaurants=restaurants)


GetAdminRestaurantUseCaseDep = Annotated[GetAdminRestaurantUseCase, Depends(get_get_admin_restaurant_use_case)]


def get_review_restaurant_use_case(restaurants: RestaurantRepositoryDep) -> ReviewRestaurantUseCase:
    return ReviewRestaurantUseCase(restaurants=restaurants)


ReviewRestaurantUseCaseDep = Annotated[ReviewRestaurantUseCase, Depends(get_review_restaurant_use_case)]


def get_review_dish_use_case(restaurants: RestaurantRepositoryDep) -> ReviewDishUseCase:
    return ReviewDishUseCase(restaurants=restaurants)


ReviewDishUseCaseDep = Annotated[ReviewDishUseCase, Depends(get_review_dish_use_case)]
