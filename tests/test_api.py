import pytest
from fastapi.testclient import TestClient
from api.app import app, ROUTES, HOURS_SEEN

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["trained_rows"] > 0


def test_home_page_is_served():
    r = client.get("/")
    assert r.status_code == 200
    assert "How late is my bus?" in r.text


def test_routes_lists_every_model_route():
    r = client.get("/routes")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == len(ROUTES)
    assert {"route", "name", "dirs"} <= set(data[0])


def test_profile_has_one_prediction_per_hour():
    r = client.get("/profile", params={"route": ROUTES[0], "direction": 0})
    assert r.status_code == 200
    hours = r.json()["hours"]
    assert [h["hour"] for h in hours] == list(range(24))
    assert all(isinstance(h["delay"], int) for h in hours)


def test_predict_returns_plausible_delay():
    r = client.get("/predict", params={"route": ROUTES[0], "direction": 1, "hour": 9})
    assert r.status_code == 200
    assert -1800 < r.json()["predicted_delay_seconds"] < 3600


def test_predict_uses_the_given_stop_sequence():
    r = client.get("/predict", params={"route": ROUTES[0], "hour": 9, "stop_sequence": 7})
    assert r.status_code == 200
    assert r.json()["stop_sequence"] == 7


def test_unknown_route_is_404():
    r = client.get("/predict", params={"route": "no-such-route"})
    assert r.status_code == 404


@pytest.mark.parametrize("params", [{"direction": 2}, {"hour": 24}, {"hour": -1}])
def test_bad_inputs_are_rejected(params):
    r = client.get("/predict", params={"route": ROUTES[0], **params})
    assert r.status_code == 422


def test_hours_without_training_data_carry_a_warning():
    unseen = [h for h in range(24) if h not in HOURS_SEEN]
    if not unseen:
        pytest.skip("every hour has training data")
    r = client.get("/predict", params={"route": ROUTES[0], "hour": unseen[0]})
    assert r.json()["note"]
