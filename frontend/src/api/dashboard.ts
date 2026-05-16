// src/api/dashboard.ts
import { http, API_BASE_URL } from "./http";

/**
 * Tipos do Dashboard
 * - espelham o backend (DashboardSnapshot / Alerts / Events)
 * - `ts` vem como string ISO (porque o backend serializa datetime)
 */
export type AlertItem = {
  nivel: "CRITICAL" | "WARNING";
  mensagem: string;
  server_id: string;
  service_name?: string | null;
  ts: string; // ISO string
};

export type ServiceEvent = {
  server_id: string;
  service_name: string;

  /**
   * No backend você usa: START | STOP | RESTART | ERROR | STATUS_CHANGE
   * Mantemos `string` como fallback para evitar quebrar caso surja novo valor.
   */
  acao: "START" | "STOP" | "RESTART" | "ERROR" | "STATUS_CHANGE" | string;

  /**
   * Status do serviço no padrão WinRM:
   * running | stopped | paused | unknown
   * Mantemos `string` como fallback para evolução sem quebrar.
   */
  status: "running" | "stopped" | "paused" | "unknown" | string;

  ts: string; // ISO string
  mensagem: string;
};

export type Snapshot = {
  kpis: { total: number; online: number; offline: number; unknown: number };
  alerts: AlertItem[];
  recent_events: ServiceEvent[];
  updated_at: string; // ISO string
};

/**
 * Busca o snapshot atual (HTTP).
 *
 * Por que existe?
 * - Usado no load inicial
 * - Usado no botão "Atualizar"
 * - Serve como fallback caso SSE caia
 */
export async function getDashboardSnapshot(): Promise<Snapshot> {
  const { data } = await http.get<Snapshot>("/api/dashboard/snapshot");
  return data;
}

/**
 * Abre stream SSE do dashboard.
 *
 * IMPORTANTE:
 * - EventSource NÃO usa Axios
 * - EventSource NÃO injeta header Authorization
 *   (por isso seu stream no backend normalmente é público ou usa cookie)
 *
 * Estratégia:
 * - Se você tiver proxy no Vite → URL relativa funciona (recomendado)
 * - Se não tiver proxy → usa API_BASE_URL completo
 */
export function openDashboardStream(): EventSource {
  // ✅ recomendado: se tiver Vite proxy para /api -> backend, use a linha abaixo:
  // return new EventSource("/api/dashboard/stream");

  // ✅ fallback: URL completa (DEV)
  return new EventSource(`${API_BASE_URL}/api/dashboard/stream`);
}
