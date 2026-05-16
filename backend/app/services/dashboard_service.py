# app/services/dashboard_service.py
"""
DashboardService — estado em memória + eventos SSE.

O que este serviço faz?
- Mantém um "estado do dashboard" em memória:
  - status dos servidores (online/offline/unknown)
  - status de serviços por servidor
  - lista de alertas ativos (derivados do estado)
  - eventos recentes (start/stop/restart/status_change/erro)
- Fornece um snapshot consolidado (GET /api/dashboard/snapshot)
- Publica eventos via SSE (GET /api/dashboard/stream)

Por que isso existe?
- Dashboard precisa "tempo real" sem banco por enquanto.
- Evita I/O e mantém as rotas rápidas (tudo em RAM).
- SSE permite múltiplos clientes conectados recebendo updates.
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List

from app.models.schemas import (
    DashboardAlert,
    DashboardKpis,
    DashboardSnapshot,
    ServiceEvent,
    ServerStatusChanged,
)


# =========================================================
# Broadcaster SSE (multi-client)
# =========================================================
class DashboardBroadcaster:
    """
    Broadcaster simples para SSE.

    Como funciona:
    - Cada cliente SSE recebe uma asyncio.Queue própria (subscribe()).
    - publish(event, data) coloca um payload em todas as filas.
    - Se alguma fila estiver cheia (cliente lento), o cliente é removido (unsubscribe).

    Motivo:
    - Evitar travar o servidor por cliente lento.
    - Permitir múltiplos dashboards abertos ao mesmo tempo.
    """

    def __init__(self):
        self._clients: List[asyncio.Queue] = []

    def subscribe(self) -> asyncio.Queue:
        """Cria uma fila para um novo cliente SSE e registra na lista."""
        q: asyncio.Queue = asyncio.Queue(maxsize=200)
        self._clients.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue):
        """Remove um cliente SSE (fila) do broadcaster."""
        if q in self._clients:
            self._clients.remove(q)

    async def publish(self, event: str, data: Any):
        """
        Publica um evento para todos os clientes.

        Payload padrão:
          { "event": <event>, "data": <data> }

        Observação:
        - Usa put_nowait() para não bloquear.
        - Se o cliente estiver lento e a fila encher, removemos o cliente.
        """
        payload = {"event": event, "data": data}
        for q in list(self._clients):
            try:
                q.put_nowait(payload)
            except asyncio.QueueFull:
                self.unsubscribe(q)


# =========================================================
# Estado do Dashboard (memória)
# =========================================================
@dataclass
class DashboardState:
    """
    Estrutura de estado em memória.

    servers:
      { "1": "online", "2": "offline", ... }

    services:
      { "1": { "Spooler": "running", "W32Time": "stopped", ... }, ... }

    alerts:
      Lista de alertas derivados do estado (recalc)

    recent_events:
      Lista ordenada por tempo (mais recente primeiro)
    """
    servers: Dict[str, str] = field(default_factory=dict)
    services: Dict[str, Dict[str, str]] = field(default_factory=dict)
    alerts: List[DashboardAlert] = field(default_factory=list)
    recent_events: List[ServiceEvent] = field(default_factory=list)
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class DashboardService:
    """
    Serviço central do Dashboard.

    Thread-safety / concorrência:
    - Usa asyncio.Lock para garantir consistência:
      qualquer update no estado recalcula alertas e publica SSE de forma coesa.
    """

    def __init__(self):
        self.bus = DashboardBroadcaster()
        self.state = DashboardState()
        self._lock = asyncio.Lock()

    def _now(self) -> datetime:
        """Retorna timestamp UTC atual."""
        return datetime.now(timezone.utc)

    def _recalc_alerts(self):
        """
        Recalcula alertas ativos com base no estado atual.

        Regras atuais:
        - Servidor offline => CRITICAL
        - Servidor unknown => WARNING
        - Serviço crítico parado => WARNING
        """
        now = self._now()
        alerts: List[DashboardAlert] = []

        # Alertas por status de servidor
        for sid, st in self.state.servers.items():
            if st == "offline":
                alerts.append(
                    DashboardAlert(
                        nivel="CRITICAL",
                        mensagem=f"SERV {sid} está OFFLINE",
                        server_id=sid,
                        ts=now,
                    )
                )
            elif st == "unknown":
                alerts.append(
                    DashboardAlert(
                        nivel="WARNING",
                        mensagem=f"Status DESCONHECIDO em SERV {sid}",
                        server_id=sid,
                        ts=now,
                    )
                )

        # Alertas por serviços críticos parados
        for sid, svc_map in self.state.services.items():
            for name, st in svc_map.items():
                if st == "stopped" and name.lower() in ("sql server", "postgres", "database", "adws"):
                    alerts.append(
                        DashboardAlert(
                            nivel="WARNING",
                            mensagem=f"Serviço crítico {name} está parado em SERV {sid}",
                            server_id=sid,
                            service_name=name,
                            ts=now,
                        )
                    )

        self.state.alerts = alerts

    def _build_snapshot(self) -> DashboardSnapshot:
        """
        Monta um snapshot consolidado do estado atual.
        Usado por:
        - GET /api/dashboard/snapshot
        - evento SSE "SNAPSHOT"

        Obs:
        - recent_events já é truncado para 20.
        """
        total = len(self.state.servers)
        online = sum(1 for s in self.state.servers.values() if s == "online")
        offline = sum(1 for s in self.state.servers.values() if s == "offline")
        unknown = sum(1 for s in self.state.servers.values() if s == "unknown")

        return DashboardSnapshot(
            kpis=DashboardKpis(total=total, online=online, offline=offline, unknown=unknown),
            alerts=self.state.alerts,
            recent_events=self.state.recent_events[:20],
            updated_at=self.state.updated_at,
        )

    async def snapshot(self) -> DashboardSnapshot:
        """
        Retorna snapshot atual com lock para evitar leitura no meio de uma escrita.
        """
        async with self._lock:
            return self._build_snapshot()

    async def _publish_full(self):
        """
        Publica eventos SSE "completos" após qualquer alteração no estado.

        Eventos emitidos:
        - ALERTS_UPDATED: lista de alertas (já serializada)
        - SNAPSHOT: snapshot completo (serializado)

        Motivo:
        - simplificar o frontend: ele pode sempre confiar no SNAPSHOT atualizado
          e também receber um delta de alertas.
        """
        await self.bus.publish("ALERTS_UPDATED", [a.model_dump() for a in self.state.alerts])
        await self.bus.publish("SNAPSHOT", self._build_snapshot().model_dump())

    # =========================================================
    # Atualizações REAL do estado (chamadas pelas rotas)
    # =========================================================
    async def set_server_status(self, server_id: str, new_status: str):
        """
        Atualiza status de um servidor.
        - Se mudou: emite SERVER_STATUS_CHANGED
        - Sempre: recalcula alertas + atualiza updated_at + publica snapshot
        """
        async with self._lock:
            now = self._now()
            old = self.state.servers.get(server_id, "unknown")

            if old != new_status:
                self.state.servers[server_id] = new_status
                await self.bus.publish(
                    "SERVER_STATUS_CHANGED",
                    ServerStatusChanged(
                        server_id=server_id,
                        from_status=old,       # type: ignore
                        to_status=new_status,  # type: ignore
                        ts=now,
                    ).model_dump(),
                )

            self._recalc_alerts()
            self.state.updated_at = now
            await self._publish_full()

    async def set_services_snapshot(self, server_id: str, services_map: Dict[str, str]):
        """
        Atualiza o snapshot inteiro de serviços de um servidor.
        - Substitui o dict atual daquele server_id
        - Recalcula alertas + atualiza updated_at + publica snapshot
        """
        async with self._lock:
            now = self._now()
            self.state.services[server_id] = services_map
            self._recalc_alerts()
            self.state.updated_at = now
            await self._publish_full()

    async def record_service_action(
        self,
        server_id: str,
        service_name: str,
        action: str,
        status: str,
        message: str,
    ):
        """
        Registra uma ação de serviço (START/STOP/RESTART/ERROR/STATUS_CHANGE).

        Efeitos:
        - Atualiza status do serviço dentro do estado (services[server_id][service_name])
        - Insere evento no topo de recent_events
        - Emite SERVICE_CHANGED para SSE (delta)
        - Recalcula alertas + publica snapshot completo

        Obs:
        - recent_events cresce, mas snapshot e frontend limitam visualização.
        """
        async with self._lock:
            now = self._now()

            if server_id not in self.state.services:
                self.state.services[server_id] = {}
            self.state.services[server_id][service_name] = status

            evt = ServiceEvent(
                server_id=server_id,
                service_name=service_name,
                acao=action,    # type: ignore
                status=status,  # type: ignore
                ts=now,
                mensagem=message,
            )
            self.state.recent_events.insert(0, evt)

            # Evento delta para atualizar frontend sem depender só do SNAPSHOT
            await self.bus.publish("SERVICE_CHANGED", evt.model_dump())

            self._recalc_alerts()
            self.state.updated_at = now
            await self._publish_full()
