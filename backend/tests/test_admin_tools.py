from collections.abc import Generator

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import Settings, get_settings
from app.db.session import Base, get_db
from app.main import create_app


def test_capabilities_report_admin_tools_enabled(client: TestClient):
    response = client.get("/capabilities")

    assert response.status_code == 200
    assert response.json() == {"admin_tools_enabled": True}


def test_admin_tools_are_disabled_without_explicit_setting():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    testing_session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)
    db = testing_session_local()
    try:
        app = create_app()

        def override_get_db() -> Generator[Session, None, None]:
            yield db

        def override_get_settings() -> Settings:
            return Settings(enable_admin_tools=False)

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_settings] = override_get_settings
        with TestClient(app) as test_client:
            household = test_client.post("/households", json={"name": "Home"}).json()

            export_response = test_client.get(f"/households/{household['id']}/export")
            import_response = test_client.post(
                "/imports/fintrack",
                json={"household_id": household["id"], "data_dir": "/tmp"},
            )
            capabilities_response = test_client.get("/capabilities")

        assert export_response.status_code == 403
        assert import_response.status_code == 403
        assert capabilities_response.json() == {"admin_tools_enabled": False}
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
