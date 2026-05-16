# app/audit/emissao.py
from __future__ import annotations

from typing import Optional

from app.audit.modelos import EventoAuditoria, NivelLog, OrigemLog
from app.audit.threads import BarramentoAuditoria

#função utilitaria que cria o eventoAuditoria e manda para o barramentoAuditoria, evita que cada rota ou serviço fique montando dicionario do log "na mão" e garantindo consistencia

#serve para padronização, sempre o mesmo formato, no frontend (logspage) lê sem surpresa

#centraliza: se amanhã for pra enriquecer o log (ex: ip, user-agent, request_id) faz aqui

def emitir_evento(
    bus: BarramentoAuditoria,
    *,
    # ✅ tipado: evita erro humano ("WAR" vs "WARN")
    nivel: NivelLog = "INFO",
    usuario: str,
    origem: OrigemLog,
    acao: str,
    mensagem: str,
    sucesso: bool = True,
    servidor_id: Optional[str] = None,
    servidor_nome: Optional[str] = None,
    servico: Optional[str] = None,
    detalhe: Optional[str] = None,
) -> bool:
    """
    Cria e publica um EventoAuditoria no barramento.

    Por que existe?
    - Centraliza o formato dos logs (padronização).
    - Evita duplicação de código nas rotas/services.
    - Mantém o mesmo "contrato" usado pelo frontend e pela persistência.

    Retorno:
    - True: evento entrou na fila do barramento
    - False: fila cheia (o evento foi descartado pelo barramento)
    """
    evento = EventoAuditoria(
        nivel=nivel,
        usuario=usuario,
        origem=origem,
        acao=acao,
        servidor_id=servidor_id,
        servidor_nome=servidor_nome,
        servico=servico,
        mensagem=mensagem,
        sucesso=sucesso,
        detalhe=detalhe,
    )

    # Publica no barramento (normalmente enfileira para a thread persistir)
    return bus.publicar(evento)
