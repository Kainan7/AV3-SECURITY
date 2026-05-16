# app/config.py
"""
Configuração central do backend.

Responsabilidades:
- Carregar variáveis de ambiente do arquivo .env.
- Expor constantes usadas pelo backend.
- Permitir execução em modo acadêmico/mock sem dependência obrigatória de LDAP real.
- Validar apenas as variáveis necessárias conforme o modo de execução.

Modos principais:
- AUTH_MODE=mock: autenticação local de demonstração.
- AUTH_MODE=ldap: autenticação via LDAP/AD configurado.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict

from dotenv import load_dotenv


# -------------------------------------------------
# Carrega .env da raiz do backend
# Ex.: backend/.env
# -------------------------------------------------
load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")


# -------------------------------------------------
# Helpers
# -------------------------------------------------
def _getenv(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def _getenv_bool(name: str, default: str = "false") -> bool:
    return _getenv(name, default).lower() in ("1", "true", "yes", "y", "on")


def _required(var_name: str, value: str) -> None:
    """
    Valida variável obrigatória.

    Falhar no startup é melhor do que falhar no meio de uma requisição.
    """
    if value is None or str(value).strip() == "":
        raise RuntimeError(f"[CONFIG] Variável obrigatória não definida: {var_name}")


def _parse_mock_users(raw: str) -> Dict[str, str]:
    """
    Converte MOCK_USERS em dicionário.

    Formato esperado:
    MOCK_USERS=admin.demo:admin123,operator.demo:operator123

    Retorno:
    {
        "admin.demo": "admin123",
        "operator.demo": "operator123"
    }
    """
    users: Dict[str, str] = {}

    for item in raw.split(","):
        item = item.strip()
        if not item:
            continue

        if ":" not in item:
            continue

        username, password = item.split(":", 1)
        username = username.strip()
        password = password.strip()

        if username and password:
            users[username] = password

    return users


# -------------------------------------------------
# Ambiente / modo de autenticação
# -------------------------------------------------
APP_ENV: str = _getenv("APP_ENV", "demo")
AUTH_MODE: str = _getenv("AUTH_MODE", "mock").lower()


# -------------------------------------------------
# Usuários mockados para apresentação acadêmica
# -------------------------------------------------
MOCK_USERS_RAW: str = _getenv(
    "MOCK_USERS",
    "admin.demo:admin123,operator.demo:operator123",
)
MOCK_USERS: Dict[str, str] = _parse_mock_users(MOCK_USERS_RAW)


# -------------------------------------------------
# LDAP / AD
# Obrigatório apenas quando AUTH_MODE=ldap
# -------------------------------------------------
LDAP_SERVER: str = _getenv("LDAP_SERVER")
LDAP_PORT: int = int(_getenv("LDAP_PORT", "389"))

LDAP_USER: str = _getenv("LDAP_USER")
LDAP_PASSWORD: str = _getenv("LDAP_PASSWORD")
LDAP_DOMAIN: str = _getenv("LDAP_DOMAIN", "demo.local")
LDAP_SEARCH_BASE: str = _getenv("LDAP_SEARCH_BASE")


# -------------------------------------------------
# JWT
# -------------------------------------------------
JWT_SECRET_KEY: str = _getenv(
    "JWT_SECRET_KEY",
    "dev-only-change-this-secret-key",
)
JWT_EXPIRE_MINUTES: int = int(_getenv("JWT_EXPIRE_MINUTES", "60"))


# -------------------------------------------------
# WinRM
# Para apresentação:
# - WINRM_HOST deve apontar para a VM Windows de demonstração.
# - Não usar IP, usuário ou senha da empresa.
# -------------------------------------------------
WINRM_HOST: str = _getenv("WINRM_HOST", "127.0.0.1")
WINRM_PORT: int = int(_getenv("WINRM_PORT", "5985"))

WINRM_USER: str = _getenv("WINRM_USER", "demo-admin")
WINRM_PASSWORD: str = _getenv("WINRM_PASSWORD", "demo-password")

WINRM_TRANSPORT: str = _getenv("WINRM_TRANSPORT", "ntlm")
WINRM_USE_SSL: bool = _getenv_bool("WINRM_USE_SSL", "false")

WINRM_SCHEME: str = "https" if WINRM_USE_SSL else "http"


# -------------------------------------------------
# Validações obrigatórias
# -------------------------------------------------
if AUTH_MODE not in ("mock", "ldap"):
    raise RuntimeError("[CONFIG] AUTH_MODE inválido. Use 'mock' ou 'ldap'.")

if AUTH_MODE == "mock":
    if not MOCK_USERS:
        raise RuntimeError("[CONFIG] MOCK_USERS não possui usuários válidos.")

if AUTH_MODE == "ldap":
    _required("LDAP_SERVER", LDAP_SERVER)
    _required("LDAP_USER", LDAP_USER)
    _required("LDAP_PASSWORD", LDAP_PASSWORD)
    _required("LDAP_DOMAIN", LDAP_DOMAIN)
    _required("LDAP_SEARCH_BASE", LDAP_SEARCH_BASE)

_required("JWT_SECRET_KEY", JWT_SECRET_KEY)

_required("WINRM_HOST", WINRM_HOST)
_required("WINRM_USER", WINRM_USER)
_required("WINRM_PASSWORD", WINRM_PASSWORD)