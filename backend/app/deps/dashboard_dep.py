# app/deps/dashboard_dep.py
"""
Dependency para acessar o serviço do Dashboard armazenado no app.state.

As rotas do dashboard e qualquer rota que queira publicar eventos
(START/STOP/RESTART) podem injetar este serviço via Depends(...).
"""

from fastapi import Request
from app.services.dashboard_service import DashboardService


def get_dashboard_service(request: Request) -> DashboardService:
    """
    Retorna o DashboardService registrado no `app.state.dashboard_service`.

    Uso:
        dash: DashboardService = Depends(get_dashboard_service)
    """
    return request.app.state.dashboard_service
