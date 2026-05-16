// src/pages/ServerSelectPage.tsx
import { useEffect, useRef, useState } from "react";
import { NavLink, useNavigate } from "react-router-dom";
import { ServerCard } from "../components/ServerCard";
import { listarServidores, type Servidor } from "../api/servers";
import { emitUiEvent } from "../api/logs";

type LoadState = "idle" | "loading" | "error";

function normalizeStatus(s: unknown): Servidor["status"] {
  const v = String(s ?? "").toLowerCase();

  if (v === "unknown" || v === "desconhecido") return "desconhecido";
  if (v === "online") return "online";
  if (v === "offline") return "offline";

  return "desconhecido";
}

export function ServerSelectPage() {
  const navigate = useNavigate();
  const username = localStorage.getItem("restart_user") ?? "usuário";

  const didLoadRef = useRef(false);

  const [state, setState] = useState<LoadState>("idle");
  const [error, setError] = useState<string | null>(null);
  const [servidores, setServidores] = useState<Servidor[]>([]);

  function handleLogout() {
    emitUiEvent({
      nivel: "INFO",
      origem: "UI",
      acao: "LOGOUT",
      mensagem: `${username} saiu do sistema.`,
      sucesso: true,
    }).catch(() => {});

    localStorage.removeItem("restart_token");
    localStorage.removeItem("restart_user");
    navigate("/login");
  }

  async function load() {
    setState("loading");
    setError(null);

    try {
      const data = await listarServidores();

      setServidores(
        data.map((s) => ({
          ...s,
          status: normalizeStatus(s.status),
        }))
      );

      setState("idle");
    } catch (err: any) {
      const status = err?.response?.status;

      if (status === 401) {
        localStorage.removeItem("restart_token");
        localStorage.removeItem("restart_user");
        navigate("/login", { replace: true });
        return;
      }

      setState("error");
      setError(
        status
          ? `Falha ao carregar servidores (HTTP ${status}).`
          : "Falha de conexão com o backend."
      );
    }
  }

  useEffect(() => {
    if (didLoadRef.current) return;
    didLoadRef.current = true;

    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="app-header-left">
          <NavLink to="/servers" className="app-brand" end>
            <div className="app-title-main">RESTART SERVER</div>
            <div className="app-title-sub">
              Painel acadêmico para gerenciamento e monitoramento de servidores.
            </div>
          </NavLink>

          <nav className="app-nav" aria-label="Navegação principal">
            <NavLink to="/servers" end className="app-nav-link">
              Servidores
            </NavLink>
            <NavLink to="/dashboard" className="app-nav-link">
              Dashboard
            </NavLink>
            <NavLink to="/logs" className="app-nav-link">
              Logs
            </NavLink>
          </nav>
        </div>

        <div className="app-user">
          <span>Olá, {username}</span>
          <button className="logout-button" onClick={handleLogout}>
            Logout
          </button>
        </div>
      </header>

      <main className="app-main">
        <div className="panel">
          <div className="panel-head" style={{ marginBottom: 14 }}>
            <div>
              <h2 className="panel-title-left">SELECIONE O SERVIDOR</h2>
              <p className="panel-sub">
                Servidores de demonstração carregados do backend com rota protegida por JWT.
              </p>
            </div>

            <button
              type="button"
              className="logout-button"
              onClick={load}
              disabled={state === "loading"}
              title="Recarregar lista"
            >
              {state === "loading" ? "Carregando..." : "Atualizar"}
            </button>
          </div>

          {error && (
            <div className="muted-note" style={{ marginBottom: 12 }}>
              {error}
            </div>
          )}

          <div className="server-grid">
            {servidores.map((s) => (
              <ServerCard
                key={s.id}
                servidor={s}
                onClick={() => navigate(`/servers/${s.id}`)}
              />
            ))}
          </div>
        </div>
      </main>
    </div>
  );
}