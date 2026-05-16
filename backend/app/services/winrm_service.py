# app/services/winrm_service.py
from __future__ import annotations

"""
WinRMService
============

Camada de infraestrutura responsável por comunicação com Windows via WinRM.

Responsabilidades:
- Criar sessão WinRM.
- Executar comandos PowerShell remotamente.
- Listar serviços Windows.
- Iniciar, parar e reiniciar serviços.
- Validar nomes de serviços antes de montar comandos PowerShell.
- Classificar erros de WinRM em exceções específicas.
"""

import json
import re
from typing import Any, Dict, List

import winrm


# =========================================================
# Exceções customizadas
# =========================================================

class WinRMError(RuntimeError):
    """Erro genérico WinRM."""
    pass


class WinRMTimeoutError(WinRMError):
    """Timeout de rede ou execução WinRM."""
    pass


class WinRMAuthError(WinRMError):
    """Falha de autenticação/autorização WinRM."""
    pass


class WinRMCommandError(WinRMError):
    """PowerShell executou, mas retornou erro."""
    pass


class WinRMParseError(WinRMError):
    """Stdout retornou conteúdo que não é JSON válido."""
    pass


class InvalidServiceNameError(WinRMError):
    """Nome de serviço inválido ou potencialmente perigoso."""
    pass


# =========================================================
# Validação de entrada
# =========================================================

SERVICE_NAME_PATTERN = re.compile(r"^[A-Za-z0-9_.\- ]{1,120}$")


def _validate_service_name(name: str) -> str:
    """
    Valida o nome do serviço antes de inserir em comandos PowerShell.

    Permitido:
    - letras
    - números
    - espaço
    - ponto
    - underline
    - hífen

    Bloqueado:
    - aspas
    - ponto e vírgula
    - pipes
    - parênteses
    - variáveis PowerShell
    - qualquer caractere que possa alterar o comando
    """
    value = str(name or "").strip()

    if not value:
        raise InvalidServiceNameError("Service name cannot be empty.")

    if not SERVICE_NAME_PATTERN.fullmatch(value):
        raise InvalidServiceNameError(f"Invalid service name: {value}")

    return value


# =========================================================
# Classificação heurística de erros
# =========================================================

def _looks_like_timeout(msg: str) -> bool:
    m = (msg or "").lower()
    return any(
        s in m
        for s in [
            "timed out",
            "timeout",
            "read timeout",
            "operation timeout",
            "winrmoperationtimeouterror",
            "the wsman operation timed out",
        ]
    )


def _looks_like_auth(msg: str) -> bool:
    m = (msg or "").lower()
    return any(
        s in m
        for s in [
            "401",
            "unauthorized",
            "access is denied",
            "forbidden",
            "authorization",
            "ntlm",
            "kerberos",
            "bad credentials",
            "the specified credentials were rejected",
        ]
    )


class WinRMService:
    """
    Cliente WinRM com execução PowerShell e retorno JSON.
    """

    def __init__(
        self,
        *,
        operation_timeout_sec: int = 20,
        read_timeout_sec: int = 30,
    ):
        """
        Cria uma sessão WinRM usando configurações do ambiente.
        """
        from app.config import (
            WINRM_HOST,
            WINRM_PORT,
            WINRM_USER,
            WINRM_PASSWORD,
            WINRM_TRANSPORT,
            WINRM_USE_SSL,
            WINRM_SCHEME,
        )

        endpoint = f"{WINRM_SCHEME}://{WINRM_HOST}:{WINRM_PORT}/wsman"
        server_cert_validation = "ignore" if WINRM_USE_SSL else "validate"

        self.session = winrm.Session(
            target=endpoint,
            auth=(WINRM_USER, WINRM_PASSWORD),
            transport=WINRM_TRANSPORT,
            server_cert_validation=server_cert_validation,
        )

        try:
            self.session.protocol.operation_timeout_sec = int(operation_timeout_sec)
            self.session.protocol.read_timeout_sec = int(read_timeout_sec)
        except Exception:
            pass

    def _run_ps_json(self, ps: str) -> Any:
        """
        Executa PowerShell remoto e espera JSON no stdout.
        """
        try:
            r = self.session.run_ps(ps)
        except Exception as e:
            msg = str(e)

            if _looks_like_timeout(msg):
                raise WinRMTimeoutError(msg)

            if _looks_like_auth(msg):
                raise WinRMAuthError(msg)

            raise WinRMError(msg)

        if r.status_code != 0:
            out = (r.std_out or b"").decode("utf-8", errors="ignore")
            err = (r.std_err or b"").decode("utf-8", errors="ignore")

            detail = f"status={r.status_code} | stderr={err.strip()} | stdout={out.strip()}"

            if _looks_like_timeout(detail):
                raise WinRMTimeoutError(detail)

            if _looks_like_auth(detail):
                raise WinRMAuthError(detail)

            raise WinRMCommandError(detail)

        raw = (r.std_out or b"").decode("utf-8", errors="ignore").strip()

        if not raw:
            return None

        try:
            return json.loads(raw)
        except Exception as e:
            preview = raw[:500] + ("..." if len(raw) > 500 else "")
            raise WinRMParseError(f"{e} | raw_preview={preview}")

    def list_services(self, limit: int = 200) -> List[Dict[str, Any]]:
        """
        Lista serviços via Win32_Service.

        Retorna:
        - Name
        - DisplayName
        - State
        - StartMode
        """
        safe_limit = max(1, min(int(limit), 500))

        ps = f"""
        $items = Get-CimInstance Win32_Service |
            Select-Object Name, DisplayName, State, StartMode |
            Sort-Object DisplayName |
            Select-Object -First {safe_limit}

        $items | ConvertTo-Json -Depth 4
        """

        data = self._run_ps_json(ps)

        if data is None:
            return []
        if isinstance(data, dict):
            return [data]
        return data

    def get_service(self, name: str) -> Dict[str, Any]:
        """
        Busca um serviço específico pelo Name.
        """
        safe_name = _validate_service_name(name)

        ps = f"""
        $serviceName = @'
{safe_name}
'@

        $svc = Get-CimInstance Win32_Service -Filter "Name='$serviceName'" |
            Select-Object Name, DisplayName, State, StartMode

        if ($null -eq $svc) {{
            throw "Service not found"
        }}

        $svc | ConvertTo-Json -Depth 4
        """

        data = self._run_ps_json(ps)

        if isinstance(data, list) and data:
            return data[0]
        if isinstance(data, dict):
            return data

        raise WinRMCommandError("Service not found.")

    def start_service(self, name: str) -> Dict[str, Any]:
        """
        Inicia um serviço e retorna o estado atualizado.
        """
        safe_name = _validate_service_name(name)

        ps = f"""
        $serviceName = @'
{safe_name}
'@

        Start-Service -Name $serviceName -ErrorAction Stop
        Start-Sleep -Milliseconds 300

        $svc = Get-CimInstance Win32_Service -Filter "Name='$serviceName'" |
            Select-Object Name, DisplayName, State, StartMode

        $svc | ConvertTo-Json -Depth 4
        """

        return self._run_ps_json(ps)

    def stop_service(self, name: str) -> Dict[str, Any]:
        """
        Para um serviço e retorna o estado atualizado.
        """
        safe_name = _validate_service_name(name)

        ps = f"""
        $serviceName = @'
{safe_name}
'@

        Stop-Service -Name $serviceName -ErrorAction Stop
        Start-Sleep -Milliseconds 300

        $svc = Get-CimInstance Win32_Service -Filter "Name='$serviceName'" |
            Select-Object Name, DisplayName, State, StartMode

        $svc | ConvertTo-Json -Depth 4
        """

        return self._run_ps_json(ps)

    def restart_service(self, name: str) -> Dict[str, Any]:
        """
        Reinicia um serviço e retorna o estado atualizado.
        """
        safe_name = _validate_service_name(name)

        ps = f"""
        $serviceName = @'
{safe_name}
'@

        Restart-Service -Name $serviceName -ErrorAction Stop
        Start-Sleep -Milliseconds 500

        $svc = Get-CimInstance Win32_Service -Filter "Name='$serviceName'" |
            Select-Object Name, DisplayName, State, StartMode

        $svc | ConvertTo-Json -Depth 4
        """

        return self._run_ps_json(ps)