"""
api/routers/ratings.py
POST /v1/ratings          — submit or update a movie rating
GET  /v1/ratings          — list the current user's ratings
DELETE /v1/ratings/{id}   — delete a rating

api/routers/events.py (included here for brevity)
POST /v1/events           — log a user interaction event
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from api.middleware.auth import get_current_user
from api.schemas.schemas import EventCreate, EventOut, RatingCreate, RatingOut
from data.database import get_db
from data.models import Event, Movie, Rating, User

# ── Ratings ───────────────────────────────────────────────────────────────────

ratings_router = APIRouter(prefix="/v1/ratings", tags=["ratings"])


@ratings_router.post("", response_model=RatingOut, status_code=status.HTTP_201_CREATED)
def submit_rating(
    payload:      RatingCreate,
    current_user: User    = Depends(get_current_user),
    db:           Session = Depends(get_db),
):
    """Submit or update a movie rating (0.5 – 5.0)."""
    # Verify movie exists
    if not db.get(Movie, payload.movie_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Movie not found")

    # Upsert: update if exists
    existing = (
        db.query(Rating)
        .filter(Rating.user_id == current_user.user_id, Rating.movie_id == payload.movie_id)
        .first()
    )
    if existing:
        existing.rating   = payload.rating
        existing.rated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(existing)
        return existing

    rating = Rating(
        user_id=current_user.user_id,
        movie_id=payload.movie_id,
        rating=payload.rating,
    )
    db.add(rating)
    db.commit()
    db.refresh(rating)
    return rating


@ratings_router.get("", response_model=list[RatingOut])
def list_ratings(
    skip:         int  = Query(default=0, ge=0),
    limit:        int  = Query(default=50, le=200),
    current_user: User    = Depends(get_current_user),
    db:           Session = Depends(get_db),
):
    """List all ratings submitted by the authenticated user."""
    return (
        db.query(Rating)
        .filter(Rating.user_id == current_user.user_id)
        .order_by(Rating.rated_at.desc())
        .offset(skip).limit(limit)
        .all()
    )


@ratings_router.delete("/{rating_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_rating(
    rating_id:    int,
    current_user: User    = Depends(get_current_user),
    db:           Session = Depends(get_db),
):
    """Delete one of the authenticated user's ratings."""
    rating = db.query(Rating).filter(
        Rating.rating_id == rating_id,
        Rating.user_id   == current_user.user_id,
    ).first()
    if not rating:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rating not found")
    db.delete(rating)
    db.commit()


# ── Events ────────────────────────────────────────────────────────────────────

events_router = APIRouter(prefix="/v1/events", tags=["events"])


@events_router.post("", response_model=EventOut, status_code=status.HTTP_201_CREATED)
def log_event(
    payload:      EventCreate,
    current_user: User    = Depends(get_current_user),
    db:           Session = Depends(get_db),
):
    """
    Log a user interaction event (click, watch, skip, bookmark, share, search).
    These events feed the implicit feedback training pipeline.
    """
    if not db.get(Movie, payload.movie_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Movie not found")

    event = Event(
        user_id=current_user.user_id,
        movie_id=payload.movie_id,
        event_type=payload.event_type,
        watch_pct=payload.watch_pct,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


@events_router.get("", response_model=list[EventOut])
def list_events(
    limit:        int  = Query(default=50, le=200),
    current_user: User    = Depends(get_current_user),
    db:           Session = Depends(get_db),
):
    """Return the authenticated user's most recent interaction events."""
    return (
        db.query(Event)
        .filter(Event.user_id == current_user.user_id)
        .order_by(Event.occurred_at.desc())
        .limit(limit)
        .all()
    )
