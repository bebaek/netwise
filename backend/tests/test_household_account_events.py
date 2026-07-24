def create_account(client, household_id: str, name: str) -> dict:
    return client.post(
        "/accounts",
        json={
            "household_id": household_id,
            "name": name,
            "account_kind": "asset",
            "category": "cash",
            "liquidity_class": "liquid",
            "currency": "USD",
        },
    ).json()


def test_list_household_account_events_batches_accounts_and_orders_newest_first(client):
    household = client.post("/households", json={"name": "Events Home"}).json()
    checking = create_account(client, household["id"], "Checking")
    brokerage = create_account(client, household["id"], "Brokerage")

    older = client.post(
        f"/accounts/{checking['id']}/events",
        json={
            "event_date": "2026-01-01",
            "amount": "100.00",
            "currency": "USD",
            "event_type": "contribution",
        },
    ).json()
    newer = client.post(
        f"/accounts/{brokerage['id']}/events",
        json={
            "event_date": "2026-02-01",
            "amount": "200.00",
            "currency": "USD",
            "event_type": "contribution",
        },
    ).json()

    response = client.get(f"/households/{household['id']}/events")

    assert response.status_code == 200
    assert [event["id"] for event in response.json()] == [newer["id"], older["id"]]
    assert {event["account_id"] for event in response.json()} == {
        checking["id"],
        brokerage["id"],
    }
