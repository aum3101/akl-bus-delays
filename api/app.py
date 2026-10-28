import json
from pathlib import Path
import joblib
import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

BASE = Path(__file__).parent
model = joblib.load(BASE / "model.joblib")
meta = json.loads((BASE / "meta.json").read_text())
info_path = BASE / "routes_info.json"
INFO = json.loads(info_path.read_text()) if info_path.exists() else {}
ROUTES = meta["route_names"]
HOURS_SEEN = set(meta["hours_seen"])

app = FastAPI(title="Auckland Bus Delay Predictor")

def check(route, direction):
    if route not in ROUTES:
        raise HTTPException(status_code=404, detail="Unknown route")
    if direction not in (0, 1):
        raise HTTPException(status_code=422, detail="direction must be 0 or 1")

@app.get("/", include_in_schema=False)
def home():
    return FileResponse(BASE / "index.html")

@app.get("/health")
def health():
    return {"status": "ok", "trained_rows": meta["trained_rows"], "mae_seconds": meta["mae_seconds"]}

@app.get("/routes")
def routes():
    return [{"route": r, "name": INFO.get(r, {}).get("name", ""), "dirs": INFO.get(r, {}).get("dirs", {})} for r in ROUTES]

@app.get("/profile")
def profile(route: str, direction: int = 0, stop_sequence: int | None = None):
    check(route, direction)
    seq = stop_sequence if stop_sequence is not None else int(meta["median_stop_seq"][route])
    X = pd.DataFrame({"route_code": [ROUTES.index(route)] * 24, "direction_id": [direction] * 24,
                      "hour": list(range(24)), "stop_sequence": [seq] * 24})
    preds = model.predict(X)
    return {"route": route, "direction": direction, "stop_sequence": seq,
            "typical_error_seconds": meta["mae_seconds"], "trained_rows": meta["trained_rows"],
            "hours": [{"hour": h, "delay": round(float(p)), "seen": h in HOURS_SEEN} for h, p in zip(range(24), preds)]}

@app.get("/predict")
def predict(route: str, direction: int = 0, hour: int = 8, stop_sequence: int | None = None):
    check(route, direction)
    if not 0 <= hour <= 23:
        raise HTTPException(status_code=422, detail="hour must be 0-23")
    seq = stop_sequence if stop_sequence is not None else int(meta["median_stop_seq"][route])
    X = pd.DataFrame([{"route_code": ROUTES.index(route), "direction_id": direction, "hour": hour, "stop_sequence": seq}])
    delay = float(model.predict(X)[0])
    note = None if hour in HOURS_SEEN else "No training data for this hour, so treat this as a rough guess."
    return {"route": route, "direction": direction, "hour": hour, "stop_sequence": seq,
            "predicted_delay_seconds": round(delay), "typical_error_seconds": meta["mae_seconds"], "note": note}
