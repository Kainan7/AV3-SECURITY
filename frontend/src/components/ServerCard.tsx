import type { Servidor } from "../api/servers";

type Props = {
  servidor: Servidor;
  onClick?: () => void;
};

/**
 * Mapeia o status do servidor para classes CSS.
 *
 * Por que existe?
 * - Centraliza o "tema" visual do status (online/offline/unknown)
 * - Evita repetir lógica de switch em vários componentes
 */
function statusClass(status: Servidor["status"] | string) {
  switch (status) {
    case "online":
      return "is-online";
    case "offline":
      return "is-offline";
    // tolerância caso algum lugar use "unknown" (dashboard) em vez de "desconhecido"
    case "unknown":
    case "desconhecido":
    default:
      return "is-unknown";
  }
}

/**
 * Extrai o número do servidor de forma segura.
 * Ex:
 * - "SERV 01" -> "01"
 * - "SERV01"  -> "01"
 * - "Servidor 01" -> "01" (se tiver número no nome)
 */
function getServerNumber(nome: string) {
  const match = (nome || "").match(/\d+/);
  return match ? match[0].padStart(2, "0") : "--";
}

export function ServerCard({ servidor, onClick }: Props) {
  const numero = getServerNumber(servidor.nome);

  return (
    <button className="server-card" onClick={onClick} type="button">
      <div className="server-card-badge">{numero}</div>

      <div>
        <div className="server-card-kicker">Servidor</div>
        <div className="server-card-title">{servidor.nome}</div>

        {servidor.descricao ? (
          <div className="server-card-desc">{servidor.descricao}</div>
        ) : null}
      </div>

      <div className={`server-card-status ${statusClass(servidor.status)}`}>
        <span className="server-card-dot" />
        {String(servidor.status).toUpperCase()}
      </div>
    </button>
  );
}
