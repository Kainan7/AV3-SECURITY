// src/App.tsx
import { Routes, Route, Navigate, useLocation } from "react-router-dom";
import { useEffect } from "react";

import { ServerSelectPage } from "./pages/ServerSelectPage";
import { ServerDetailsPage } from "./pages/ServerDetailsPage";
import { DashboardPage } from "./pages/DashboardPage";
import { LogsPage } from "./pages/LogsPage";
import LoginPage from "./pages/LoginPage";

import { emitUiEvent } from "./api/logs";
import "./styles/App.css";

function PrivateRoute({ children }: { children: React.ReactElement }) {
  const token = localStorage.getItem("restart_token");
  if (!token) return <Navigate to="/login" replace />;
  return children;
}

function buildNavigateMessage(username: string, path: string) {
  if (path === "/servers") return `${username} acessou a tela de servidores.`;
  if (path === "/dashboard") return `${username} acessou o dashboard.`;
  if (path === "/logs") return `${username} acessou a tela de logs.`;

  if (path.startsWith("/servers/")) {
    const id = path.split("/")[2] || "?";
    const serv = `SRV-DEMO-${String(id).padStart(2, "0")}`;
    return `${username} acessou o servidor ${serv}.`;
  }

  return `${username} navegou para ${path}.`;
}

function RouteAudit() {
  const location = useLocation();

  useEffect(() => {
    const token = localStorage.getItem("restart_token");
    if (!token) return;

    const username = localStorage.getItem("restart_user") ?? "usuário";
    const path = location.pathname;

    const key = `audit:navigate:${path}`;
    const last = sessionStorage.getItem(key);
    const now = Date.now();

    if (last && now - Number(last) < 1500) return;
    sessionStorage.setItem(key, String(now));

    const msg = buildNavigateMessage(username, path);

    emitUiEvent({
      nivel: "INFO",
      origem: "UI",
      acao: "NAVIGATE",
      mensagem: msg,
      sucesso: true,
    }).catch(() => {});
  }, [location.pathname]);

  return null;
}

function App() {
  return (
    <>
      <RouteAudit />

      <Routes>
        <Route path="/" element={<Navigate to="/servers" replace />} />

        <Route path="/login" element={<LoginPage />} />

        <Route
          path="/servers"
          element={
            <PrivateRoute>
              <ServerSelectPage />
            </PrivateRoute>
          }
        />

        <Route
          path="/servers/:id"
          element={
            <PrivateRoute>
              <ServerDetailsPage />
            </PrivateRoute>
          }
        />

        <Route
          path="/dashboard"
          element={
            <PrivateRoute>
              <DashboardPage />
            </PrivateRoute>
          }
        />

        <Route
          path="/logs"
          element={
            <PrivateRoute>
              <LogsPage />
            </PrivateRoute>
          }
        />

        <Route path="*" element={<Navigate to="/servers" replace />} />
      </Routes>
    </>
  );
}

export default App;