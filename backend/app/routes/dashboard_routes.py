# app/routes/dashboard_routes.py
"""
Rotas do Dashboard (Snapshot + Stream SSE).

O que este módulo faz?
- /api/dashboard/snapshot: retorna o estado atual consolidado (KPIs, alertas, eventos).
- /api/dashboard/stream: fornece atualizações em tempo real via SSE (Server-Sent Events).

Por que existe?
- Separar o "painel em tempo real" das rotas de serviços/logs.
- Permitir o frontend se manter atualizado sem polling pesado.
"""

import json
from fastapi import APIRouter, Depends, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from starlette.responses import StreamingResponse

from app.deps.dashboard_dep import get_dashboard_service
from app.services.dashboard_service import DashboardService

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/snapshot")
async def get_snapshot(svc: DashboardService = Depends(get_dashboard_service)):
    """
    Retorna um snapshot completo do dashboard.

    Observação:
    - jsonable_encoder converte datetime -> string ISO automaticamente.
    - É útil para "carregar rápido" a tela e para o botão Atualizar.
    """
    snap = await svc.snapshot()
    return JSONResponse(content=jsonable_encoder(snap))


@router.get("/stream")
async def stream(request: Request, svc: DashboardService = Depends(get_dashboard_service)):
    """
    Stream SSE (tempo real).

    Fluxo:
    - Cliente conecta
    - Envia um SNAPSHOT inicial
    - Depois envia eventos publicados pelo DashboardBroadcaster:
      • ALERTS_UPDATED
      • SERVICE_CHANGED
      • SERVER_STATUS_CHANGED
      • SNAPSHOT (se você publicar)
    """
    q = svc.bus.subscribe()

    async def event_generator():
        try:
            # 1) Snapshot inicial na conexão (cliente já renderiza na hora)
            snap = await svc.snapshot()
            yield f"event: SNAPSHOT\ndata: {json.dumps(jsonable_encoder(snap))}\n\n"

            # 2) Eventos contínuos
            while True:
                if await request.is_disconnected():
                    break

                item = await q.get()
                event = item["event"]
                data = item["data"]

                # Garante que datetime e modelos Pydantic saiam serializáveis
                yield f"event: {event}\ndata: {json.dumps(jsonable_encoder(data))}\n\n"
        finally:
            # Evita vazamento de "clientes" no broadcaster
            svc.bus.unsubscribe(q)

    return StreamingResponse(event_generator(), media_type="text/event-stream")
