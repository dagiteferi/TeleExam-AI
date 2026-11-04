"""
Free trial of Review My Mistakes.

Free users can see their newest FREE_VISIBLE_MISTAKES wrong questions, retry
FREE_TRIES of them ("Try again") and get FREE_AI_EXPLANATIONS AI explanation(s).
These are lifetime allowances (not daily); after that, PRO is required.
"""
from __future__ import annotations

from redis.asyncio import Redis

FREE_VISIBLE_MISTAKES = 3
FREE_TRIES = 3
FREE_AI_EXPLANATIONS = 1

_TRY_KEY = "teleexam:mistakes_trial:try:{telegram_id}"
_AI_KEY = "teleexam:mistakes_trial:ai:{telegram_id}"


def _left(used: str | int | None, limit: int) -> int:
    return max(0, limit - int(used or 0))


async def trial_left(redis: Redis, telegram_id: int) -> tuple[int, int]:
    """(tries left, AI explanations left) for a free user."""
    tries_used, ai_used = await redis.mget(
        _TRY_KEY.format(telegram_id=telegram_id), _AI_KEY.format(telegram_id=telegram_id)
    )
    return _left(tries_used, FREE_TRIES), _left(ai_used, FREE_AI_EXPLANATIONS)


async def _consume(redis: Redis, key: str, limit: int) -> bool:
    """Atomically uses one; False (and nothing used) once the limit is reached."""
    used = await redis.incr(key)
    if used > limit:
        await redis.decr(key)
        return False
    return True


async def consume_try(redis: Redis, telegram_id: int) -> bool:
    return await _consume(redis, _TRY_KEY.format(telegram_id=telegram_id), FREE_TRIES)


async def refund_try(redis: Redis, telegram_id: int) -> None:
    await redis.decr(_TRY_KEY.format(telegram_id=telegram_id))


async def consume_ai(redis: Redis, telegram_id: int) -> bool:
    return await _consume(redis, _AI_KEY.format(telegram_id=telegram_id), FREE_AI_EXPLANATIONS)


async def refund_ai(redis: Redis, telegram_id: int) -> None:
    """Gives the trial explanation back when the AI failed to produce one."""
    await redis.decr(_AI_KEY.format(telegram_id=telegram_id))
