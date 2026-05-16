// src/api/servers.ts
import { http } from "./http";

/**
 * Tipos de servidor
 * - `desconhecido` existe porque seu backend usa isso hoje
 * - o Dashboard normaliza para "unknown"
 */
export type ServidorStatus = "online" | "offline" | "desconhecido";

export type Servidor = {
  id: string;
  nome: string;
  descricao?: string | null;
  status: ServidorStatus;
};

/**
 * Lista servidores (GET /servers)
 */
export async function listarServidores(): Promise<Servidor[]> {
  const response = await http.get<Servidor[]>("/servers");
  return response.data;
}
