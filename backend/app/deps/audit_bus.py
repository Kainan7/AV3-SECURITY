# app/deps/audit_bus.py
"""
Dependency helpers do FastAPI.

Este arquivo expõe o barramento de auditoria (fila + thread consumidora)
armazenado no app.state no startup.
"""

from fastapi import Request
from app.audit.threads import BarramentoAuditoria


def get_audit_bus(request: Request) -> BarramentoAuditoria:
    """
    Retorna o Barramento de Auditoria registrado no `app.state.audit_bus`.

    Uso típico:
        bus: BarramentoAuditoria = Depends(get_audit_bus)

    Por que existe:
    - Evita acessar `request.app.state.*` diretamente em todas as rotas
    - Padroniza a injeção e facilita testes/mocks
    """
    return request.app.state.audit_bus
