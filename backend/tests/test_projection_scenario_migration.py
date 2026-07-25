from uuid import uuid4

from alembic import command
from alembic.config import Config
from sqlalchemy import MetaData, Table, create_engine, func, select

from app.core.config import get_settings
from app.db.session import Base


def test_projection_scenario_migration_backfills_existing_households(tmp_path, monkeypatch):
    database_path = tmp_path / "scenario-migration.db"
    database_url = f"sqlite:///{database_path}"
    monkeypatch.setenv("NETWISE_DATABASE_URL", database_url)
    get_settings.cache_clear()
    config = Config("alembic.ini")

    try:
        engine = create_engine(database_url)
        Base.metadata.tables["households"].create(engine)
        command.stamp(config, "0024_user_authentication")
        metadata = MetaData()
        households = Table("households", metadata, autoload_with=engine)
        household_id = uuid4()
        with engine.begin() as connection:
            connection.execute(
                households.insert().values(
                    id=household_id.hex,
                    name="Existing Household",
                    created_at=func.current_timestamp(),
                    updated_at=func.current_timestamp(),
                )
            )

        command.upgrade(config, "0025_projection_scenarios")
        migrated_metadata = MetaData()
        scenarios = Table("projection_scenarios", migrated_metadata, autoload_with=engine)
        with engine.connect() as connection:
            rows = connection.execute(
                select(
                    scenarios.c.household_id,
                    scenarios.c.name,
                    scenarios.c.description,
                    scenarios.c.is_baseline,
                )
            ).all()

        assert rows == [
            (
                household_id.hex,
                "Baseline",
                "Default household projection assumptions",
                True,
            )
        ]
    finally:
        get_settings.cache_clear()
