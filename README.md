# Nexus.AI — Movie Recommender

A personalized movie recommendation system powered by a hybrid ML engine (collaborative filtering + content-based + neural re-ranking).

---

## Quick Start

**1. Clone / download the project, then open a terminal in the project folder.**

**2. Activate the virtual environment**
```bash
venv\Scripts\activate
```

**3. Copy the environment file**
```bash
copy .env.example .env
```

**4. Start the server**
```bash
uvicorn api.main:app --reload
```

**5. Open your browser**

| Page | URL |
|---|---|
| App UI | http://localhost:8000 |
| API Docs | http://localhost:8000/docs |

Register an account on the login screen, sign in, and start getting recommendations.

---

## How It Works

The recommendation engine runs a 3-stage pipeline:

1. **ALS (Collaborative Filtering)** — finds movies liked by users with similar taste (up to 400 candidates)
2. **Content Model** — finds movies similar to your watch history (up to 200 candidates)
3. **LightGBM Ranker** — scores and re-ranks the merged candidate pool, returns top N

Strategies available: `hybrid` (default), `cf`, `content`, `popular`

---

## Project Structure

```
movie-recommender/
├── api/
│   ├── main.py              # FastAPI app factory
│   ├── model_registry.py    # Loads ML engine on startup
│   └── routers/
│       ├── auth.py          # Register / login / JWT
│       ├── recommendations.py
│       ├── ratings.py
│       └── reviews.py
├── ml/
│   └── models/
│       ├── hybrid_engine.py # Orchestrates ALS + Content + Ranker
│       ├── als_model.py
│       ├── content_model.py
│       └── ranker.py
├── static/
│   └── index.html           # Frontend UI (Nexus.AI)
├── config.py                # All settings (loaded from .env)
├── seed.py                  # Populate DB with sample movies
├── requirements.txt
├── .env.example
└── docker-compose.yml
```

---

## Full Stack (Docker)

To run with PostgreSQL, Redis, Kafka, MLflow, and Grafana:

```bash
docker compose up --build
```

| Service | URL |
|---|---|
| App UI | http://localhost:8000 |
| MLflow | http://localhost:5000 |
| Grafana | http://localhost:3000 (admin/admin) |

---

## Configuration

All settings live in `.env`. Key options:

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./recommender.db` | Use SQLite locally, PostgreSQL in production |
| `SECRET_KEY` | `dev_secret_key_...` | Change this in production |
| `TMDB_API_KEY` | *(empty)* | Optional — for fetching movie posters/metadata |
| `DEBUG` | `false` | Enables verbose logging and open CORS |

Generate a secure secret key:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

---

## Running Tests

```bash
pytest
```

---

## Tech Stack

- **API** — FastAPI + Uvicorn
- **Database** — SQLite (dev) / PostgreSQL (prod) via SQLAlchemy
- **ML** — scikit-learn, LightGBM, NumPy, pandas
- **Auth** — JWT (python-jose + bcrypt)
- **Experiment Tracking** — MLflow
- **Caching** — Redis
- **Event Streaming** — Kafka
- **Monitoring** — Grafana
