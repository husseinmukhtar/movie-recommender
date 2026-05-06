"""
api/routers/recommendations.py
GET  /v1/recommendations              — personalised recs for authenticated user
GET  /v1/recommendations/similar/{id} — movies similar to a given movie
POST /v1/recommendations/reload       — hot-reload ML models (admin only)
"""
import logging
import json
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from api.middleware.auth import get_current_user
from api.model_registry import get_engine, reload_engine
from api.schemas.schemas import (
    RecommendationItem, RecommendationResponse, SimilarMoviesResponse, VALID_STRATEGIES,
)
from config import get_settings
from data.database import get_db
from data.models import Movie, User
from ml.models.hybrid_engine import HybridEngine

logger   = logging.getLogger(__name__)
router   = APIRouter(prefix="/v1/recommendations", tags=["recommendations"])
settings = get_settings()


def _normalize_genres(raw_genres) -> list[str]:
    """Normalize DB/raw SQL genres field to a list of strings."""
    if isinstance(raw_genres, list):
        return [str(g) for g in raw_genres]
    if isinstance(raw_genres, str):
        try:
            parsed = json.loads(raw_genres)
        except json.JSONDecodeError:
            return []
        if isinstance(parsed, list):
            return [str(g) for g in parsed]
    return []


def _get_movie_meta(movie_ids: list[int], db: Session) -> dict[int, dict]:
    """Batch-fetch movie metadata for enriching recommendation results."""
    if not movie_ids:
        return {}

    # SQLite compat: SQLAlchemy's expanding binds keep this parameterized.
    placeholders = ", ".join(f":id_{idx}" for idx, _ in enumerate(movie_ids))
    bind_params = {f"id_{idx}": movie_id for idx, movie_id in enumerate(movie_ids)}
    rows = db.execute(
        text(
            "SELECT movie_id, title, release_year, genres, avg_rating, metadata "
            f"FROM movies WHERE movie_id IN ({placeholders})"
        ),
        bind_params,
    ).fetchall()
    result = {}
    for r in rows:
        raw_meta = r[5]
        if isinstance(raw_meta, str):
            try:
                raw_meta = json.loads(raw_meta)
            except (json.JSONDecodeError, TypeError):
                raw_meta = {}
        meta = raw_meta if isinstance(raw_meta, dict) else {}
        poster_url = meta.get("poster_url") or meta.get("tmdb_poster_path") or None
        result[r[0]] = {
            "title": r[1],
            "release_year": r[2],
            "genres": _normalize_genres(r[3]),
            "avg_rating": r[4] or 0.0,
            "poster_url": poster_url,
        }
    return result


def _get_user_seen(user_id: int, db: Session) -> set[int]:
    """Movie IDs the user has already rated or watched."""
    rows = db.execute(
        text(
            "SELECT DISTINCT movie_id FROM ratings WHERE user_id = :user_id "
            "UNION "
            "SELECT DISTINCT movie_id FROM events WHERE user_id = :user_id AND event_type = 'watch'"
        ),
        {"user_id": user_id},
    ).fetchall()
    return {r[0] for r in rows}


def _get_watch_history(user_id: int, db: Session, limit: int = 30) -> list[int]:
    rows = db.execute(
        text(
            "SELECT movie_id FROM events WHERE user_id = :user_id "
            "ORDER BY occurred_at DESC LIMIT :limit"
        ),
        {"user_id": user_id, "limit": limit},
    ).fetchall()
    return [r[0] for r in rows]


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("", response_model=RecommendationResponse)
def get_recommendations(
    n:            int     = Query(default=10, ge=1, le=settings.max_recommendations),
    strategy:     str     = Query(default="hybrid"),
    exclude_seen: bool    = Query(default=True),
    genre:        Optional[str] = Query(default=None, description="Filter by genre name"),
    current_user: User    = Depends(get_current_user),
    db:           Session = Depends(get_db),
):
    """
    Return personalised movie recommendations for the authenticated user.

    - **n**: number of recommendations (1-50)
    - **strategy**: hybrid | cf | content | popular
    - **exclude_seen**: filter out already-watched/rated movies
    - **genre**: optional genre filter (e.g. "Action", "Comedy")
    """
    if strategy not in VALID_STRATEGIES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"strategy must be one of {VALID_STRATEGIES}",
        )

    try:
        engine: HybridEngine = get_engine()
    except RuntimeError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Recommendation engine not available. Models may still be training.",
        )
    als_model = getattr(engine, "als", None)
    als_user_map = getattr(als_model, "user_id_to_idx", {}) if als_model is not None else {}
    in_model = current_user.user_id in als_user_map
    logger.info(
        "Recommendations request user_id=%s strategy=%s n=%s in_als_model=%s",
        current_user.user_id,
        strategy,
        n,
        in_model,
    )

    seen_ids      = _get_user_seen(current_user.user_id, db) if exclude_seen else set()
    watch_history = _get_watch_history(current_user.user_id, db)

    try:
        raw_recs = engine.recommend(
            user_id=current_user.user_id,
            watch_history=watch_history,
            n=n,
            strategy=strategy,
            seen_ids=seen_ids,
            genre_filter=genre,
        )
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "USER_NOT_IN_MODEL", "message": str(exc)},
        )

    if not raw_recs:
        # Ultimate fallback: return popular movies
        raw_recs = engine.recommend(
            user_id=current_user.user_id,
            watch_history=[],
            n=n,
            strategy="popular",
            seen_ids=seen_ids,
            genre_filter=genre,
        )

    movie_ids = [r["movie_id"] for r in raw_recs]
    meta      = _get_movie_meta(movie_ids, db)

    items = []
    for rec in raw_recs:
        mid  = rec["movie_id"]
        info = meta.get(mid, {})
        items.append(RecommendationItem(
            movie_id=mid,
            title=info.get("title", f"Movie {mid}"),
            genres=info.get("genres", []),
            release_year=info.get("release_year"),
            avg_rating=info.get("avg_rating", 0.0),
            score=rec["score"],
            strategy=rec["strategy"],
            explanation=rec["explanation"],
            poster_url=info.get("poster_url"),
        ))

    return RecommendationResponse(
        user_id=current_user.user_id,
        strategy=strategy,
        generated_at=datetime.now(timezone.utc),
        recommendations=items,
    )


@router.get("/similar/{movie_id}", response_model=SimilarMoviesResponse)
def similar_movies(
    movie_id: int,
    n:        int     = Query(default=10, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db:       Session  = Depends(get_db),
):
    """Return movies similar to the given movie (content + CF hybrid)."""
    movie = db.get(Movie, movie_id)
    if not movie:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Movie not found")

    try:
        engine: HybridEngine = get_engine()
    except RuntimeError:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            detail="Engine not available")

    # Content-based similarity
    try:
        content_similar = engine.content.similar_to_movie(movie_id, n=n)
    except KeyError:
        content_similar = []

    # ALS item similarity
    try:
        als_similar = engine.als.similar_items(movie_id, n=n)
    except KeyError:
        als_similar = []

    # Merge, deduplicate, sort by score
    score_map: dict[int, float] = {}
    for mid, score in content_similar:
        score_map[mid] = max(score_map.get(mid, 0.0), score * 0.5)
    for mid, score in als_similar:
        score_map[mid] = max(score_map.get(mid, 0.0), score * 0.5)

    sorted_similar = sorted(score_map.items(), key=lambda x: x[1], reverse=True)[:n]
    similar_ids    = [mid for mid, _ in sorted_similar]
    meta           = _get_movie_meta([movie_id] + similar_ids, db)

    similar_list = [
        {"movie_id": mid, "title": meta.get(mid, {}).get("title", f"Movie {mid}"),
         "similarity": round(score, 4), "genres": meta.get(mid, {}).get("genres", [])}
        for mid, score in sorted_similar
    ]

    return SimilarMoviesResponse(
        movie_id=movie_id,
        title=movie.title,
        similar_movies=similar_list,
    )


@router.post("/reload", status_code=status.HTTP_200_OK)
def reload_models(current_user: User = Depends(get_current_user)):
    """Hot-reload ML models from disk. Useful after a new training run."""
    try:
        reload_engine()
        return {"status": "ok", "message": "Models reloaded successfully"}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
