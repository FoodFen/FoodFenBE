"""Use case: the admin users table. Filter by effective tier and search text, then page."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from src.application.account_status import is_premium_today, shown_streak
from src.application.dish_fit import fold
from src.application.dtos.admin import AdminUserListDTO, AdminUserRowDTO
from src.application.ports.admin_stats_repository import AdminStatsRepositoryProtocol
from src.application.use_cases.get_admin_dashboard import VIETNAM
from src.domain.enums import SubscriptionTier


@dataclass
class ListAdminUsersUseCase:
    stats: AdminStatsRepositoryProtocol

    async def execute(
        self,
        q: str | None,
        tier: SubscriptionTier | None,
        offset: int = 0,
        limit: int = 20,
        today: date | None = None,
    ) -> AdminUserListDTO:
        """Newest first (id breaks ties), filter, then slice ``[offset, offset + limit)``."""
        today = today or datetime.now(VIETNAM).date()
        needle = fold(q.strip()) if q else ""
        # ponytail: every user + subscription + streak is loaded and filtered in memory; move to SQL
        # when the user count makes it slow (same ceiling as GET /dishes).
        accounts = sorted(await self.stats.accounts(), key=lambda a: (a[0].created_at, a[0].id), reverse=True)
        rows = [
            AdminUserRowDTO(
                id=u.id,
                display_name=u.name,
                email=u.email,
                role=u.role,
                tier=SubscriptionTier.PREMIUM if is_premium_today(u, s, today) else SubscriptionTier.FREE,
                streak=shown_streak(k, today),
                created_at=u.created_at,
                is_active=u.is_active,
            )
            for u, s, k in accounts
        ]
        shown = [
            r for r in rows
            if (tier is None or r.tier == tier)
            and (not needle or needle in fold(r.display_name or "") or needle in fold(r.email))
        ]
        end = offset + limit
        return AdminUserListDTO(
            users=shown[offset:end], total=len(shown), next_cursor=str(end) if end < len(shown) else None
        )
