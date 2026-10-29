import copy
from collector import parse

SAMPLE = {
    "id": "x",
    "trip_update": {
        "trip": {"trip_id": "t1", "start_time": "19:26:00", "start_date": "20261022",
                 "schedule_relationship": 0, "route_id": "S-C-201", "direction_id": 1},
        "stop_time_update": {"stop_sequence": 22, "departure": {"delay": 49, "time": 1, "uncertainty": 0},
                             "stop_id": "9237-f5d0ce7f", "schedule_relationship": 0},
        "vehicle": {"id": "59428", "label": "AMP 428", "license_plate": ""},
        "timestamp": 1792655389,
        "delay": 72,
    },
    "is_deleted": False,
}


def test_parse_maps_every_field():
    rows = parse([SAMPLE], 1000)
    assert rows == [(1000, 1792655389, "t1", "S-C-201", 1, "20261022", "19:26:00",
                     "59428", 22, "9237-f5d0ce7f", 72, 49, 0)]


def test_parse_skips_entities_without_a_trip_update():
    assert parse([{"id": "v", "vehicle": {"position": {}}}], 1) == []


def test_parse_handles_an_empty_feed():
    assert parse([], 1) == []


def test_parse_handles_stop_time_update_as_a_list():
    e = copy.deepcopy(SAMPLE)
    e["trip_update"]["stop_time_update"] = [e["trip_update"]["stop_time_update"]]
    assert parse([e], 1)[0][11] == 49


def test_parse_prefers_arrival_over_departure():
    e = copy.deepcopy(SAMPLE)
    e["trip_update"]["stop_time_update"]["arrival"] = {"delay": 10}
    assert parse([e], 1)[0][11] == 10


def test_parse_copes_with_missing_stop_time_update():
    e = copy.deepcopy(SAMPLE)
    del e["trip_update"]["stop_time_update"]
    row = parse([e], 1)[0]
    assert row[8] is None and row[11] is None
    assert row[10] == 72
