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
    max_invite_years: int = Field(
        default=1,
        ge=0,
        description="Maximum extra exam years invites can unlock beyond the free ones; the rest require PRO.",
    )

    # ── Courses Unlock Rules ──
    free_courses_ratio: float = Field(
        default=0.25,
        ge=0.0,
        le=1.0,
        description="Proportion of courses unlocked for free by default (0.25 = 25%).",
    )
    courses_per_invite: int = Field(
        default=1,
        ge=1,
        description="Number of extra courses unlocked by each invite.",
    )

    # ── Extra Referral Rewards ──
    ai_bonus_per_invite: int = Field(
        default=0,
        ge=0,
        description="Extra daily free AI explanations granted per invite.",
    )

    # Invites never unlock everything: at most max_invite_years extra years, never the
    # newest year, and never the last course. Full access requires payment.

    def _year_invite_cap(self, total_years: int) -> int:
        """Max years a non-PRO user can ever reach (free years stay free even if they cover all years)."""
        free = min(self.free_years, total_years)
        return max(free, min(total_years - 1, free + self.max_invite_years))

    def calculate_unlocked_years_count(self, invite_count: int, total_years: int) -> int:
        """Calculates total count of exam years allowed for this invite count."""
        if total_years <= 0:
            return 0
        free = min(self.free_years, total_years)
        if self.years_per_invite > 1:
            extra_years = invite_count * self.years_per_invite
        else:
            extra_years = invite_count // self.invites_per_year
        return max(free, min(self._year_invite_cap(total_years), free + extra_years))

    def calculate_allowed_years(
        self,
        all_years_sorted_asc: list[int],
        invite_count: int,
        fully_unlocked: bool = False,
    ) -> list[int]:
        """Returns the list of year integers that the user is permitted to access."""
        if fully_unlocked:
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
    ) -> int | None:
        """Total invites needed to unlock a specific year; None means PRO-only."""
        if year not in all_years_sorted_asc:
            return None

        year_index = all_years_sorted_asc.index(year)
        if year_index < self.free_years:
            return 0
        if year_index >= self._year_invite_cap(len(all_years_sorted_asc)):
            return None

        # Number of additional years beyond the free tier (1-based index among locked years)
        additional_year_number = year_index + 1 - self.free_years

        if self.years_per_invite > 1:
            return math.ceil(additional_year_number / self.years_per_invite)
        return additional_year_number * self.invites_per_year

    def _free_courses_count(self, total_courses: int) -> int:
        return min(total_courses, max(1, int(total_courses * self.free_courses_ratio)))

    def _course_invite_cap(self, total_courses: int) -> int:
        return max(self._free_courses_count(total_courses), total_courses - 1)

    def calculate_unlocked_courses_count(
        self,
        invite_count: int,
        total_courses: int,
        fully_unlocked: bool = False,
    ) -> int:
        """Calculates how many courses are unlocked for this user."""
        if total_courses <= 0:
            return 0
        if fully_unlocked:
            return total_courses
        base = self._free_courses_count(total_courses)
        return min(self._course_invite_cap(total_courses), base + invite_count * self.courses_per_invite)

    def calculate_required_invites_for_course(self, course_index: int, total_courses: int) -> int | None:
        """Total invites needed to unlock the course at this position; None means PRO-only."""
        base = self._free_courses_count(total_courses)
        if course_index < base:
            return 0
        if course_index >= self._course_invite_cap(total_courses):
            return None
        return math.ceil((course_index + 1 - base) / self.courses_per_invite)

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
        year_rule += f" (max {self.max_invite_years} extra year(s) by invites)"

        free_rule = (
            f"{self.free_years} oldest year(s) free by default"
            if self.free_years > 0
            else "0 free years"
        )
        course_rule = (
            f"{round(self.free_courses_ratio * 100)}% of courses free, "
            f"+{self.courses_per_invite} course(s) per invite"
        )
        all_rule = "newest year and full access require PRO"

        perks = []
        if self.ai_bonus_per_invite > 0:
            perks.append(f"+{self.ai_bonus_per_invite} daily AI explanations/invite")

        perks_summary = f"; Rewards: {', '.join(perks)}" if perks else ""
        return f"{year_rule}; {free_rule}; {course_rule}; {all_rule}{perks_summary}."


class InvitationRuleUpdate(BaseModel):
    free_years: int | None = Field(default=None, ge=0)
    invites_per_year: int | None = Field(default=None, ge=1)
    years_per_invite: int | None = Field(default=None, ge=1)
    max_invite_years: int | None = Field(default=None, ge=0)
    free_courses_ratio: float | None = Field(default=None, ge=0.0, le=1.0)
    courses_per_invite: int | None = Field(default=None, ge=1)
    ai_bonus_per_invite: int | None = Field(default=None, ge=0)


class InvitationRuleResponse(InvitationRuleConfig):
    summary: str
    updated_at: datetime | None = None
