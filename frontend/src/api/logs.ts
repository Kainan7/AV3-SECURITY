// src/api/logs.ts
import { http } from "./http";

/**
 * Tipos de auditoria (logs)
 * - são o formato “verdadeiro” e persistido no backend (JSONL)
 */
export type LogLevel = "DEBUG" | "INFO" | "WARN" | "ERROR";
export type LogSource = "AUTH" | "UI" | "SERVER" | "SERVICE" | "WINRM" | "AUDIT";

export type AuditLogItem = {
  id: string;
  timestamp: string;
  nivel: LogLevel;
  usuario: string;
  origem: LogSource;
  acao: string;
  servidor_id?: string | null;
  servidor_nome?: string | null;
  servico?: string | null;
  mensagem?: string | null;
  sucesso?: boolean;
  detalhe?: string | null;
};

/**
 * Busca logs persistidos do backend (últimos N)
 */
export async function fetchLogs(limit = 200): Promise<AuditLogItem[]> {
  const res = await http.get<{ items: AuditLogItem[] }>(`/logs?limit=${limit}`);
  return res.data.items;
}

/**
 * "Limpar logs" por usuário
 * - no backend salva um marker (timestamp)
 * - depois disso o GET /logs filtra logs antigos
 */
export async function clearLogs(): Promise<{ ok: boolean; clear_after: string }> {
  const res = await http.post<{ ok: boolean; clear_after: string }>(`/logs/clear`);
  return res.data;
}

/**
 * Emite evento de UI para auditoria.
 *
 * Por que existe?
 * - Ações que acontecem só no frontend (navegação, refresh, click em botão)
 * - Precisam ser registradas na auditoria mesmo sem rota backend “natural”
 */
export async function emitUiEvent(payload: {
  nivel?: LogLevel;
  origem?: LogSource; // default "UI"
  acao: string;
  mensagem?: string;
  servidor_id?: string;
  servidor_nome?: string;
  servico?: string;
  sucesso?: boolean;
  detalhe?: string | null;
}): Promise<void> {
  await http.post("/logs/event", payload);
}
