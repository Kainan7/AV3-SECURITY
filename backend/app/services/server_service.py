# app/services/server_service.py
from __future__ import annotations

"""
ServerService
=============

Camada de serviço usada pelas rotas /servers.

Responsabilidades:
- Listar servidores demonstrativos exibidos na UI.
- Listar serviços de um servidor via WinRM.
- Executar ações start/stop/restart via WinRM.
- Padronizar os dados retornados para o frontend.

Observação:
- O projeto acadêmico usa dados mockados para catálogo de servidores.
- Apenas o servidor de demonstração configurado no ambiente executa WinRM real.
"""

from typing import List

from app.models.schemas import Servidor, ServiceItem
from app.services.winrm_service import WinRMService


def _map_state_to_status(state: str) -> str:
    """
    Converte o estado vindo do WinRM para o padrão interno:
    running | stopped | paused | unknown
    """
    s = str(state or "").lower()

    if "running" in s:
        return "running"
    if "stopped" in s:
        return "stopped"
    if "paused" in s:
        return "paused"

    return "unknown"


def _map_startmode_to_starttype(mode: str) -> str:
    """
    Converte o StartMode vindo do WinRM para o padrão interno:
    automatic | manual | disabled | unknown
    """
    m = str(mode or "").lower()

    if "auto" in m:
        return "automatic"
    if "manual" in m:
        return "manual"
    if "disabled" in m:
        return "disabled"

    return "unknown"


class ServerService:
    """
    Serviço stateless responsável por operações relacionadas a servidores
    e serviços Windows.
    """

    @staticmethod
    def listar_servidores() -> List[Servidor]:
        """
        Retorna a lista mockada de servidores do ambiente acadêmico.

        Apenas o servidor id="1" deve ser conectado à VM real de demonstração.
        Os demais servidores são placeholders para demonstrar a interface,
        o dashboard e a lógica de status.
        """
        return [
            Servidor(
                id="1",
                nome="SRV-DEMO-01",
                descricao="Servidor Windows de demonstração",
                status="online",
            ),
            Servidor(
                id="2",
                nome="SRV-DEMO-02",
                descricao="Servidor de aplicação simulado",
                status="offline",
            ),
            Servidor(
                id="3",
                nome="SRV-DEMO-03",
                descricao="Servidor de banco de dados simulado",
                status="online",
            ),
            Servidor(
                id="4",
                nome="SRV-DEMO-04",
                descricao="Servidor de relatórios simulado",
                status="online",
            ),
            Servidor(
                id="5",
                nome="SRV-DEMO-05",
                descricao="Servidor de testes simulado",
                status="desconhecido",
            ),
            Servidor(
                id="6",
                nome="SRV-DEMO-06",
                descricao="Servidor auxiliar simulado",
                status="online",
            ),
        ]

    @staticmethod
    def listar_servicos(server_id: str, limit: int = 200) -> List[ServiceItem]:
        """
        Lista serviços do servidor informado.

        Regra do ambiente acadêmico:
        - Apenas server_id == "1" usa WinRM real.
        - Outros servidores retornam lista vazia.
        """
        if server_id != "1":
            return []

        winrm = WinRMService()
        raw = winrm.list_services(limit=limit)

        services: List[ServiceItem] = []

        for s in raw:
            name = s.get("Name", "")
            display = s.get("DisplayName", "") or name
            status = _map_state_to_status(s.get("State"))
            start_type = _map_startmode_to_starttype(s.get("StartMode"))

            services.append(
                ServiceItem(
                    name=name,
                    displayName=display,
                    status=status,
                    startType=start_type,
                )
            )

        return services

    @staticmethod
    def start(server_id: str, service_name: str) -> ServiceItem:
        """
        Inicia um serviço no servidor de demonstração e retorna o estado atualizado.
        """
        if server_id != "1":
            raise RuntimeError("Server not implemented in demo environment.")

        winrm = WinRMService()
        s = winrm.start_service(service_name)

        return ServiceItem(
            name=s.get("Name", service_name),
            displayName=s.get("DisplayName", "") or service_name,
            status=_map_state_to_status(s.get("State")),
            startType=_map_startmode_to_starttype(s.get("StartMode")),
        )

    @staticmethod
    def stop(server_id: str, service_name: str) -> ServiceItem:
        """
        Para um serviço no servidor de demonstração e retorna o estado atualizado.
        """
        if server_id != "1":
            raise RuntimeError("Server not implemented in demo environment.")

        winrm = WinRMService()
        s = winrm.stop_service(service_name)

        return ServiceItem(
            name=s.get("Name", service_name),
            displayName=s.get("DisplayName", "") or service_name,
            status=_map_state_to_status(s.get("State")),
            startType=_map_startmode_to_starttype(s.get("StartMode")),
        )

    @staticmethod
    def restart(server_id: str, service_name: str) -> ServiceItem:
        """
        Reinicia um serviço no servidor de demonstração e retorna o estado atualizado.
        """
        if server_id != "1":
            raise RuntimeError("Server not implemented in demo environment.")

        winrm = WinRMService()
        s = winrm.restart_service(service_name)

        return ServiceItem(
            name=s.get("Name", service_name),
            displayName=s.get("DisplayName", "") or service_name,
            status=_map_state_to_status(s.get("State")),
            startType=_map_startmode_to_starttype(s.get("StartMode")),
        )