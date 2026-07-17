from pathlib import Path


def write_text(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def test_fintrack_import_creates_accounts_snapshots_events_and_profiles(client, tmp_path):
    household = client.post("/households", json={"name": "Import Home"}).json()

    write_text(tmp_path / "brokerage-condition.toml", "yield = 0.06\n")
    write_text(
        tmp_path / "brokerage-values.csv",
        "date,value\n2024-01-01,1000.00\n2024-02-01,1100.00\n",
    )
    write_text(tmp_path / "brokerage-value-changes.csv", "date,value\n2024-03-01,250.00\n")

    write_text(
        tmp_path / "home-condition.toml",
        'yield = 0.03\nloan = 250000\ninterest_rate = 0.04\nterm_months = 360\nstart_date = "2020-01-01"\n',
    )
    write_text(tmp_path / "home-values.csv", "date,value\n2024-01-01,400000.00\n")

    response = client.post(
        "/imports/fintrack",
        json={"household_id": household["id"], "data_dir": str(tmp_path)},
    )

    assert response.status_code == 201
    result = response.json()
    assert result["accounts_created"] == 3
    assert result["snapshots_created"] == 3
    assert result["events_created"] == 1
    assert result["real_estate_profiles_created"] == 1
    assert result["mortgage_profiles_created"] == 1

    accounts = client.get(f"/accounts?household_id={household['id']}").json()
    account_names = {account["name"] for account in accounts}
    assert account_names == {"Brokerage", "Home", "Home Mortgage"}

    brokerage = next(account for account in accounts if account["name"] == "Brokerage")
    assert brokerage["expected_annual_yield"] == "0.060000"
    assert brokerage["category"] == "taxable_investment"
    events = client.get(f"/accounts/{brokerage['id']}/events").json()
    assert len(events) == 1
    assert events[0]["event_type"] == "contribution"

    home = next(account for account in accounts if account["name"] == "Home")
    assert home["category"] == "real_estate"
    properties = client.get(f"/real-estate/properties?household_id={household['id']}").json()
    assert len(properties) == 1
    assert properties[0]["account_id"] == home["id"]

    mortgages = client.get(f"/mortgages?household_id={household['id']}").json()
    assert len(mortgages) == 1
    assert mortgages[0]["original_principal"] == "250000.00"


def test_fintrack_import_is_idempotent_and_supports_dry_run(client, tmp_path):
    household = client.post("/households", json={"name": "Import Home"}).json()
    write_text(tmp_path / "ally-condition.toml", "yield = 0.04\n")
    write_text(tmp_path / "ally-values.csv", "date,value\n2024-01-01,1000.00\n")

    first = client.post(
        "/imports/fintrack",
        json={"household_id": household["id"], "data_dir": str(tmp_path)},
    )
    assert first.status_code == 201
    assert first.json()["accounts_created"] == 1
    assert first.json()["snapshots_created"] == 1

    second = client.post(
        "/imports/fintrack",
        json={"household_id": household["id"], "data_dir": str(tmp_path)},
    )
    assert second.status_code == 201
    assert second.json()["accounts_created"] == 0
    assert second.json()["accounts_existing"] == 1
    assert second.json()["snapshots_created"] == 0
    assert second.json()["snapshots_updated"] == 0
    assert second.json()["snapshots_existing"] == 1

    write_text(tmp_path / "new-account-condition.toml", "yield = 0.01\n")
    write_text(tmp_path / "new-account-values.csv", "date,value\n2024-01-01,500.00\n")
    dry_run = client.post(
        "/imports/fintrack",
        json={"household_id": household["id"], "data_dir": str(tmp_path), "dry_run": True},
    )
    assert dry_run.status_code == 201
    assert dry_run.json()["dry_run"] is True
    assert dry_run.json()["accounts_created"] == 1
    assert dry_run.json()["accounts_existing"] == 1
    assert dry_run.json()["snapshots_existing"] == 1

    accounts = client.get(f"/accounts?household_id={household['id']}").json()
    assert {account["name"] for account in accounts} == {"Ally"}
