# app/audit/persistencia.py
from __future__ import annotations

"""
Persistência de Auditoria (JSONL por dia)

Por que existe?
- Guardar histórico de eventos em disco sem travar requisições HTTP.
- Facilitar backup/restore: arquivos simples (.jsonl) e por data (rotação diária).
- Permitir "limpar logs" sem deletar o histórico: usamos um clear marker por usuário.

Formato:
- utils/audit/YYYY-MM-DD.jsonl
- Cada linha é um JSON completo (1 evento por linha).
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from app.audit.modelos import EventoAuditoria

# ---------------------------------------------------------
# Local de armazenamento
# ---------------------------------------------------------
# Mantemos fora de app/ para facilitar deploy/backup.
# Ex.: backend/utils/audit/2026-01-08.jsonl
BASE_DIR = Path(__file__).resolve().parents[2]  # .../backend
AUDIT_DIR = BASE_DIR / "utils" / "audit"
AUDIT_DIR.mkdir(parents=True, exist_ok=True)

# Arquivo com "clear marker" por usuário (não apaga histórico; só filtra visualização)
CLEAR_MARKERS_PATH = AUDIT_DIR / "clear_markers.json"


# ---------------------------------------------------------
# Helpers de data/arquivo
# ---------------------------------------------------------
def _data_utc(ts_iso: Optional[str] = None) -> str:
    """
    Retorna a data UTC no formato YYYY-MM-DD.

    Para que serve?
    - Rotacionar logs por dia (um arquivo por dia em UTC).
    - Se um evento já tem timestamp, usamos a data dele; caso contrário, usamos "hoje".
    """
    if ts_iso:
        try:
            dt = datetime.fromisoformat(ts_iso.replace("Z", "+00:00"))
            dt = dt.astimezone(timezone.utc)
            return dt.strftime("%Y-%m-%d")
        except Exception:
            # Se o timestamp vier inválido, cai no "agora"
            pass

    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _arquivo_do_dia(data_utc: str) -> Path:
    """
    Monta o caminho do arquivo JSONL daquele dia (UTC).
    """
    return AUDIT_DIR / f"{data_utc}.jsonl"


def _utc_now_iso() -> str:
    """
    Retorna timestamp ISO-8601 em UTC (string).
    Usado no clear marker.
    """
    return datetime.now(timezone.utc).isoformat()


def _to_dt(ts_iso: str) -> Optional[datetime]:
    """
    Converte timestamp ISO em datetime UTC.

    Para que serve?
    - Comparações na função filtrar_por_clear_marker()
    """
    try:
        dt = datetime.fromisoformat(ts_iso.replace("Z", "+00:00"))
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def _evento_to_dict(evento: EventoAuditoria) -> dict:
    """
    Converte EventoAuditoria para dict de forma compatível com Pydantic v1 e v2.

    Por que existe?
    - Pydantic v2: evento.model_dump()
    - Pydantic v1: evento.dict()
    """
    if hasattr(evento, "model_dump"):  # pydantic v2
        return evento.model_dump()
    return evento.dict()  # pydantic v1


# ---------------------------------------------------------
# Escrita (usada pela thread consumidora)
# ---------------------------------------------------------
def persistir_evento(evento: EventoAuditoria) -> None:
    """
    Persiste 1 evento em JSONL (1 linha = 1 JSON).

    Quem chama?
    - A thread consumidora do BarramentoAuditoria (producer/consumer).

    Por que assim?
    - JSONL é simples, rápido e robusto.
    - 1 evento por linha evita corrupção completa do arquivo se o processo cair.
    """
    data = _data_utc(evento.timestamp)
    path = _arquivo_do_dia(data)

    linha = json.dumps(_evento_to_dict(evento), ensure_ascii=False)

    # Abre em append e escreve uma linha.
    # Em logs críticos, é boa prática dar flush + fsync para reduzir risco de perda.
    with path.open("a", encoding="utf-8") as f:
        f.write(linha + "\n")
        f.flush()
        os.fsync(f.fileno())


# ---------------------------------------------------------
# Leitura (usada na rota /logs)
# ---------------------------------------------------------
def ler_eventos(*, limit: int = 300, dia_utc: Optional[str] = None) -> list[dict]:
    """
    Lê eventos do JSONL.

    Regras:
    - Se dia_utc não for informado, lê do arquivo do dia atual (UTC).
    - Retorna os últimos `limit` eventos.

    Observação:
    - Aqui usamos leitura simples do arquivo inteiro e tail.
      Para volumes enormes, podemos otimizar para "tail" real,
      mas nesse projeto atual está ok e mantém robustez.
    """
    data = dia_utc or _data_utc()
    path = _arquivo_do_dia(data)

    if not path.exists():
        return []

    lines = path.read_text(encoding="utf-8").splitlines()
    tail = lines[-limit:]

    out: list[dict] = []
    for ln in tail:
        try:
            out.append(json.loads(ln))
        except Exception:
            # Se uma linha estiver corrupta, ignora e segue
            continue

    return out


# ---------------------------------------------------------
# Clear Marker (para "Limpar logs" por usuário)
# ---------------------------------------------------------
def salvar_clear_marker(*, usuario: str, ts_iso: Optional[str] = None) -> str:
    """
    Salva um "marco de limpeza" por usuário.

    O que isso significa?
    - Quando o usuário clica "Limpar logs", não apagamos o arquivo.
    - Apenas gravamos: "a partir deste timestamp, esse usuário não verá logs anteriores".

    Por que isso é bom?
    - Preserva histórico para auditoria/forense.
    - UX: o usuário vê "limpo" ao voltar na tela (persistente).
    """
    ts = ts_iso or _utc_now_iso()

    # Carrega JSON atual
    data: dict[str, str] = {}
    if CLEAR_MARKERS_PATH.exists():
        try:
            data = json.loads(CLEAR_MARKERS_PATH.read_text(encoding="utf-8") or "{}")
        except Exception:
            data = {}

    # Atualiza o marco do usuário
    data[usuario] = ts

    # Escrita atômica: escreve em .tmp e depois substitui o arquivo final.
    tmp = CLEAR_MARKERS_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(CLEAR_MARKERS_PATH)

    return ts


def ler_clear_marker(*, usuario: str) -> Optional[str]:
    """
    Lê o clear marker do usuário, se existir.

    Retorna:
    - timestamp ISO (string) se houver
    - None se não houver ou se falhar leitura
    """
    if not CLEAR_MARKERS_PATH.exists():
        return None

    try:
        data = json.loads(CLEAR_MARKERS_PATH.read_text(encoding="utf-8") or "{}")
        return data.get(usuario)
    except Exception:
        return None


def filtrar_por_clear_marker(items: list[dict], clear_after_iso: Optional[str]) -> list[dict]:
    """
    Filtra logs mantendo somente itens com timestamp >= clear_after_iso.

    Quem usa?
    - A rota de listar logs, depois de ler_eventos().

    Por que aqui e não no frontend?
    - Segurança/consistência: o backend entrega o que o usuário "tem direito a ver"
    - Evita o frontend ter que implementar regra de corte
    """
    if not clear_after_iso:
        return items

    cut = _to_dt(clear_after_iso)
    if not cut:
        return items

    out: list[dict] = []
    for it in items:
        ts = it.get("timestamp")
        if not ts:
            continue

        d = _to_dt(ts)
        if d and d >= cut:
            out.append(it)

    return out
