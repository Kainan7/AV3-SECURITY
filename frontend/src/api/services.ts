// src/api/services.ts
import { http } from "./http";

export type ServiceStatus = "running" | "stopped" | "paused" | "unknown";

export type Service = {
  name: string;         // "Spooler"
  displayName: string;  // "Spooler de Impressão"
  status: ServiceStatus;
  startType?: "automatic" | "manual" | "disabled" | string;
};

export type ServicesResponse = {
  server_id: string;
  host?: string;
  services: Service[];
};

export type ActionResponse = {
  ok: boolean;
  message: string;
};

/** Encode seguro para path params */
function enc(v: string) {
  return encodeURIComponent(v);
}

/**
 * Lista serviços do servidor (GET /servers/:id/services)
 */
export async function listarServicos(serverId: string, limit = 200): Promise<ServicesResponse> {
  const response = await http.get<ServicesResponse>(`/servers/${enc(serverId)}/services`, {
    params: { limit },
  });
  return response.data;
}

/**
 * Inicia serviço (POST)
 */
export async function startService(serverId: string, serviceName: string): Promise<ActionResponse> {
  const response = await http.post<ActionResponse>(
    `/servers/${enc(serverId)}/services/${enc(serviceName)}/start`
  );
  return response.data;
}

/**
 * Para serviço (POST)
 */
export async function stopService(serverId: string, serviceName: string): Promise<ActionResponse> {
  const response = await http.post<ActionResponse>(
    `/servers/${enc(serverId)}/services/${enc(serviceName)}/stop`
  );
  return response.data;
}

/**
 * Reinicia serviço (POST)
 */
export async function restartService(serverId: string, serviceName: string): Promise<ActionResponse> {
  const response = await http.post<ActionResponse>(
    `/servers/${enc(serverId)}/services/${enc(serviceName)}/restart`
  );
  return response.data;
}
