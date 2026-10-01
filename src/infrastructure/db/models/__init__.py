"""Importing this package registers every table on ``Base.metadata``.

Alembic and ``create_all`` depend on that, so any new model must be added here.
"""

from src.infrastructure.db.models.activity_log_model import ActivityLogORM
from src.infrastructure.db.models.ai_trial_usage_model import AiTrialUsageORM
from src.infrastructure.db.models.chat_message_model import ChatMessageORM
from src.infrastructure.db.models.coin_transaction_model import CoinTransactionORM
from src.infrastructure.db.models.daily_goal_model import DailyGoalORM
from src.infrastructure.db.models.food_entry_model import FoodEntryORM, IngredientORM
from src.infrastructure.db.models.payment_model import PaymentORM
from src.infrastructure.db.models.quest_definition_model import QuestDefinitionORM
from src.infrastructure.db.models.quest_model import QuestORM
from src.infrastructure.db.models.refresh_token_model import RefreshTokenORM
from src.infrastructure.db.models.social_identity_model import SocialIdentityORM
from src.infrastructure.db.models.streak_model import StreakORM
from src.infrastructure.db.models.subscription_model import SubscriptionORM
from src.infrastructure.db.models.user_model import UserORM
from src.infrastructure.db.models.water_log_model import WaterLogORM
from src.infrastructure.db.models.weight_log_model import WeightLogORM

__all__ = [
    "ActivityLogORM",
    "AiTrialUsageORM",
    "ChatMessageORM",
    "CoinTransactionORM",
    "DailyGoalORM",
    "FoodEntryORM",
    "IngredientORM",
    "PaymentORM",
    "QuestDefinitionORM",
    "QuestORM",
    "RefreshTokenORM",
    "SocialIdentityORM",
    "StreakORM",
    "SubscriptionORM",
    "UserORM",
    "WaterLogORM",
    "WeightLogORM",
]
