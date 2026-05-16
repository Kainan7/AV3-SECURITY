// src/pages/ServerDetailsPage.tsx
import { useEffect, useMemo, useState } from "react";
import { Link, NavLink, useNavigate, useParams } from "react-router-dom";

import {
  listarServicos,
  restartService,
  startService,
  stopService,
  type Service,
  type ServiceStatus,
} from "../api/services";

import { emitUiEvent } from "../api/logs";

function statusLabel(s: ServiceStatus) {
  switch (s) {
    case "running":
      return "EM EXECUÇÃO";
    case "stopped":
      return "PARADO";
    case "paused":
      return "PAUSADO";
    default:
      return "DESCONHECIDO";
  }
}

function normalizeStatus(s: any): ServiceStatus {
  const v = String(s ?? "").toLowerCase();
  if (v === "running" || v === "4") return "running";
  if (v === "stopped" || v === "1") return "stopped";
  if (v === "paused" || v === "7") return "paused";
  return "unknown";
}

function normalizeStartType(t: any): "automatic" | "manual" | "disabled" | "unknown" {
  const v = String(t ?? "").toLowerCase();
  if (v === "2" || v.includes("auto")) return "automatic";
  if (v === "4" || v.includes("disabled")) return "disabled";
  if (v === "3" || v.includes("manual") || v.includes("trigger")) return "manual";
  return "unknown";
}

function serverLabel(id?: string) {
  if (!id) return "SRV-DEMO";
  const n = Number(id);
  if (!Number.isFinite(n)) return `SRV-DEMO-${id}`;
  return `SRV-DEMO-${String(n).padStart(2, "0")}`;
}

export function ServerDetailsPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const username = useMemo(() => localStorage.getItem("restart_user") ?? "usuário", []);

  const integrated = id === "1";

  const [services, setServices] = useState<Service[]>([]);
  const [query, setQuery] = useState("");

  const [loading, setLoading] = useState(false);
  const [busyService, setBusyService] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const filteredServices = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return services;

    return services.filter((s) => {
      const name = (s.name ?? "").toLowerCase();
      const display = (s.displayName ?? "").toLowerCase();
      return name.includes(q) || display.includes(q);
    });
  }, [services, query]);

  async function fetchServices() {
    if (!id || !integrated) return;

    setLoading(true);
    setError(null);

    try {
      const data = await listarServicos(id, 200);

      const normalized = (data.services ?? []).map((s) => ({
        ...s,
        status: normalizeStatus((s as any).status),
        startType: normalizeStartType((s as any).startType),
      }));

      setServices(normalized);
    } catch (err: any) {
      console.error(err);
      const status = err?.response?.status;

      if (status === 401) setError("Sessão expirada. Faça login novamente.");
      else if (status) setError(`Falha ao carregar serviços (HTTP ${status}).`);
      else setError("Falha de conexão com o backend. Verifique se a API está ativa.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    fetchServices();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  async function doAction(action: "start" | "stop" | "restart", serviceName: string) {
    if (!id) return;

    setBusyService(serviceName);
    setError(null);

    const optimisticStatus: ServiceStatus =
      action === "start" ? "running" : action === "stop" ? "stopped" : "running";

    setServices((prev) =>
      prev.map((s) => (s.name === serviceName ? { ...s, status: optimisticStatus } : s))
    );

    try {
      if (action === "start") await startService(id, serviceName);
      if (action === "stop") await stopService(id, serviceName);
      if (action === "restart") await restartService(id, serviceName);
    } catch (err: any) {
      console.error(err);

      setServices((prev) =>
        prev.map((s) => (s.name === serviceName ? { ...s, status: "unknown" } : s))
      );

      const status = err?.response?.status;

      if (status === 401) setError("Sessão expirada. Faça login novamente.");
      else if (status) setError(`Falha ao executar ação (HTTP ${status}).`);
      else setError("Falha de conexão com o backend. Verifique se a API está ativa.");
    } finally {
      setBusyService(null);
    }
  }

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

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="app-header-left">
          <NavLink to="/servers" className="app-brand" end>
            <div className="app-title-main">RESTART SERVER</div>
            <div className="app-title-sub">Detalhes e serviços do servidor.</div>
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
          <div className="panel-head">
            <div>
              <h2 className="panel-title-left">Servidor: {serverLabel(id)}</h2>
              <p className="panel-sub">
                Serviços reais do <span className="kbd">services.msc</span> via WinRM — ambiente
                acadêmico de demonstração.
              </p>

              {integrated && (
                <div style={{ marginTop: 12, maxWidth: 520 }}>
                  <input
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    placeholder="Pesquisar serviço..."
                    className="svc-search"
                    aria-label="Pesquisar serviço"
                    autoComplete="off"
                    spellCheck={false}
                  />
                </div>
              )}
            </div>

            <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
              {integrated && (
                <button
                  type="button"
                  className="back-link"
                  onClick={fetchServices}
                  disabled={loading}
                  title="Recarregar lista de serviços"
                >
                  ↻ Atualizar
                </button>
              )}

              <Link to="/servers" className="back-link">
                ← Voltar para a lista
              </Link>
            </div>
          </div>

          {!integrated && (
            <div className="muted-note" style={{ marginTop: 10 }}>
              Somente o <strong>SRV-DEMO-01</strong> está integrado ao WinRM no ambiente de
              demonstração. Os demais servidores são ilustrativos.
            </div>
          )}

          {error && (
            <div className="muted-note" style={{ marginTop: 10, borderColor: "rgba(239,35,60,.35)" }}>
              {error}
            </div>
          )}

          {integrated && (
            <>
              <div className="table-wrap" style={{ marginTop: 14 }}>
                <table className="services-table">
                  <thead>
                    <tr>
                      <th>Serviço</th>
                      <th>Status</th>
                      <th>Inicialização</th>
                      <th className="actions-col">Ações</th>
                    </tr>
                  </thead>

                  <tbody>
                    {loading ? (
                      <tr>
                        <td colSpan={4} style={{ padding: 18, color: "var(--fan-gray)" }}>
                          Carregando serviços...
                        </td>
                      </tr>
                    ) : filteredServices.length === 0 ? (
                      <tr>
                        <td colSpan={4} style={{ padding: 18, color: "var(--fan-gray)" }}>
                          {query.trim()
                            ? "Nenhum serviço encontrado para a busca."
                            : "Nenhum serviço retornado."}
                        </td>
                      </tr>
                    ) : (
                      filteredServices.map((svc) => {
                        const busy = busyService === svc.name;

                        return (
                          <tr key={svc.name}>
                            <td>
                              <div className="svc-name">{svc.displayName || svc.name}</div>
                              <div className="svc-meta">{svc.name}</div>
                            </td>

                            <td>
                              <span className={`status-pill status-${svc.status}`}>
                                {statusLabel(svc.status)}
                              </span>
                            </td>

                            <td>
                              <span className="startup-pill">{svc.startType ?? "unknown"}</span>
                            </td>

                            <td className="actions-col">
                              <div className="svc-actions">
                                <button
                                  type="button"
                                  className="icon-btn"
                                  onClick={() => doAction("start", svc.name)}
                                  title="Iniciar"
                                  aria-label="Iniciar"
                                  disabled={busy}
                                >
                                  <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
                                    <path d="M8 5v14l11-7z" fill="currentColor" />
                                  </svg>
                                </button>

                                <button
                                  type="button"
                                  className="icon-btn"
                                  onClick={() => doAction("stop", svc.name)}
                                  title="Parar"
                                  aria-label="Parar"
                                  disabled={busy}
                                >
                                  <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
                                    <path d="M7 7h10v10H7z" fill="currentColor" />
                                  </svg>
                                </button>

                                <button
                                  type="button"
                                  className="icon-btn icon-btn-danger"
                                  onClick={() => doAction("restart", svc.name)}
                                  title="Reiniciar"
                                  aria-label="Reiniciar"
                                  disabled={busy}
                                >
                                  <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
                                    <path
                                      d="M17.65 6.35A7.95 7.95 0 0 0 12 4V1L7 6l5 5V7a5 5 0 1 1-5 5H5a7 7 0 1 0 12.65-5.65z"
                                      fill="currentColor"
                                    />
                                  </svg>
                                </button>
                              </div>
                            </td>
                          </tr>
                        );
                      })
                    )}
                  </tbody>
                </table>
              </div>

              <div className="panel-foot">
                <div className="muted-note">
                  * As ações chamam o backend via WinRM e a interface atualiza a linha de forma
                  otimista. Para validar o estado real, use o botão <strong>Atualizar</strong>.
                </div>
              </div>
            </>
          )}
        </div>
      </main>
    </div>
  );
}