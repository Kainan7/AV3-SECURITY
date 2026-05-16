# app/routes/server_routes.py
"""
Rotas de Servidores e Serviços (WinRM).

O que este módulo faz?
- Lista servidores disponíveis (demo: SERV 01).
- Lista serviços de um servidor via ServerService (WinRM).
- Executa ações START/STOP/RESTART em serviços.
- Emite auditoria padronizada (BarramentoAuditoria -> JSONL).
- Atualiza o Dashboard em "quase tempo real" usando fire-and-forget
  (rota sync -> chama coroutines do DashboardService no loop principal).

Por que existe?
- Centraliza endpoints de operação (serviços) e mantém rastreabilidade (auditoria).
- Integra WinRM com Dashboard sem bloquear request e sem quebrar fluxo.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.config import WINRM_HOST
from app.models.schemas import ServicesResponse, ActionResponse, Servidor

from app.deps.security import get_current_user
from app.deps.audit_bus import get_audit_bus
from app.audit.threads import BarramentoAuditoria
from app.audit.emissao import emitir_evento

from app.services.server_service import ServerService

from app.deps.dashboard_dep import get_dashboard_service
from app.services.dashboard_service import DashboardService
from app.deps.dashboard_dispatch import fire_and_forget


router = APIRouter(prefix="/servers", tags=["Servers"])

# Demo atual (você pode expandir depois)
SERVER_ID = "1"


def _serv_name(server_id: str) -> str:
    """Converte id -> label amigável (SERV 01, SERV 02...)."""
    return f"SERV {str(server_id).zfill(2)}"


def _svc_label(svc: object) -> str:
    """
    Gera um nome consistente para o serviço no dashboard.

    Motivo:
    - Alguns retornos vêm como ServiceItem (display_name)
    - Outros podem vir como dict/obj com displayName
    - Fallback: name
    """
    display = getattr(svc, "display_name", None) or getattr(svc, "displayName", None)
    name = getattr(svc, "name", None)
    return str(display or name or "unknown")


@router.get("", response_model=list[Servidor])
def list_servers(
    user: str = Depends(get_current_user),
    bus: BarramentoAuditoria = Depends(get_audit_bus),
):
    """
    Lista os servidores conhecidos.

    Auditoria:
    - Sucesso -> FETCH_SERVERS INFO
    - Falha   -> FETCH_SERVERS ERROR

    Obs:
    - Não mexe com dashboard aqui porque é só catálogo/lista.
    """
    try:
        data = ServerService.listar_servidores()

        emitir_evento(
            bus,
            nivel="INFO",
            usuario=user,
            origem="SERVER",
            acao="FETCH_SERVERS",
            mensagem="Lista de servidores carregada com sucesso.",
            sucesso=True,
        )
        return data

    except Exception as e:
        emitir_evento(
            bus,
            nivel="ERROR",
            usuario=user,
            origem="SERVER",
            acao="FETCH_SERVERS",
            mensagem="Falha ao carregar lista de servidores.",
            sucesso=False,
            detalhe=str(e),
        )
        raise HTTPException(status_code=500, detail="Failed to list servers")


@router.get("/{server_id}/services", response_model=ServicesResponse)
def list_services(
    request: Request,
    server_id: str,
    limit: int = Query(200, ge=1, le=500),
    user: str = Depends(get_current_user),
    bus: BarramentoAuditoria = Depends(get_audit_bus),
    dash: DashboardService = Depends(get_dashboard_service),
):
    """
    Lista serviços do servidor via WinRM.

    Regra de status do servidor (sua regra atual):
    - Se conseguiu listar serviços -> server online
    - Se deu erro/exception -> server offline

    Dashboard:
    - Atualiza status online/offline
    - Atualiza snapshot de serviços (para cards/alertas/eventos)
    """
    if server_id != SERVER_ID:
        emitir_evento(
            bus,
            nivel="WARN",
            usuario=user,
            origem="SERVER",
            acao="FETCH_SERVICES",
            mensagem=f"Tentativa de listar serviços no servidor {_serv_name(server_id)} (não implementado).",
            sucesso=False,
            servidor_id=server_id,
            servidor_nome=_serv_name(server_id),
            detalhe="HTTP 404 - Server not implemented (demo only server 1).",
        )
        raise HTTPException(status_code=404, detail="Server not implemented yet (demo is only server 1).")

    try:
        services = ServerService.listar_servicos(server_id=server_id, limit=limit)

        emitir_evento(
            bus,
            nivel="INFO",
            usuario=user,
            origem="SERVER",
            acao="FETCH_SERVICES",
            mensagem=f"Lista de serviços carregada com sucesso ({_serv_name(server_id)}).",
            sucesso=True,
            servidor_id=server_id,
            servidor_nome=_serv_name(server_id),
        )

        # Dashboard: SERV 01 online + snapshot serviços
        try:
            services_map = {_svc_label(s): getattr(s, "status", "unknown") for s in services}
            fire_and_forget(request, dash.set_server_status(server_id=server_id, new_status="online"))
            fire_and_forget(request, dash.set_services_snapshot(server_id=server_id, services_map=services_map))
        except Exception:
            # Nunca quebra a rota por causa do dashboard
            pass

        return {"server_id": server_id, "host": WINRM_HOST, "services": services}

    except Exception as e:
        emitir_evento(
            bus,
            nivel="ERROR",
            usuario=user,
            origem="SERVER",
            acao="FETCH_SERVICES",
            mensagem="Falha ao listar serviços.",
            sucesso=False,
            servidor_id=server_id,
            servidor_nome=_serv_name(server_id),
            detalhe=str(e),
        )

        # Dashboard: SERV 01 offline
        try:
            fire_and_forget(request, dash.set_server_status(server_id=server_id, new_status="offline"))
        except Exception:
            pass

        raise HTTPException(status_code=500, detail="Failed to list services")


@router.post("/{server_id}/services/{service_name}/start", response_model=ActionResponse)
def start_service(
    request: Request,
    server_id: str,
    service_name: str,
    user: str = Depends(get_current_user),
    bus: BarramentoAuditoria = Depends(get_audit_bus),
    dash: DashboardService = Depends(get_dashboard_service),
):
    """
    START de um serviço via WinRM.

    Auditoria:
    - SERVICE_START INFO/ERROR

    Dashboard:
    - publica evento de ação recente (START)
    """
    if server_id != SERVER_ID:
        emitir_evento(
            bus,
            nivel="WARN",
            usuario=user,
            origem="SERVICE",
            acao="SERVICE_START",
            mensagem=f"Tentativa de START em {service_name} no server {_serv_name(server_id)} (não implementado).",
            sucesso=False,
            servidor_id=server_id,
            servidor_nome=_serv_name(server_id),
            servico=service_name,
            detalhe="HTTP 404 - Server not implemented (demo only server 1).",
        )
        raise HTTPException(status_code=404, detail="Server not implemented yet (demo is only server 1).")

    try:
        s = ServerService.start(server_id=server_id, service_name=service_name)

        emitir_evento(
            bus,
            nivel="INFO",
            usuario=user,
            origem="SERVICE",
            acao="SERVICE_START",
            mensagem=f"Início do serviço {service_name} executado com sucesso.",
            sucesso=True,
            servidor_id=server_id,
            servidor_nome=_serv_name(server_id),
            servico=service_name,
        )

        try:
            fire_and_forget(
                request,
                dash.record_service_action(
                    server_id=server_id,
                    service_name=service_name,
                    action="START",
                    status=getattr(s, "status", "unknown"),
                    message=f"{_serv_name(server_id)}: Serviço {service_name} iniciado.",
                ),
            )
        except Exception:
            pass

        return {"ok": True, "message": f"Service '{service_name}' started"}

    except Exception as e:
        emitir_evento(
            bus,
            nivel="ERROR",
            usuario=user,
            origem="SERVICE",
            acao="SERVICE_START",
            mensagem=f"Falha ao iniciar serviço {service_name}.",
            sucesso=False,
            servidor_id=server_id,
            servidor_nome=_serv_name(server_id),
            servico=service_name,
            detalhe=str(e),
        )

        try:
            fire_and_forget(
                request,
                dash.record_service_action(
                    server_id=server_id,
                    service_name=service_name,
                    action="ERROR",
                    status="unknown",
                    message=f"{_serv_name(server_id)}: erro ao iniciar {service_name}.",
                ),
            )
        except Exception:
            pass

        raise HTTPException(status_code=500, detail="Failed to start service")


@router.post("/{server_id}/services/{service_name}/stop", response_model=ActionResponse)
def stop_service(
    request: Request,
    server_id: str,
    service_name: str,
    user: str = Depends(get_current_user),
    bus: BarramentoAuditoria = Depends(get_audit_bus),
    dash: DashboardService = Depends(get_dashboard_service),
):
    """
    STOP de um serviço via WinRM.

    Auditoria:
    - SERVICE_STOP WARN/ERROR (você escolheu WARN para STOP e RESTART)

    Dashboard:
    - publica evento recente (STOP)
    """
    if server_id != SERVER_ID:
        emitir_evento(
            bus,
            nivel="WARN",
            usuario=user,
            origem="SERVICE",
            acao="SERVICE_STOP",
            mensagem=f"Tentativa de STOP em {service_name} no server {_serv_name(server_id)} (não implementado).",
            sucesso=False,
            servidor_id=server_id,
            servidor_nome=_serv_name(server_id),
            servico=service_name,
            detalhe="HTTP 404 - Server not implemented (demo only server 1).",
        )
        raise HTTPException(status_code=404, detail="Server not implemented yet (demo is only server 1).")

    try:
        s = ServerService.stop(server_id=server_id, service_name=service_name)

        emitir_evento(
            bus,
            nivel="WARN",
            usuario=user,
            origem="SERVICE",
            acao="SERVICE_STOP",
            mensagem=f"Parada do serviço {service_name} executada com sucesso.",
            sucesso=True,
            servidor_id=server_id,
            servidor_nome=_serv_name(server_id),
            servico=service_name,
        )

        try:
            fire_and_forget(
                request,
                dash.record_service_action(
                    server_id=server_id,
                    service_name=service_name,
                    action="STOP",
                    status=getattr(s, "status", "unknown"),
                    message=f"{_serv_name(server_id)}: Serviço {service_name} parado.",
                ),
            )
        except Exception:
            pass

        return {"ok": True, "message": f"Service '{service_name}' stopped"}

    except Exception as e:
        emitir_evento(
            bus,
            nivel="ERROR",
            usuario=user,
            origem="SERVICE",
            acao="SERVICE_STOP",
            mensagem=f"Falha ao parar serviço {service_name}.",
            sucesso=False,
            servidor_id=server_id,
            servidor_nome=_serv_name(server_id),
            servico=service_name,
            detalhe=str(e),
        )

        try:
            fire_and_forget(
                request,
                dash.record_service_action(
                    server_id=server_id,
                    service_name=service_name,
                    action="ERROR",
                    status="unknown",
                    message=f"{_serv_name(server_id)}: erro ao parar {service_name}.",
                ),
            )
        except Exception:
            pass

        raise HTTPException(status_code=500, detail="Failed to stop service")


@router.post("/{server_id}/services/{service_name}/restart", response_model=ActionResponse)
def restart_service(
    request: Request,
    server_id: str,
    service_name: str,
    user: str = Depends(get_current_user),
    bus: BarramentoAuditoria = Depends(get_audit_bus),
    dash: DashboardService = Depends(get_dashboard_service),
):
    """
    RESTART de um serviço via WinRM.

    Auditoria:
    - SERVICE_RESTART WARN/ERROR

    Dashboard:
    - publica evento recente (RESTART)
    """
    if server_id != SERVER_ID:
        emitir_evento(
            bus,
            nivel="WARN",
            usuario=user,
            origem="SERVICE",
            acao="SERVICE_RESTART",
            mensagem=f"Tentativa de RESTART em {service_name} no server {_serv_name(server_id)} (não implementado).",
            sucesso=False,
            servidor_id=server_id,
            servidor_nome=_serv_name(server_id),
            servico=service_name,
            detalhe="HTTP 404 - Server not implemented (demo only server 1).",
        )
        raise HTTPException(status_code=404, detail="Server not implemented yet (demo is only server 1).")

    try:
        s = ServerService.restart(server_id=server_id, service_name=service_name)

        emitir_evento(
            bus,
            nivel="WARN",
            usuario=user,
            origem="SERVICE",
            acao="SERVICE_RESTART",
            mensagem=f"Reinício do serviço {service_name} executado com sucesso.",
            sucesso=True,
            servidor_id=server_id,
            servidor_nome=_serv_name(server_id),
            servico=service_name,
        )

        try:
            fire_and_forget(
                request,
                dash.record_service_action(
                    server_id=server_id,
                    service_name=service_name,
                    action="RESTART",
                    status=getattr(s, "status", "unknown"),
                    message=f"{_serv_name(server_id)}: Serviço {service_name} reiniciado.",
                ),
            )
        except Exception:
            pass

        return {"ok": True, "message": f"Service '{service_name}' restarted"}

    except Exception as e:
        emitir_evento(
            bus,
            nivel="ERROR",
            usuario=user,
            origem="SERVICE",
            acao="SERVICE_RESTART",
            mensagem=f"Falha ao reiniciar serviço {service_name}.",
            sucesso=False,
            servidor_id=server_id,
            servidor_nome=_serv_name(server_id),
            servico=service_name,
            detalhe=str(e),
        )

        try:
            fire_and_forget(
                request,
                dash.record_service_action(
                    server_id=server_id,
                    service_name=service_name,
                    action="ERROR",
                    status="unknown",
                    message=f"{_serv_name(server_id)}: erro ao reiniciar {service_name}.",
                ),
            )
        except Exception:
            pass

        raise HTTPException(status_code=500, detail="Failed to restart service")
