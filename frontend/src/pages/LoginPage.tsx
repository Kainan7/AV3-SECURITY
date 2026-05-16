import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/http";
import "../styles/login.css";

interface TokenResponse {
  access_token: string;
}

function EyeOpenIcon() {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width="20"
      height="20"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
      <circle cx="12" cy="12" r="3" />
    </svg>
  );
}

function EyeOffIcon() {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width="20"
      height="20"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M17.94 17.94A10.94 10.94 0 0 1 12 20C5 20 1 12 1 12a21.77 21.77 0 0 1 5.06-7.94" />
      <path d="M1 1l22 22" />
      <path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a21.78 21.78 0 0 1-4.87 6.5" />
      <path d="M14.12 14.12a3 3 0 0 1-4.24-4.24" />
    </svg>
  );
}

function DemoLogo() {
  return (
    <div className="demo-logo" aria-label="Restart Server Demo">
      <span>RS</span>
    </div>
  );
}

export default function LoginPage() {
  const navigate = useNavigate();

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");

  const [showPassword, setShowPassword] = useState(false);

  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);

    const usuario = username.trim();

    localStorage.removeItem("restart_token");
    localStorage.removeItem("restart_user");

    try {
      const response = await api.post<TokenResponse>("/auth/login", {
        usuario,
        senha: password,
      });

      localStorage.setItem("restart_user", usuario);
      localStorage.setItem("restart_token", response.data.access_token);

      navigate("/servers");
    } catch (err: any) {
      console.error(err);

      const status = err?.response?.status;

      if (status === 401) {
        setError("Usuário ou senha inválidos.");
      } else if (status) {
        setError(`Falha ao autenticar (HTTP ${status}).`);
      } else {
        setError("Falha de conexão com o backend. Verifique se a API está ativa.");
      }
    } finally {
      setLoading(false);
    }
  }

  function togglePassword() {
    if (!password) return;
    setShowPassword((prev) => !prev);
  }

  return (
    <div className="login-page">
      <div className="login-layout">
        <div className="login-left demo-theme">
          <div className="login-left-content">
            <DemoLogo />

            <div className="login-divider" />

            <h1 className="login-left-title">Restart Server</h1>
            <h2 className="login-left-subtitle">
              Plataforma acadêmica de gerenciamento de serviços Windows
            </h2>
            <p className="login-left-text">
              Monitore servidores, visualize serviços e execute ações de start,
              stop e restart em um ambiente controlado de demonstração.
            </p>
          </div>
        </div>

        <div className="login-right">
          <div className="login-right-card">
            <h2 className="login-right-title">Acesse sua conta</h2>
            <p className="login-right-subtitle">
              Use as credenciais de demonstração configuradas no ambiente.
            </p>

            <form className="login-form" onSubmit={handleSubmit}>
              <div className="login-field">
                <label htmlFor="usuario">Usuário</label>
                <input
                  id="usuario"
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="Exemplo: admin.demo"
                  required
                />
              </div>

              <div className="login-field">
                <label htmlFor="senha">Senha</label>

                <div className="password-wrapper">
                  <input
                    id="senha"
                    type={showPassword ? "text" : "password"}
                    value={password}
                    onChange={(e) => {
                      setPassword(e.target.value);
                      if (e.target.value === "") setShowPassword(false);
                    }}
                    placeholder="Digite sua senha"
                    required
                    className="password-input"
                  />

                  <button
                    type="button"
                    className="password-toggle"
                    onClick={togglePassword}
                    aria-label={showPassword ? "Ocultar senha" : "Mostrar senha"}
                    aria-pressed={showPassword}
                    disabled={!password}
                  >
                    {showPassword ? <EyeOpenIcon /> : <EyeOffIcon />}
                  </button>
                </div>
              </div>

              {error && <p className="login-error">{error}</p>}

              <button className="login-button" type="submit" disabled={loading}>
                {loading ? "Entrando..." : "Entrar"}
              </button>
            </form>

            <p className="login-demo-hint">
              Ambiente demo: admin.demo / admin123
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}