"""
Teste manual de conexão WinRM.

Uso:
1) Configure as variáveis no .env ou no ambiente:
   WINRM_HOST
   WINRM_PORT
   WINRM_USER
   WINRM_PASSWORD
   WINRM_TRANSPORT

2) Execute:
   python tests/test_winrm.py

Observação:
- Este teste não deve conter IPs, usuários ou senhas hardcoded.
- Para apresentação acadêmica, use uma VM Windows própria de demonstração.
"""

import os
from pathlib import Path

import winrm
from dotenv import load_dotenv


load_dotenv(dotenv_path=Path(__file__).resolve().parents[1] / ".env")


HOST = os.getenv("WINRM_HOST", "127.0.0.1")
PORT = int(os.getenv("WINRM_PORT", "5985"))
USER = os.getenv("WINRM_USER", "demo-admin")
PASSWORD = os.getenv("WINRM_PASSWORD", "demo-password")
TRANSPORT = os.getenv("WINRM_TRANSPORT", "ntlm")
USE_SSL = os.getenv("WINRM_USE_SSL", "false").lower() == "true"

SCHEME = "https" if USE_SSL else "http"


def main():
    endpoint = f"{SCHEME}://{HOST}:{PORT}/wsman"

    session = winrm.Session(
        endpoint,
        auth=(USER, PASSWORD),
        transport=TRANSPORT,
        server_cert_validation="ignore" if USE_SSL else "validate",
    )

    ps = r"""
    Get-Service |
    Select-Object -First 15 Name, DisplayName, Status, StartType |
    ConvertTo-Json -Depth 4
    """

    result = session.run_ps(ps)

    print("ENDPOINT:", endpoint)
    print("STDOUT:\n", result.std_out.decode("utf-8", errors="ignore"))
    print("STDERR:\n", result.std_err.decode("utf-8", errors="ignore"))
    print("CODE:", result.status_code)


if __name__ == "__main__":
    main()