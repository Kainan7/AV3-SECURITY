// src/api/http.ts
import axios from "axios";

/**
 * URL base do backend.
 *
 * Exemplos:
 * - DEV local: http://127.0.0.1:8000
 * - VM demo:   http://IP_DA_VM:4000
 *
 * Vite lê variáveis que começam com VITE_
 * Ex:
 * VITE_API_BASE_URL=http://127.0.0.1:8000
 * VITE_API_BASE_URL=http://IP_DA_VM:4000
 */
export const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

/**
 * Instância única do Axios.
 * - Centraliza baseURL
 * - Centraliza interceptors (JWT / 401)
 */
export const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    "Content-Type": "application/json",
  },
});

// Alias opcional para manter o padrão de chamadas como http.get/http.post
export const http = api;

/**
 * Request interceptor:
 * - Anexa JWT no Authorization
 */
api.interceptors.request.use((config) => {
  const token = localStorage.getItem("restart_token");

  if (token) {
    config.headers = config.headers ?? {};
    config.headers["Authorization"] = `Bearer ${token}`;
  }

  return config;
});

/**
 * Response interceptor:
 * - Se 401, limpa a sessão local e redireciona para /login
 */
api.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error?.response?.status;

    if (status === 401) {
      localStorage.removeItem("restart_token");
      localStorage.removeItem("restart_user");

      if (window.location.pathname !== "/login") {
        window.location.href = "/login";
      }
    }

    return Promise.reject(error);
  }
);