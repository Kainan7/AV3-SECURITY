# app/models/schemas.py
"""
Schemas (Pydantic Models)
========================

O que é:
- Modelos Pydantic usados como contrato de entrada/saída da API.

Por que existe:
- Padroniza o formato de dados entre backend e frontend.
- Evita erro humano (campos faltando, tipos errados).
- Ajuda o FastAPI a gerar OpenAPI/Swagger automaticamente.

Observação:
- Esse arquivo concentra tudo (Servidores, Serviços, Dashboard e Auditoria)
  para evitar duplicação e imports quebrando o app.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field
from pydantic.config import ConfigDict


# =====================================================
# TIPOS BÁSICOS E ENUMS (padronização de domínio)
# =====================================================

# Status do servidor (listagem de servidores)
# Obs: mantido "desconhecido" para não quebrar lógica atual do projeto
ServidorStatus = Literal["online", "offline", "desconhecido"]

# Status do serviço (Windows Services via WinRM)
ServiceStatus = Literal["running", "stopped", "paused", "unknown"]

# Tipo de inicialização do serviço (Win32_Service.StartMode)
StartupType = Literal["automatic", "manual", "disabled", "unknown"]


# =====================================================
# SERVIDORES (listagem e detalhes)
# =====================================================

class Servidor(BaseModel):
    """
    Representa um servidor conhecido pelo sistema.

    Usado em:
    - GET /servers
    - Seed do Dashboard no startup (main.py)
    """
    id: str
    nome: str
    descricao: Optional[str] = None
    status: ServidorStatus


class ServiceItem(BaseModel):
    """
    Representa um serviço do Windows retornado via WinRM.

    Observação (aliases):
    - WinRM/PS retorna campos em PascalCase ou você pode preferir camelCase no frontend.
    - Aqui aceitamos e emitimos alias como displayName / startType.
    """
    # Pydantic v2 config
    model_config = ConfigDict(populate_by_name=True)

    name: str
    display_name: str = Field(..., alias="displayName")
    status: ServiceStatus
    start_type: StartupType = Field("unknown", alias="startType")


class ServicesResponse(BaseModel):
    """
    Resposta da listagem de serviços de um servidor.
    """
    server_id: str
    host: str
    services: List[ServiceItem]


class ActionResponse(BaseModel):
    """
    Resposta padrão para ações (start/stop/restart).
    """
    ok: bool
    message: str


# =====================================================
# DASHBOARD (estado operacional em tempo real)
# =====================================================

# Status usado especificamente no dashboard
DashboardServerStatus = Literal["online", "offline", "unknown"]


class DashboardKpis(BaseModel):
    """
    Indicadores principais do dashboard.
    """
    total: int
    online: int
    offline: int
    unknown: int


class DashboardAlert(BaseModel):
    """
    Alerta ativo exibido no dashboard.

    Exemplo:
    - SERV 01 offline (CRITICAL)
    - Serviço crítico parado (WARNING)
    """
    nivel: Literal["CRITICAL", "WARNING"]
    mensagem: str
    server_id: str
    service_name: Optional[str] = None
    ts: datetime


class ServiceEvent(BaseModel):
    """
    Evento relevante para o dashboard (visão operacional).

    Importante:
    - Isso NÃO é o log completo (auditoria).
    - É só um resumo dos eventos recentes para NOC/monitoramento.
    """
    server_id: str
    service_name: str
    acao: Literal["START", "STOP", "RESTART", "ERROR", "STATUS_CHANGE"]
    status: ServiceStatus
    ts: datetime
    mensagem: str


class ServerStatusChanged(BaseModel):
    """
    Evento de mudança de status do servidor (online/offline/unknown).
    """
    server_id: str
    from_status: DashboardServerStatus
    to_status: DashboardServerStatus
    ts: datetime


class DashboardSnapshot(BaseModel):
    """
    Estado completo do dashboard em um ponto no tempo.

    Usado em:
    - GET /api/dashboard/snapshot
    - SSE (event: SNAPSHOT)
    """
    kpis: DashboardKpis
    alerts: List[DashboardAlert]
    recent_events: List[ServiceEvent]
    updated_at: datetime


# =====================================================
# LOGS / AUDITORIA (evento completo, histórico)
# =====================================================

LogLevel = Literal["DEBUG", "INFO", "WARN", "ERROR"]
LogSource = Literal["AUTH", "UI", "SERVER", "SERVICE", "WINRM", "AUDIT"]


class AuditLogItem(BaseModel):
    """
    Evento de auditoria persistido no sistema (JSONL).

    Usado em:
    - LogsPage (frontend)
    - GET /logs
    - base para exportações futuras
    """
    id: str
    timestamp: str
    nivel: LogLevel
    usuario: str
    origem: LogSource
    acao: str
    servidor_id: Optional[str] = None
    servidor_nome: Optional[str] = None
    servico: Optional[str] = None
    mensagem: Optional[str] = None
    sucesso: bool = True
    detalhe: Optional[str] = None


class AuditLogsResponse(BaseModel):
    """
    Resposta da API de logs.
    """
    items: List[AuditLogItem]


class EmitAuditEventRequest(BaseModel):
    """
    Evento de auditoria vindo do frontend (UI).

    Segurança:
    - O usuário vem do JWT (Depends(get_current_user))
    - NÃO aceitamos 'usuario' aqui (evita spoofing)
    """
    nivel: LogLevel = "INFO"
    origem: LogSource = "UI"
    acao: str
    mensagem: Optional[str] = None
    servidor_id: Optional[str] = None
    servidor_nome: Optional[str] = None
    servico: Optional[str] = None
    sucesso: bool = True
    detalhe: Optional[str] = None
