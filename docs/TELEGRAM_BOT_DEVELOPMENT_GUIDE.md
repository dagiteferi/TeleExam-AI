# TeleExam AI - Telegram Bot Development & Deployment Guide (Production/Open-Source Edition)

## 1. Executive Summary
This document provides a highly scalable, production-ready specification for building the Telegram Bot frontend of the TeleExam AI platform. It is strictly designed for **open-source public repositories** capable of managing **1,000+ concurrent requests**. 

The backend (FastAPI) handles all complex state, database queries, and AI generation. This bot is strictly an **asynchronous proxy layer** built with Python `aiogram 3.x`. It translates Telegram interactions into HTTP REST calls.

**CRITICAL RULE:** Do not build admin tools in this bot. Administrative control is reserved exclusively for the standalone Web Admin panel.

## 2. Security & Open-Source Readiness
Because the repository will be hosted publicly on GitHub, no hardcoded secrets or identifiable API endpoints should ever be committed.

1. **Environment Variables Only**: All configuration must load from `.env`.
2. **`.gitignore`**: Must strictly ignore `.env`, `.venv`, `__pycache__`, and `logs/`.
3. **`.env.example`**: Tracked in git, displaying empty template variables.

**.env.example**
```env
BOT_TOKEN=
BACKEND_BASE_URL=
BACKEND_SECRET=
WEBHOOK_URL=
WEBHOOK_PATH=/webhook
```

## 3. High-Performance Modular Architecture
To support intense concurrency (1,000+ users), the bot must be entirely async, utilizing connection pools, singletons, and router segregation. 

### Folder Structure
```text
telegram-bot/
├── .env.example
├── .gitignore
├── requirements.txt
├── pytest.ini
├── run.py                 
├── bot/
│   ├── __init__.py
│   ├── config.py          
│   ├── middlewares/       
│   │   ├── auth.py        
│   │   └── throttler.py   
│   ├── services/          
│   │   └── api_client.py  
│   ├── handlers/          
│   │   ├── start.py       
│   │   ├── exam.py        
│   │   └── ai.py          
│   ├── keyboards/         
│   │   ├── reply.py       
│   │   └── inline.py      
│   ├── states/            
│   │   └── exam_state.py  
├── tests/
│   ├── conftest.py
│   └── test_handlers.py
```

## 4. Production Code Guidance & Snippets

### A. The Backend API Client (`bot/services/api_client.py`)
To prevent socket exhaustion under massive load, use a single `aiohttp.ClientSession` across the bot's lifecycle.

```python
import aiohttp
from typing import Any, Dict
from bot.config import settings

class APIClient:
    _session: aiohttp.ClientSession | None = None

    @classmethod
    async def get_session(cls) -> aiohttp.ClientSession:
        if cls._session is None or cls._session.closed:
            cls._session = aiohttp.ClientSession(
                base_url=settings.BACKEND_BASE_URL,
                headers={"X-Telegram-Secret": settings.BACKEND_SECRET}
            )
        return cls._session

    @classmethod
    async def post(cls, endpoint: str, user_id: int, payload: Dict[str, Any] = None) -> Dict[str, Any]:
        session = await cls.get_session()
        headers = {"X-Telegram-Id": str(user_id)}
        async with session.post(endpoint, json=payload, headers=headers) as response:
            response.raise_for_status()
            return await response.json()

    @classmethod
    async def get(cls, endpoint: str, user_id: int, params: Dict[str, Any] = None) -> Dict[str, Any]:
        session = await cls.get_session()
        headers = {"X-Telegram-Id": str(user_id)}
        async with session.get(endpoint, params=params, headers=headers) as response:
            response.raise_for_status()
            return await response.json()
```

### B. Auto-Upsert Middleware (`bot/middlewares/auth.py`)
Intercept updates globally to ensure the user exists in the backend before handling commands.

```python
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
from typing import Callable, Dict, Any, Awaitable
from bot.services.api_client import APIClient

class AuthMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message | CallbackQuery,
        data: Dict[str, Any]
    ) -> Any:
        user = event.from_user
        if not user:
            return await handler(event, data)
            
        payload = {
            "telegram_id": user.id,
            "telegram_username": user.username,
            "first_name": user.first_name,
            "last_name": user.last_name
        }
        
        await APIClient.post("/api/users/upsert", user_id=user.id, payload=payload)
        return await handler(event, data)
```

### C. Async Endpoint Examples (`bot/handlers/exam.py`)
Clean, callback-driven interaction for the exam loop passing the crucial `qtoken`.

```python
from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext
from bot.services.api_client import APIClient
from bot.keyboards.inline import build_question_keyboard

router = Router()

@router.callback_query(F.data.startswith("start_exam_"))
async def start_exam(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    res = await APIClient.post("/api/sessions/start", user_id=user_id, payload={"mode": "exam"})
    await state.update_data(session_id=res["session_id"])
    
    await serve_next_question(callback, state)

async def serve_next_question(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    data = await state.get_data()
    
    q_data = await APIClient.get(f"/api/sessions/{data['session_id']}/question", user_id=user_id)
    await state.update_data(qtoken=q_data["qtoken"])
    
    kb = build_question_keyboard(q_data["choices"])
    await callback.message.edit_text(q_data["prompt"], reply_markup=kb)

@router.callback_query(F.data.startswith("answer_"))
async def handle_answer(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    data = await state.get_data()
    selected = callback.data.split("_")[1]
    
    await APIClient.post(
        f"/api/sessions/{data['session_id']}/answer",
        user_id=user_id,
        payload={"qtoken": data["qtoken"], "answer": selected}
    )
    
    await APIClient.post(f"/api/sessions/{data['session_id']}/next", user_id=user_id)
    await serve_next_question(callback, state)
```

## 5. Testing Framework (`pytest`)
High-quality code mandates testing. Because the bot is decoupled via `APIClient`, we mock network calls.

```python
# tests/test_handlers.py
from unittest.mock import patch, AsyncMock
from bot.handlers.exam import start_exam

@patch("bot.services.api_client.APIClient.post", new_callable=AsyncMock)
async def test_start_exam(mock_post, mock_callback, mock_fsm_context):
    mock_post.return_value = {"session_id": "test_uuid_123"}
    
    await start_exam(mock_callback, mock_fsm_context)
    
    mock_post.assert_awaited_once_with("/api/sessions/start", user_id=mock_callback.from_user.id, payload={"mode": "exam"})
    mock_fsm_context.update_data.assert_awaited_with(session_id="test_uuid_123")
```

## 6. Deplyoment (High Speed / 100% Free)
Use **Render** Web Service (Free Tier) with `aiogram`'s Webhook configuration. Do **NOT** use `bot.start_polling()` in production; Webhooks are necessary for horizontally scaling traffic reliably.

**`run.py`**
```python
from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from bot.config import settings
from bot.handlers import start, exam, ai
from bot.services.api_client import APIClient

bot = Bot(token=settings.BOT_TOKEN, parse_mode="HTML")
dp = Dispatcher()

dp.include_routers(start.router, exam.router, ai.router)

async def on_startup(bot: Bot):
    await bot.set_webhook(f"{settings.WEBHOOK_URL}{settings.WEBHOOK_PATH}")

async def on_shutdown(bot: Bot):
    await bot.delete_webhook()
    session = await APIClient.get_session()
    await session.close()

dp.startup.register(on_startup)
dp.shutdown.register(on_shutdown)

app = web.Application()
SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=settings.WEBHOOK_PATH)
setup_application(app, dp, bot=bot)

if __name__ == "__main__":
    web.run_app(app, host="0.0.0.0", port=8080)
```
- By booting an `aiohttp` web server (like Express), Render.com recognizes the bot as an active web dependency and port-binds it.
- **Cost**: $0.00/month.
- **Speed**: Webhook push-delivery reduces latency drastically over standard sequential GET polling.
