# app/audit/modelos.py
from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


# =====================================================
# Tipos restritos: evitam erro humano e padronizam logs
# =====================================================

# Severidade do log
NivelLog = Literal["DEBUG", "INFO", "WARN", "ERROR"]

# Origem do evento (quem gerou)
OrigemLog = Literal[
    "AUTH",    # autenticação
    "UI",      # ações do usuário na interface
    "SERVER",  # ações relacionadas a servidor
    "SERVICE", # ações relacionadas a serviços
    "WINRM",   # integração WinRM
    "AUDIT",   # sistema de auditoria/logs
]


# =====================================================
# Modelo principal do evento de auditoria
# =====================================================
class EventoAuditoria(BaseModel):
    """
    Contrato oficial de auditoria/logs.

    Usado em:
    - persistência (jsonl)
    - retorno da API /logs
    - exibição no frontend
    - stream SSE (se habilitado)

    Regras importantes:
    - extra="forbid": proíbe campos não definidos aqui
    - frozen=True: imutável (mais seguro em concorrência)
    """

    # -----------------------------
    # Identificação do evento
    # -----------------------------
    id: str = Field(
        default_factory=lambda: str(uuid4()),
        description="Identificador único do evento",
    )

    # Mantemos string ISO-8601 UTC para compatibilidade direta com frontend
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="Timestamp UTC ISO-8601",
    )

    # -----------------------------
    # Severidade e contexto
    # -----------------------------
    nivel: NivelLog = Field(
        default="INFO",
        description="Nível do evento",
    )

    usuario: str = Field(
        description="Usuário autenticado que gerou o evento",
    )

    origem: OrigemLog = Field(
        description="Origem do evento (AUTH, UI, SERVICE, etc.)",
    )

    acao: str = Field(
        description="Ação semântica (ex: LOGIN_SUCCESS, SERVICE_START)",
    )

    # -----------------------------
    # Alvos do evento (opcionais)
    # -----------------------------
    servidor_id: Optional[str] = Field(
        default=None,
        description="ID do servidor relacionado",
    )

    servidor_nome: Optional[str] = Field(
        default=None,
        description="Nome amigável do servidor (ex: SERV 01)",
    )

    servico: Optional[str] = Field(
        default=None,
        description="Serviço afetado (ex: Spooler)",
    )

    # -----------------------------
    # Mensagem e resultado
    # -----------------------------
    mensagem: Optional[str] = Field(
        default=None,
        description="Mensagem humana do evento",
    )

    sucesso: bool = Field(
        default=True,
        description="Se a ação foi concluída com sucesso",
    )

    detalhe: Optional[str] = Field(
        default=None,
        description="Detalhe técnico (erro, timeout, etc.)",
    )

    class Config:
        frozen = True
        extra = "forbid"
