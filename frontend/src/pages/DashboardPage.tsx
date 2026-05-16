import { Link, NavLink, useNavigate } from "react-router-dom";
import { useEffect, useMemo, useRef, useState } from "react";
import "../styles/dashboard.css";

import { emitUiEvent } from "../api/logs";
import {
  getDashboardSnapshot,
  openDashboardStream,
  type AlertItem,
  type ServiceEvent,
  type Snapshot,
} from "../api/dashboard";

function toServLabel(id: string) {
  const n = Number(id);
  if (!Number.isFinite(n)) return `SRV-DEMO-${id}`;
  return `SRV-DEMO-${String(n).padStart(2, "0")}`;
}

function eventKey(ev: ServiceEvent) {
  return `${ev.ts}|${ev.server_id}|${ev.service_name}|${ev.acao}|${ev.status}|${ev.mensagem}`;
}

function toActionLabel(a: ServiceEvent["acao"]) {
  switch (a) {
    case "START":
      return "INICIADO";
    case "STOP":
      return "PARADO";
    case "RESTART":
      return "REINICIADO";
    case "ERROR":
      return "ERRO";
    case "STATUS_CHANGE":
      return "STATUS";
    default:
      return a;
  }
}

function toStatusClass(status: ServiceEvent["status"]) {
  switch (status) {
    case "running":
      return "evt-pill evt-ok";
    case "stopped":
      return "evt-pill evt-bad";
    case "paused":
      return "evt-pill evt-warn";
    default:
      return "evt-pill evt-unk";
  }
}

function serviceLink(serverId: string, serviceName: string) {
  const hash = `#svc-${encodeURIComponent(serviceName)}`;
  const qs = `?service=${encodeURIComponent(serviceName)}`;
  return `/servers/${serverId}${qs}${hash}`;
}

type TopService = {
  key: string;
  server_id: string;
  service_name: string;
  count: number;
  last_ts: string;
  last_status: ServiceEvent["status"];
  last_action: ServiceEvent["acao"];
};

export function DashboardPage() {
  const navigate = useNavigate();
  const username = localStorage.getItem("restart_user") ?? "usuário";

  const [snap, setSnap] = useState<Snapshot | null>(null);
  const [connected, setConnected] = useState(false);
  const [refreshing, setRefreshing] = useState(false);

  const seenKeysRef = useRef<Set<string>>(new Set());

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

  async function hardRefreshSnapshot() {
    setRefreshing(true);

    try {
      const data = await getDashboardSnapshot();
      setSnap({ ...data });

      const keys = new Set<string>();
      for (const ev of data.recent_events ?? []) keys.add(eventKey(ev));
      seenKeysRef.current = keys;

      emitUiEvent({
        nivel: "INFO",
        origem: "UI",
        acao: "DASHBOARD_REFRESH",
        mensagem: `${username} atualizou o dashboard.`,
        sucesso: true,
      }).catch(() => {});
    } catch {
      emitUiEvent({
        nivel: "WARN",
        origem: "UI",
        acao: "DASHBOARD_REFRESH",
        mensagem: `${username} tentou atualizar o dashboard, mas falhou.`,
        sucesso: false,
      }).catch(() => {});
    } finally {
      setRefreshing(false);
    }
  }

  useEffect(() => {
    let alive = true;

    getDashboardSnapshot()
      .then((data) => {
        if (!alive) return;
        setSnap(data);

        const keys = new Set<string>();
        for (const ev of data.recent_events ?? []) keys.add(eventKey(ev));
        seenKeysRef.current = keys;
      })
      .catch(() => {});

    const es = openDashboardStream();

    es.addEventListener("open", () => setConnected(true));
    es.addEventListener("error", () => setConnected(false));

    es.addEventListener("SNAPSHOT", (e: MessageEvent) => {
      try {
        const data = JSON.parse(e.data) as Snapshot;
        setSnap(data);

        const keys = new Set<string>();
        for (const ev of data.recent_events ?? []) keys.add(eventKey(ev));
        seenKeysRef.current = keys;
      } catch {}
    });

    es.addEventListener("ALERTS_UPDATED", (e: MessageEvent) => {
      try {
        const alerts = JSON.parse(e.data) as AlertItem[];
        setSnap((prev) => (prev ? { ...prev, alerts } : prev));
      } catch {}
    });

    es.addEventListener("SERVICE_CHANGED", (e: MessageEvent) => {
      try {
        const evt = JSON.parse(e.data) as ServiceEvent;
        const key = eventKey(evt);

        if (seenKeysRef.current.has(key)) return;
        seenKeysRef.current.add(key);

        if (seenKeysRef.current.size > 120) {
          const arr = Array.from(seenKeysRef.current);
          seenKeysRef.current = new Set(arr.slice(0, 80));
        }

        setSnap((prev) =>
          prev
            ? {
                ...prev,
                recent_events: [evt, ...(prev.recent_events ?? [])].slice(0, 20),
              }
            : prev
        );
      } catch {}
    });

    return () => {
      alive = false;
      es.close();
    };
  }, []);

  const alerts = snap?.alerts ?? [];
  const kpis = snap?.kpis ?? { total: 0, online: 0, offline: 0, unknown: 0 };

  const topAlerts = useMemo(() => alerts.slice(0, 6), [alerts]);

  const recentUiEvents = useMemo(() => {
    const list = snap?.recent_events ?? [];
    return list.slice(0, 6);
  }, [snap?.recent_events]);

  const topServices = useMemo<TopService[]>(() => {
    const list = snap?.recent_events ?? [];
    const map = new Map<string, TopService>();

    for (const ev of list) {
      const key = `${ev.server_id}|${ev.service_name}`;
      const prev = map.get(key);

      if (!prev) {
        map.set(key, {
          key,
          server_id: ev.server_id,
          service_name: ev.service_name,
          count: 1,
          last_ts: ev.ts,
          last_status: ev.status,
          last_action: ev.acao,
        });
      } else {
        prev.count += 1;

        if (new Date(ev.ts).getTime() > new Date(prev.last_ts).getTime()) {
          prev.last_ts = ev.ts;
          prev.last_status = ev.status;
          prev.last_action = ev.acao;
        }
      }
    }

    return Array.from(map.values())
      .sort(
        (a, b) =>
          b.count - a.count ||
          new Date(b.last_ts).getTime() - new Date(a.last_ts).getTime()
      )
      .slice(0, 4);
  }, [snap?.recent_events]);

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
          <div className="dash-head">
            <div>
              <h2 className="dash-title">DASHBOARD</h2>
              <p className="dash-subtitle">
                Visão operacional em tempo real. Prioridade para alertas e eventos recentes.
              </p>

              <div className="dash-conn">
                <span className={connected ? "dash-pill dash-pill-ok" : "dash-pill dash-pill-bad"}>
                  {connected ? "AO VIVO" : "DESCONECTADO"}
                </span>

                {snap?.updated_at && (
                  <span className="dash-meta">
                    Atualizado: {new Date(snap.updated_at).toLocaleString("pt-BR")}
                  </span>
                )}
              </div>
            </div>

            <div className="dash-actions">
              <Link to="/servers" className="dash-back">
                ← Voltar para a lista
              </Link>

              <button
                type="button"
                className="dash-refresh"
                onClick={hardRefreshSnapshot}
                disabled={refreshing}
                aria-busy={refreshing}
                title="Atualiza o snapshot via API"
              >
                {refreshing ? "Atualizando..." : "Atualizar"}
              </button>
            </div>
          </div>

          <section className="dash-alerts">
            <div className="dash-section-head">
              <h3 className="dash-section-title">ALERTAS ATIVOS</h3>
              <span className="dash-badge">{alerts.length}</span>
            </div>

            {topAlerts.length === 0 ? (
              <div className="dash-empty">Nenhum alerta no momento.</div>
            ) : (
              <ul className="alert-list">
                {topAlerts.map((a, idx) => {
                  const isCritical = a.nivel === "CRITICAL";
                  const cls = isCritical ? "alert-row alert-critical" : "alert-row alert-warning";
                  const sid = a.server_id;

                  return (
                    <li key={`${a.ts}-${idx}`} className={cls}>
                      <span className="alert-dot" />

                      <div className="alert-main">
                        <div className="alert-line">
                          <span className="alert-strong">{toServLabel(sid)}</span>
                          <span className="alert-sep">—</span>
                          <span className="alert-msg">{a.mensagem}</span>
                        </div>

                        {a.service_name ? (
                          <div className="alert-sub">
                            Serviço:{" "}
                            <Link className="alert-svc" to={serviceLink(sid, a.service_name)}>
                              {a.service_name}
                            </Link>
                          </div>
                        ) : null}
                      </div>

                      <Link to={`/servers/${sid}`} className="alert-cta">
                        Ver servidor
                      </Link>
                    </li>
                  );
                })}
              </ul>
            )}
          </section>

          <section className="dash-section">
            <h3 className="dash-section-title">Resumo Operacional</h3>

            <div className="kpi-grid">
              <div className="kpi-card">
                <div className="kpi-label">Total</div>
                <div className="kpi-value">{kpis.total}</div>
                <div className="kpi-foot">servidores</div>
              </div>

              <div className="kpi-card">
                <div className="kpi-label">Online</div>
                <div className="kpi-value kpi-online">{kpis.online}</div>
                <div className="kpi-foot">OK</div>
              </div>

              <div className="kpi-card">
                <div className="kpi-label">Offline</div>
                <div className="kpi-value kpi-offline">{kpis.offline}</div>
                <div className="kpi-foot">crítico</div>
              </div>

              <div className="kpi-card">
                <div className="kpi-label">Unknown</div>
                <div className="kpi-value kpi-unknown">{kpis.unknown}</div>
                <div className="kpi-foot">atenção</div>
              </div>
            </div>
          </section>

          <section className="dash-section">
            <div className="dash-split-head">
              <div>
                <h3 className="dash-section-title">Serviços mais acionados</h3>
                <div className="dash-note">Baseado nos eventos recentes do dashboard</div>
              </div>
            </div>

            {topServices.length === 0 ? (
              <div className="dash-empty">Sem dados de serviços ainda.</div>
            ) : (
              <ul className="topsvc-list">
                {topServices.map((it) => (
                  <li key={it.key} className="topsvc-item">
                    <div className="topsvc-left">
                      <div className="topsvc-name">{it.service_name}</div>
                      <div className="topsvc-meta">
                        Última ação:{" "}
                        <span className="topsvc-strong">
                          {new Date(it.last_ts).toLocaleTimeString("pt-BR", { hour12: false })}
                        </span>{" "}
                        •{" "}
                        <Link className="topsvc-link" to={`/servers/${it.server_id}`}>
                          {toServLabel(it.server_id)}
                        </Link>
                      </div>
                    </div>

                    <div className="topsvc-right">
                      <span className={toStatusClass(it.last_status)}>{it.last_status}</span>
                      <span className="topsvc-count">{it.count}x</span>
                      <Link className="topsvc-open" to={serviceLink(it.server_id, it.service_name)}>
                        Abrir
                      </Link>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section className="dash-section">
            <div className="dash-split-head">
              <div>
                <h3 className="dash-section-title">Eventos Recentes</h3>
                <div className="dash-note">Máximo 6 • Histórico completo em Logs</div>
              </div>
            </div>

            {recentUiEvents.length === 0 ? (
              <div className="dash-empty">Sem eventos recentes.</div>
            ) : (
              <div className="events-box" role="region" aria-label="Eventos recentes">
                <ul className="events-list">
                  {recentUiEvents.map((ev) => (
                    <li key={eventKey(ev)} className="event-row">
                      <div className="event-time">
                        {new Date(ev.ts).toLocaleTimeString("pt-BR", { hour12: false })}
                      </div>

                      <div className="event-main">
                        <div className="event-line">
                          <Link className="event-server" to={`/servers/${ev.server_id}`}>
                            {toServLabel(ev.server_id)}
                          </Link>

                          <span className="event-sep">•</span>

                          <Link
                            className="event-service"
                            to={serviceLink(ev.server_id, ev.service_name)}
                          >
                            {ev.service_name}
                          </Link>

                          <span className={toStatusClass(ev.status)}>{ev.status}</span>
                          <span className="event-action">{toActionLabel(ev.acao)}</span>
                        </div>

                        <div className="event-msg">{ev.mensagem}</div>
                      </div>

                      <Link to={`/servers/${ev.server_id}`} className="event-cta">
                        Ver servidor
                      </Link>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            <div className="dash-footer-actions">
              <Link to="/logs" className="dash-audit-cta">
                Ver auditoria completa →
              </Link>
            </div>
          </section>
        </div>
      </main>
    </div>
  );
}