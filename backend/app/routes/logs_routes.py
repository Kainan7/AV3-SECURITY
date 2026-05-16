# app/routes/logs_routes.py
"""
Rotas de Logs/Auditoria.

O que este módulo faz?
- GET /logs:
  Lê eventos persistidos (JSONL) e aplica o "clear marker" do usuário.
- POST /logs/clear:
  Não apaga fisicamente; salva um timestamp por usuário.
  A partir desse marco, o usuário não vê logs antigos.
- POST /logs/event:
  Endpoint para o frontend registrar ações de UI (navegação etc.).

Por que existe?
- Separar auditoria do resto do sistema.
- Garantir rastreabilidade (quem fez o quê e quando).
- Manter integridade: limpeza é "por visão do usuário", não destrutiva.
"""

from fastapi import APIRouter, Depends, Query

from app.deps.security import get_current_user
from app.deps.audit_bus import get_audit_bus
from app.audit.threads import BarramentoAuditoria
from app.audit.emissao import emitir_evento

from app.audit.persistencia import (
    ler_eventos,
    salvar_clear_marker,
    ler_clear_marker,
    filtrar_por_clear_marker,
)

from app.models.schemas import AuditLogsResponse, EmitAuditEventRequest

router = APIRouter(prefix="/logs", tags=["Logs"])


@router.get("", response_model=AuditLogsResponse)
def list_logs(
    limit: int = Query(200, ge=1, le=1000),
    user: str = Depends(get_current_user),
):
    """
    Retorna os últimos N logs persistidos.

    Regras:
    - Lê do JSONL do dia (ou do padrão da persistência).
    - Aplica o "clear marker" do usuário:
      o usuário não vê logs anteriores ao timestamp salvo em /logs/clear.
    """
    items = ler_eventos(limit=limit)
    clear_after = ler_clear_marker(usuario=user)
    items = filtrar_por_clear_marker(items, clear_after)
    return {"items": items}


@router.post("/clear")
def clear_logs(
    user: str = Depends(get_current_user),
    bus: BarramentoAuditoria = Depends(get_audit_bus),
):
    """
    "Limpar logs" por usuário (não destrutivo).

    O que acontece:
    - Salva um timestamp para aquele usuário.
    - Nas próximas consultas, logs anteriores a esse timestamp são ocultados.

    Obs:
    - Aqui você pode (opcionalmente) emitir um evento de auditoria informando o clear.
      (não vou mudar lógica agora; só documentando)
    """
    ts = salvar_clear_marker(usuario=user)
    return {"ok": True, "clear_after": ts}


@router.post("/event")
def emit_ui_event(
    payload: EmitAuditEventRequest,
    user: str = Depends(get_current_user),
    bus: BarramentoAuditoria = Depends(get_audit_bus),
):
    """
    Registra eventos originados pelo frontend (UI).

    Exemplo de uso:
    - usuário navegou para /dashboard
    - usuário clicou "Atualizar"
    - usuário saiu do sistema (logout)

    Segurança:
    - usuario vem do JWT (Depends(get_current_user)).
    - O frontend não pode forjar o "usuario".
    """
    ok = emitir_evento(
        bus,
        nivel=payload.nivel,
        usuario=user,
        origem=payload.origem,
        acao=payload.acao,
        mensagem=payload.mensagem or f"Evento UI: {payload.acao}",
        sucesso=payload.sucesso,
        servidor_id=payload.servidor_id,
        servidor_nome=payload.servidor_nome,
        servico=payload.servico,
        detalhe=payload.detalhe,
    )
    return {"ok": ok}
