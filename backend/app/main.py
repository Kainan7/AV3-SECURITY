# app/main.py
"""
Main / Bootstrap do FastAPI
==========================

O que é:
- Ponto de entrada do backend.
- Registra middlewares, rotas, dependências globais (app.state) e lifecycle
  (startup/shutdown).

Por que existe:
- Centraliza tudo que precisa ser inicializado UMA vez:
  - thread de auditoria (fila + consumer)
  - dashboard service em memória (SSE)
  - loop de eventos para fire_and_forget (quando rota é sync)
"""

import asyncio

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# -------------------------------------------------
# Rotas (controllers)
# -------------------------------------------------
from app.routes.auth_routes import router as auth_router
from app.routes.server_routes import router as server_router
from app.routes.logs_routes import router as logs_router
from app.routes.dashboard_routes import router as dashboard_router

# -------------------------------------------------
# Auditoria (fila + persistência)
# -------------------------------------------------
from app.audit.threads import BarramentoAuditoria
from app.audit.modelos import EventoAuditoria
from app.audit.persistencia import persistir_evento

# -------------------------------------------------
# Services globais (estado em memória)
# -------------------------------------------------
from app.services.dashboard_service import DashboardService
from app.services.server_service import ServerService  # usado para seed inicial do dashboard

# -------------------------------------------------
# Instância do app
# -------------------------------------------------
app = FastAPI(title="RESTART-SERVER API")


# -------------------------------------------------
# CORS (frontend Vite)
# -------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# -------------------------------------------------
# Handler do worker de auditoria
# -------------------------------------------------
def handler_auditoria(evento: EventoAuditoria) -> None:
    """
    Handler chamado pela thread consumidora do BarramentoAuditoria.

    O que faz:
    - Recebe 1 EventoAuditoria da fila
    - Persiste em JSONL (um arquivo por dia) via persistir_evento(...)

    Por que:
    - Mantém I/O fora das rotas (rotas não travam por escrever em disco).
    """
    persistir_evento(evento)


# -------------------------------------------------
# Ciclo de vida: startup
# -------------------------------------------------
@app.on_event("startup")
async def startup() -> None:
    """
    Startup do app.

    O que é inicializado:
    1) app.state.audit_bus -> thread + fila do barramento de auditoria
    2) app.state.dashboard_service -> estado do dashboard em memória
    3) app.state.loop -> referência do event loop (para fire_and_forget)
    4) seed inicial do dashboard com SERV 01..06 (evita KPI=0 no início)
    """

    # 1) Auditoria: cria barramento e inicia worker
    app.state.audit_bus = BarramentoAuditoria(handler=handler_auditoria)
    app.state.audit_bus.iniciar()

    # 2) Dashboard: cria serviço em memória (SSE)
    app.state.dashboard_service = DashboardService()

    # 3) Guarda o loop atual (necessário para disparar coroutines a partir de rotas sync)
    app.state.loop = asyncio.get_running_loop()

    # 4) Seed inicial do dashboard com lista de servidores
    #    (assim o dashboard já nasce com total/online/offline/unknown coerente)
    try:
        servidores = ServerService.listar_servidores()
        for s in servidores:
            # normaliza "desconhecido" -> "unknown" (padrão do dashboard)
            status = s.status
            if status == "desconhecido":
                status = "unknown"

            # registra status no dashboard state
            await app.state.dashboard_service.set_server_status(s.id, status)

    except Exception:
        # não derruba o startup se algo der errado no seed
        pass


# -------------------------------------------------
# Ciclo de vida: shutdown
# -------------------------------------------------
@app.on_event("shutdown")
def shutdown() -> None:
    """
    Shutdown do app.

    O que faz:
    - Para a thread do barramento de auditoria com join,
      para encerrar limpo.
    """
    bus = getattr(app.state, "audit_bus", None)
    if bus:
        bus.parar()


# -------------------------------------------------
# Registro das rotas
# -------------------------------------------------
app.include_router(auth_router)
app.include_router(server_router)
app.include_router(logs_router)
app.include_router(dashboard_router)
