"""
api/schemas/schemas.py
All Pydantic request and response models for the API.
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, field_validator


# ─── Auth ─────────────────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    username: str  = Field(..., min_length=3, max_length=100)
    email:    str  = Field(..., max_length=255)
    password: str  = Field(..., min_length=8)

class LoginRequest(BaseModel):
    username: str
    password: str

class TokenResponse(BaseModel):
    access_token:  str
    refresh_token: str
    token_type:    str = "bearer"
    expires_in:    int           # seconds

class RefreshRequest(BaseModel):
    refresh_token: str


# ─── Users ────────────────────────────────────────────────────────────────────

class UserOut(BaseModel):
    user_id:     int
    username:    str
    email:       str
    created_at:  datetime
    last_active: Optional[datetime]
    preferences: dict

    model_config = {"from_attributes": True}


# ─── Movies ───────────────────────────────────────────────────────────────────

class MovieOut(BaseModel):
    movie_id:     int
    title:        str
    release_year: Optional[int]
    genres:       list[str]
    language:     Optional[str]
    avg_rating:   float
    rating_count: int

    model_config = {"from_attributes": True}


# ─── Ratings ──────────────────────────────────────────────────────────────────

class RatingCreate(BaseModel):
    movie_id: int
    rating:   float = Field(..., ge=0.5, le=5.0)

    @field_validator("rating")
    @classmethod
    def round_to_half(cls, v: float) -> float:
        return round(v * 2) / 2   # snap to nearest 0.5

class RatingOut(BaseModel):
    rating_id: int
    movie_id:  int
    rating:    float
    rated_at:  datetime

    model_config = {"from_attributes": True}


# ─── Events ───────────────────────────────────────────────────────────────────

VALID_EVENT_TYPES = {"click", "watch", "skip", "bookmark", "share", "search"}

class EventCreate(BaseModel):
    movie_id:   int
    event_type: str
    watch_pct:  Optional[float] = Field(None, ge=0.0, le=100.0)

    @field_validator("event_type")
    @classmethod
    def validate_event_type(cls, v: str) -> str:
        if v not in VALID_EVENT_TYPES:
            raise ValueError(f"event_type must be one of {VALID_EVENT_TYPES}")
        return v

class EventOut(BaseModel):
    event_id:    int
    movie_id:    int
    event_type:  str
    watch_pct:   Optional[float]
    occurred_at: datetime

    model_config = {"from_attributes": True}


# ─── Recommendations ──────────────────────────────────────────────────────────

VALID_STRATEGIES = {"hybrid", "cf", "content", "popular"}

class RecommendationItem(BaseModel):
    movie_id:    int
    title:       str
    genres:      list[str]
    release_year: Optional[int]
    avg_rating:  float
    score:       float
    strategy:    str
    explanation: str
    poster_url:  Optional[str] = None

class RecommendationResponse(BaseModel):
    user_id:          int
    strategy:         str
    generated_at:     datetime
    recommendations:  list[RecommendationItem]

class SimilarMoviesResponse(BaseModel):
    movie_id:      int
    title:         str
    similar_movies: list[dict]


# ─── Reviews ──────────────────────────────────────────────────────────────────

class ReviewCreate(BaseModel):
    movie_id:    int
    review_text: str = Field(..., min_length=1, max_length=2000)

class ReviewOut(BaseModel):
    review_id:   int
    movie_id:    int
    review_text: str
    created_at:  datetime
    updated_at:  datetime

    model_config = {"from_attributes": True}


# ─── Health ───────────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status:     str
    version:    str
    db:         str
    model:      str
    timestamp:  datetime
