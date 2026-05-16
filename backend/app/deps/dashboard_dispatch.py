# app/deps/dashboard_dispatch.py
"""
Helpers para executar coroutines do DashboardService a partir de rotas sync.

Contexto:
- Rotas `def` executam em threadpool.
- DashboardService é async (usa asyncio.Lock, publish SSE, etc).
- Então precisamos agendar a coroutine no loop principal do FastAPI.
"""

from __future__ import annotations

import asyncio
from typing import Awaitable, Any
from fastapi import Request


def fire_and_forget(request: Request, coro: Awaitable[Any]) -> None:
    """
    Agenda uma coroutine no event loop principal do FastAPI.

    - Funciona mesmo quando chamado dentro de uma rota sync.
    - Nunca quebra o fluxo da rota.
    - Se o loop não estiver disponível, simplesmente não faz nada.

    Requisito:
    - `request.app.state.loop` deve existir e apontar para o loop principal.
    """
    loop = getattr(request.app.state, "loop", None)
    if loop is None:
        return

    try:
        asyncio.run_coroutine_threadsafe(coro, loop)
    except Exception:
        # regra: dashboard nunca pode derrubar a operação principal
        pass
