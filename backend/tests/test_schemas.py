import pytest
from pydantic import ValidationError

from app.models.schemas import Servidor, ServiceItem, ActionResponse


def test_servidor_schema_creation():
    servidor = Servidor(
        id="1",
        nome="SRV-DEMO-01",
        descricao="Servidor Windows de demonstração",
        status="online",
    )

    assert servidor.id == "1"
    assert servidor.nome == "SRV-DEMO-01"
    assert servidor.descricao == "Servidor Windows de demonstração"
    assert servidor.status == "online"


def test_servidor_schema_invalid_status():
    with pytest.raises(ValidationError):
        Servidor(
            id="1",
            nome="SRV-DEMO-01",
            descricao="Servidor Windows de demonstração",
            status="ativo",
        )


def test_service_item_schema_creation_with_aliases():
    service = ServiceItem(
        name="Spooler",
        displayName="Print Spooler",
        status="running",
        startType="automatic",
    )

    assert service.name == "Spooler"
    assert service.display_name == "Print Spooler"
    assert service.status == "running"
    assert service.start_type == "automatic"


def test_service_item_schema_invalid_status():
    with pytest.raises(ValidationError):
        ServiceItem(
            name="DemoService",
            displayName="Demo Service",
            status="started",
            startType="manual",
        )


def test_action_response_schema_creation():
    response = ActionResponse(
        ok=True,
        message="Service action completed successfully.",
    )

    assert response.ok is True
    assert response.message == "Service action completed successfully."