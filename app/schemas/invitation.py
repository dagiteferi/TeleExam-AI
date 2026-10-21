from __future__ import annotations

import math
from datetime import datetime
from pydantic import BaseModel, Field


class InvitationRuleConfig(BaseModel):
    # ── Exam Years Unlock Rules ──
    free_years: int = Field(
        default=1,
        ge=0,
        description="Number of oldest exam years available for free (with 0 invites required).",
    )
    invites_per_year: int = Field(
        default=1,
        ge=1,
        description="Number of invites required to unlock one additional exam year.",
    )
    years_per_invite: int = Field(
        default=1,
        ge=1,
        description="Number of exam years unlocked by each invite (if 1 invite opens multiple years).",
    )
    invites_to_unlock_all_years: int = Field(
        default=4,
        ge=0,
        description="Total invites required to unlock ALL exam years in a department.",
    )

    # ── Courses Unlock Rules ──
    free_courses_ratio: float = Field(
        default=0.25,
        ge=0.0,
        le=1.0,
        description="Proportion of courses unlocked for free by default (0.25 = 25%).",
    )
    invites_to_unlock_all_courses: int = Field(
        default=4,
        ge=0,
        description="Total invites required to unlock all courses.",
    )

    # ── Universal Threshold ──
    invites_to_unlock_all: int = Field(
        default=4,
        ge=0,
        description="Universal invite threshold that unlocks all locked exam years and courses.",
    )

    # ── Extra Referral Rewards ──
    ai_bonus_per_invite: int = Field(
        default=0,
        ge=0,
        description="Extra daily free AI explanations granted per invite.",
    )

    def is_all_unlocked(self, invite_count: int) -> bool:
        """True if user has reached the universal threshold or years threshold."""
        return (
            invite_count >= self.invites_to_unlock_all
            or invite_count >= self.invites_to_unlock_all_years
        )

    def calculate_unlocked_years_count(self, invite_count: int, total_years: int) -> int:
        """Calculates total count of exam years allowed for this invite count."""
        if total_years <= 0:
            return 0
        if self.is_all_unlocked(invite_count):
            return total_years

        if self.years_per_invite > 1:
            extra_years = invite_count * self.years_per_invite
        else:
            extra_years = invite_count // self.invites_per_year

        return min(total_years, self.free_years + extra_years)

    def calculate_allowed_years(
        self,
        all_years_sorted_asc: list[int],
        invite_count: int,
        fully_unlocked: bool = False,
    ) -> list[int]:
        """Returns the list of year integers that the user is permitted to access."""
        if fully_unlocked or self.is_all_unlocked(invite_count):
            return list(all_years_sorted_asc)

        unlocked_count = self.calculate_unlocked_years_count(
            invite_count=invite_count,
            total_years=len(all_years_sorted_asc),
        )
        return all_years_sorted_asc[:unlocked_count]

    def calculate_required_invites_for_year(
        self,
        year: int,
        all_years_sorted_asc: list[int],
    ) -> int:
        """Calculates how many total invites are needed to unlock a specific year."""
        if year not in all_years_sorted_asc:
            return min(self.invites_to_unlock_all, self.invites_to_unlock_all_years)

        year_index = all_years_sorted_asc.index(year)
        # If year falls within the free tier, no invites are required
        if year_index < self.free_years:
            return 0

        # Number of additional years beyond the free tier (1-based index among locked years)
        additional_year_number = year_index + 1 - self.free_years

        if self.years_per_invite > 1:
            needed = math.ceil(additional_year_number / self.years_per_invite)
        else:
            needed = additional_year_number * self.invites_per_year

        max_limit = min(self.invites_to_unlock_all, self.invites_to_unlock_all_years)
        return min(needed, max_limit)

    def calculate_unlocked_courses_count(
        self,
        invite_count: int,
        total_courses: int,
        fully_unlocked: bool = False,
    ) -> int:
        """Calculates how many courses are unlocked for this user."""
        if total_courses <= 0:
            return 0
        unlock_threshold = min(self.invites_to_unlock_all, self.invites_to_unlock_all_courses)
        if fully_unlocked or invite_count >= unlock_threshold:
            return total_courses

        base_unlocked = max(1, int(total_courses * self.free_courses_ratio))
        remaining_to_unlock = total_courses - base_unlocked
        if unlock_threshold <= 0:
            return total_courses

        extra_unlocked_per_invite = remaining_to_unlock / unlock_threshold
        unlocked = base_unlocked + int(invite_count * extra_unlocked_per_invite)
        return min(total_courses, max(base_unlocked, unlocked))

    def calculate_ai_daily_limit(self, invite_count: int, base_limit: int = 5) -> int:
        """Calculates daily free AI quota including bonus for invites."""
        return base_limit + max(0, invite_count * self.ai_bonus_per_invite)

    def get_summary(self) -> str:
        """Generates human-readable summary of the active rules."""
        if self.years_per_invite > 1:
            year_rule = f"1 invite unlocks {self.years_per_invite} exam years"
        elif self.invites_per_year > 1:
            year_rule = f"{self.invites_per_year} invites unlock 1 exam year"
        else:
            year_rule = "1 invite unlocks 1 exam year"

        free_rule = (
            f"{self.free_years} oldest year(s) free by default"
            if self.free_years > 0
            else "0 free years"
        )
        all_rule = f"{self.invites_to_unlock_all} invites unlock all content"

        perks = []
        if self.ai_bonus_per_invite > 0:
            perks.append(f"+{self.ai_bonus_per_invite} daily AI explanations/invite")

        perks_summary = f"; Rewards: {', '.join(perks)}" if perks else ""
        return f"{year_rule}; {free_rule}; {all_rule}{perks_summary}."


class InvitationRuleUpdate(BaseModel):
    free_years: int | None = Field(default=None, ge=0)
    invites_per_year: int | None = Field(default=None, ge=1)
    years_per_invite: int | None = Field(default=None, ge=1)
    invites_to_unlock_all_years: int | None = Field(default=None, ge=0)
    free_courses_ratio: float | None = Field(default=None, ge=0.0, le=1.0)
    invites_to_unlock_all_courses: int | None = Field(default=None, ge=0)
    invites_to_unlock_all: int | None = Field(default=None, ge=0)
    ai_bonus_per_invite: int | None = Field(default=None, ge=0)


class InvitationRuleResponse(InvitationRuleConfig):
    summary: str
    updated_at: datetime | None = None
