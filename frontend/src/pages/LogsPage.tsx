// src/pages/LogsPage.tsx
import { useEffect, useMemo, useRef, useState } from "react";
import { NavLink, useNavigate } from "react-router-dom";
import "../styles/logs.css";

import { fetchLogs, emitUiEvent, clearLogs as clearLogsApi } from "../api/logs";
import type { AuditLogItem, LogLevel } from "../api/logs";

type LevelFilter = LogLevel | "ALL";

function toTime(tsIso: string) {
  const d = new Date(tsIso);
  return d.toLocaleTimeString("pt-BR", { hour12: false });
}

function isNearBottom(el: HTMLDivElement, thresholdPx = 80) {
  const distance = el.scrollHeight - el.scrollTop - el.clientHeight;
  return distance <= thresholdPx;
}

function toServLabel(id: string) {
  const n = Number(id);
  if (!Number.isFinite(n)) return `SRV-DEMO-${id}`;
  return `SRV-DEMO-${String(n).padStart(2, "0")}`;
}

export function LogsPage() {
  const navigate = useNavigate();
  const username = localStorage.getItem("restart_user") ?? "usuário";

  const terminalRef = useRef<HTMLDivElement | null>(null);

  const [autoScroll, setAutoScroll] = useState(false);
  const [levelFilter, setLevelFilter] = useState<LevelFilter>("ALL");
  const [query, setQuery] = useState("");

  const [logs, setLogs] = useState<AuditLogItem[]>([]);
  const [error, setError] = useState<string | null>(null);

  const aliveRef = useRef(true);
  const clearInFlightRef = useRef(false);

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

  useEffect(() => {
    aliveRef.current = true;

    async function tick() {
      if (!aliveRef.current) return;

      try {
        const items = await fetchLogs(1000);
        setError(null);

        setLogs((prev) => {
          const map = new Map<string, AuditLogItem>();

          for (const p of prev) map.set(p.id, p);
          for (const it of items) map.set(it.id, it);

          const merged = Array.from(map.values()).sort(
            (a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
          );

          return merged.length > 1000 ? merged.slice(merged.length - 1000) : merged;
        });
      } catch {
        setError("Falha ao buscar logs do backend.");
      }
    }

    tick();
    const timer = window.setInterval(tick, 1200);

    return () => {
      aliveRef.current = false;
      window.clearInterval(timer);
    };
  }, []);

  useEffect(() => {
    if (!autoScroll) return;

    const el = terminalRef.current;
    if (!el) return;

    if (!isNearBottom(el, 200)) return;

    el.scrollTo({ top: el.scrollHeight, behavior: "auto" });
  }, [logs, autoScroll]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();

    return logs.filter((l) => {
      const okLevel = levelFilter === "ALL" ? true : l.nivel === levelFilter;

      const hay =
        `${l.timestamp} ${l.nivel} ${l.usuario} ${l.origem} ${l.acao} ${l.servidor_nome ?? ""} ${
          l.servidor_id ?? ""
        } ${l.servico ?? ""} ${l.mensagem ?? ""} ${l.detalhe ?? ""}`.toLowerCase();

      const okQuery = !q ? true : hay.includes(q);

      return okLevel && okQuery;
    });
  }, [logs, levelFilter, query]);

  async function clearLogs() {
    if (clearInFlightRef.current) return;
    clearInFlightRef.current = true;

    try {
      await clearLogsApi();
      setLogs([]);

      emitUiEvent({
        nivel: "INFO",
        origem: "UI",
        acao: "LOGS_CLEAR",
        mensagem: `${username} limpou a tela de logs.`,
        sucesso: true,
      }).catch(() => {});
    } catch {
      setError("Falha ao limpar logs.");
    } finally {
      window.setTimeout(() => {
        clearInFlightRef.current = false;
      }, 400);
    }
  }

  function toggleFollow() {
    setAutoScroll((prev) => {
      const next = !prev;

      if (next) {
        requestAnimationFrame(() => {
          const el = terminalRef.current;
          if (el) el.scrollTo({ top: el.scrollHeight, behavior: "auto" });
        });
      }

      return next;
    });
  }

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
          <div className="logs-head">
            <div>
              <h2 className="logs-title">LOGS</h2>
              <p className="logs-subtitle">
                Auditoria em tempo real: acessos, navegação e ações em serviços.
              </p>

              {error ? (
                <p className="muted" style={{ marginTop: 8 }}>
                  {error}
                </p>
              ) : null}
            </div>

            <div className="logs-actions">
              <button
                type="button"
                className={`logs-btn ${autoScroll ? "logs-btn-on" : ""}`}
                onClick={toggleFollow}
                aria-pressed={autoScroll}
                title="Seguir logs"
              >
                {autoScroll ? "Seguir: ON" : "Seguir: OFF"}
              </button>

              <button type="button" className="logs-btn logs-btn-danger" onClick={clearLogs}>
                Limpar
              </button>
            </div>
          </div>

          <div className="logs-toolbar">
            <div className="logs-filters">
              {(["ALL", "INFO", "WARN", "ERROR"] as const).map((lvl) => (
                <button
                  key={lvl}
                  type="button"
                  className={`filter-chip ${levelFilter === lvl ? "is-active" : ""}`}
                  onClick={() => setLevelFilter(lvl)}
                >
                  {lvl}
                </button>
              ))}
            </div>

            <div className="logs-search">
              <input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Buscar: SRV-DEMO-01, Spooler, LOGIN, timeout..."
              />
            </div>
          </div>

          <div className="terminal">
            <div className="terminal-topbar">
              <span className="dot red" />
              <span className="dot yellow" />
              <span className="dot green" />
              <span className="terminal-title">restart-server • audit-log</span>
              <span className="terminal-badge">AO VIVO</span>
            </div>

            <div ref={terminalRef} className="terminal-body" role="log" aria-live="polite">
              {filtered.length === 0 ? (
                <div className="terminal-empty">Nenhum log ainda ou filtros aplicados.</div>
              ) : (
                filtered.map((l) => (
                  <div key={l.id} className={`log-row level-${l.nivel}`}>
                    <span className="log-ts">[{toTime(l.timestamp)}]</span>
                    <span className="log-level">{l.nivel}</span>

                    <span className="log-meta">
                      ({l.origem}) {l.usuario}
                      {l.servidor_nome ? ` • ${l.servidor_nome}` : ""}
                      {!l.servidor_nome && l.servidor_id ? ` • ${toServLabel(l.servidor_id)}` : ""}
                      {l.servico ? ` • ${l.servico}` : ""}:
                    </span>

                    <span className="log-msg">
                      {l.mensagem ?? `Evento: ${l.acao}`}
                      {l.detalhe ? ` (${l.detalhe})` : ""}
                    </span>
                  </div>
                ))
              )}
            </div>
          </div>

          <div className="logs-foot">
            <span className="muted">Retenção local: últimos 1000 eventos. Auto-scroll inicia OFF.</span>
          </div>
        </div>
      </main>
    </div>
  );
}