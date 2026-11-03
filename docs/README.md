# How late is my bus?

![tests](https://github.com/aum3101/akl-bus-delays/actions/workflows/tests.yml/badge.svg)

A small end-to-end data project. It collects live Auckland Transport bus data around the clock, learns the typical delay for each route, and serves the result as a web app. Pick a route and a direction, then drag through the day to see how late that bus usually runs.

**Live demo: http://16.178.172.104/** (plain HTTP, running on a small AWS server, so it may be offline at times)

![The delay predictor](docs/screenshot.png)


## Why I built it

Auckland buses often run early or late in ways a timetable doesn't show. I wanted to find out how much of that is predictable from the route and the time of day, and to build the whole pipeline myself: collection, cleaning, modelling, an API, a front end, tests and deployment.

## How it works

```
Auckland Transport           AWS EC2 (Sydney)                       Laptop
Realtime API  -- 60 s -->    collector.py (systemd) -> SQLite  -->  clean, join to GTFS,
                                                                    train and evaluate
                                                                           |
                                                                           v
                             Docker container: FastAPI + web page  <-- model.joblib
```

1. **Collect.** `collector.py` polls the realtime feed once a minute and stores each trip's delay in SQLite. It runs as a `systemd` service on a small EC2 instance, so it restarts after crashes and reboots.
2. **Clean.** Live trips are joined to the static GTFS timetable by trip ID (about 98-99% of trips match) and only buses are kept. Readings older than two minutes, cancelled trips, and delays beyond 15 minutes early or 30 minutes late are dropped.
3. **Model.** A gradient boosting regressor (scikit-learn) predicts a trip's delay in seconds from the route, direction, hour of day (Auckland time) and position along the trip.
4. **Serve.** A FastAPI service exposes the predictions and a single-page UI draws the whole day as a chart. The service runs in a Docker container on the same server as the collector.

## Results

The data covers about a week of live readings (roughly 2.5 million after cleaning), including one weekend. I evaluated the model with a **forward-in-time test**: for each test day it trains only on earlier days, then scores that day. Splitting at random would put near-identical readings of the same trip on both sides and make the score look better than it is.

Average miss in seconds, over four test days (31 October to 3 November):

| Model | Mean miss |
|---|---|
| Global median delay | 164.3 s |
| Median delay per route | 156.6 s |
| Median delay per route and hour | 157.6 s |
| **Gradient boosting** | **144.2 s** |

| Test day | Route median | Gradient boosting |
|---|---|---|
| Sat 31 Oct | 153.1 s | 145.5 s |
| Sun 1 Nov | 151.1 s | 145.0 s |
| Mon 2 Nov | 163.5 s | 148.9 s |
| Tue 3 Nov | 158.7 s | 137.4 s |

What this shows:

- The model beat every baseline on every test day, by about 8% against the per-route median and 12% against the global median. It held up on Saturday even though it had never seen a weekend.
- An average miss of about 2.4 minutes is still large, because the delay of any single bus is noisy. The model captures the typical pattern for a route. It does not predict a particular bus.
- Most of the gain comes from which route it is and how far along the trip the bus is. Hour of day adds less than I expected: the route-and-hour baseline barely beats the route median on weekdays.
- I also tried a weekend flag. It made no difference on average (144.4 s against 144.2 s) and was worse on Sunday, so I left it out. With only two weekend days in the data it can't be judged properly.

## Limitations

- **Short history.** About a week of data, with one weekend. School holidays, public holidays, special events and weather are not represented.
- **Thin overnight coverage.** Few buses run between about 1am and 4am, so there is little to learn from. The chart draws hours with too little data as dashed lines and the page labels them as estimates.
- **Typical delay, not a live arrival time.** The model doesn't see where a bus is right now, so it can't tell you whether today's bus is running late.
- **Static timetable snapshot.** The GTFS timetable was downloaded once, and the match rate for the most recent data (98.1%) is slightly lower than for the first days (99.0%), which suggests the timetable changed a little. A production version would refresh it on a schedule.
- **Demo-grade hosting.** The live app runs on a single small server over plain HTTP, with no autoscaling or monitoring.

## Run it locally

You need Python 3.13 (the project is pinned to the versions in `requirements.txt`).

```bash
pip install -r requirements.txt
python -m uvicorn api.app:app --port 8001
```

Open http://127.0.0.1:8001/. The trained model and route metadata are in `api/`, so the app runs without any data or API key.

With Docker:

```bash
docker build -t akl-bus-delays .
docker run -p 8000:8000 akl-bus-delays
```

To collect your own data, register at the [Auckland Transport developer portal](https://dev-portal.at.govt.nz), subscribe to the Public Transport Dev product, and put your key in a `.env` file:

```
AT_API_KEY=your_key_here
```

Then run `python collector.py`. It polls every 60 seconds and writes to `bus_delays.db`.

## API

| Endpoint | Returns |
|---|---|
| `GET /routes` | Every bus route with its name and destinations |
| `GET /profile?route=83&direction=0` | Predicted delay for each hour of the day |
| `GET /predict?route=83&direction=0&hour=9` | Predicted delay for one hour |
| `GET /health` | Service status and model metadata |

## Project structure

```
collector.py          Polls the realtime API and stores trip delays in SQLite
API.ipynb             Cleaning, GTFS join, training and forward-in-time evaluation
api/app.py            FastAPI service
api/index.html        The web page (route picker, day chart)
api/model.joblib      Trained model
api/meta.json         Route list and training metadata
api/routes_info.json  Route names and destinations from the GTFS feed
tests/                17 pytest tests for the API and the collector's parsing
Dockerfile            Container image for the API
.github/workflows/    CI: runs the tests and builds the image on every push
```

## Deployment

- **Server:** a t3.micro EC2 instance in Sydney (Ubuntu 24.04) with an Elastic IP and 1 GB of swap.
- **Collector:** a `systemd` service that restarts on failure.
- **API:** the Docker image, run with `--restart unless-stopped`.
- **CI:** GitHub Actions installs the pinned dependencies, runs the tests, then builds the image and smoke-tests `/health`.

## What I would do next

- Collect for longer, then repeat the forward-in-time evaluation across more weekdays, weekends and a school holiday.
- Use the delay at earlier stops of the same trip, to predict how late a bus already on the road will be.
- Refresh the static timetable automatically and retrain on a schedule.
- Move the database to PostgreSQL and the infrastructure to Terraform.
- Add HTTPS and basic monitoring.

## Data

Realtime and timetable data come from Auckland Transport's public APIs. This project isn't affiliated with or endorsed by Auckland Transport.
