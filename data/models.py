"""
data/models.py — SQLAlchemy ORM models.
Mirrors the schema defined in the project documentation.
"""

from sqlalchemy import (
    BigInteger, Boolean, Column, DateTime, Float, ForeignKey,
    Integer, SmallInteger, String, UniqueConstraint, func,
    JSON,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


# ─────────────────────────────────────────────────────────────────────────────
# Users
# ─────────────────────────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    user_id     = Column(Integer, primary_key=True, autoincrement=True)
    username    = Column(String(100), unique=True, nullable=False, index=True)
    email       = Column(String(255), unique=True, nullable=False, index=True)
    hashed_pw   = Column(String(255), nullable=False)
    is_active   = Column(Boolean, default=True, nullable=False)
    created_at  = Column(DateTime(timezone=True), server_default=func.now())
    last_active = Column(DateTime(timezone=True), nullable=True)
    # Onboarding preferences: {"genre_weights": {...}, "language_pref": "en"}
    preferences = Column(JSON, default=dict)

    ratings  = relationship("Rating", back_populates="user", lazy="dynamic")
    events   = relationship("Event",  back_populates="user", lazy="dynamic")

    def __repr__(self):
        return f"<User id={self.user_id} username={self.username!r}>"


# ─────────────────────────────────────────────────────────────────────────────
# Movies
# ─────────────────────────────────────────────────────────────────────────────

class Movie(Base):
    __tablename__ = "movies"

    movie_id     = Column(Integer, primary_key=True, autoincrement=True)
    title        = Column(String(255), nullable=False, index=True)
    release_year = Column(SmallInteger, nullable=True)
    # Stored as JSON list: ["Action", "Drama"]
    genres       = Column(JSON, default=list)
    language     = Column(String(10), default="en")
    avg_rating   = Column(Float, default=0.0)
    rating_count = Column(Integer, default=0)
    # Rich metadata: {director, cast, tmdb_id, poster_url, overview, ...}
    metadata_    = Column("metadata", JSON, default=dict)

    ratings = relationship("Rating", back_populates="movie", lazy="dynamic")
    events  = relationship("Event",  back_populates="movie", lazy="dynamic")

    def __repr__(self):
        return f"<Movie id={self.movie_id} title={self.title!r}>"


# ─────────────────────────────────────────────────────────────────────────────
# Ratings  (explicit feedback)
# ─────────────────────────────────────────────────────────────────────────────

class Rating(Base):
    __tablename__ = "ratings"
    __table_args__ = (UniqueConstraint("user_id", "movie_id", name="uq_user_movie"),)

    rating_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id   = Column(BigInteger, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True)
    movie_id  = Column(BigInteger, ForeignKey("movies.movie_id", ondelete="CASCADE"), nullable=False, index=True)
    rating    = Column(Float, nullable=False)   # 0.5 – 5.0
    rated_at  = Column(DateTime(timezone=True), server_default=func.now())

    user  = relationship("User",  back_populates="ratings")
    movie = relationship("Movie", back_populates="ratings")

    def __repr__(self):
        return f"<Rating user={self.user_id} movie={self.movie_id} rating={self.rating}>"


# ─────────────────────────────────────────────────────────────────────────────
# Events  (implicit feedback stream)
# ─────────────────────────────────────────────────────────────────────────────

class Event(Base):
    __tablename__ = "events"

    event_id    = Column(Integer, primary_key=True, autoincrement=True)
    user_id     = Column(BigInteger, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True)
    movie_id    = Column(BigInteger, ForeignKey("movies.movie_id", ondelete="CASCADE"), nullable=False, index=True)
    # click | watch | skip | search | bookmark | share
    event_type  = Column(String(30), nullable=False, index=True)
    watch_pct   = Column(Float, nullable=True)    # 0.0 – 100.0
    occurred_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    user  = relationship("User",  back_populates="events")
    movie = relationship("Movie", back_populates="events")

    def __repr__(self):
        return f"<Event user={self.user_id} movie={self.movie_id} type={self.event_type!r}>"


# ─────────────────────────────────────────────────────────────────────────────
# Reviews  (user text reviews)
# ─────────────────────────────────────────────────────────────────────────────

class Review(Base):
    __tablename__ = "reviews"
    __table_args__ = (UniqueConstraint("user_id", "movie_id", name="uq_review_user_movie"),)

    review_id   = Column(Integer, primary_key=True, autoincrement=True)
    user_id     = Column(BigInteger, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True)
    movie_id    = Column(BigInteger, ForeignKey("movies.movie_id", ondelete="CASCADE"), nullable=False, index=True)
    review_text = Column(String(2000), nullable=False)
    created_at  = Column(DateTime(timezone=True), server_default=func.now())
    updated_at  = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<Review user={self.user_id} movie={self.movie_id}>"
