"""
ml/features/user_features.py
Extracts and builds user feature vectors from the database using SQLAlchemy ORM.
"""
import numpy as np
import pandas as pd
from sqlalchemy.orm import Session
from sqlalchemy import func

from data.models import User, Movie, Rating, Event

GENRES = [
    "Action", "Adventure", "Animation", "Comedy", "Crime",
    "Documentary", "Drama", "Fantasy", "Horror", "Mystery",
    "Romance", "Sci-Fi", "Thriller", "Western", "Family",
]
GENRE_INDEX = {g: i for i, g in enumerate(GENRES)}


def get_user_genre_vector(user_id: int, db: Session) -> np.ndarray:
    """
    Returns a 15-dim genre preference vector for a user,
    computed as the mean rating they gave to each genre.
    """
    rows = db.query(Movie.genres, Rating.rating)\
             .join(Rating, Movie.movie_id == Rating.movie_id)\
             .filter(Rating.user_id == user_id)\
             .all()

    genre_sums   = np.zeros(len(GENRES))
    genre_counts = np.zeros(len(GENRES))

    for row in rows:
        genres = row.genres if isinstance(row.genres, list) else []
        rating = float(row.rating)
        for g in genres:
            if g in GENRE_INDEX:
                idx = GENRE_INDEX[g]
                genre_sums[idx]   += rating
                genre_counts[idx] += 1

    # Avoid division by zero; default 0.0 where no data
    mask = genre_counts > 0
    vec  = np.zeros(len(GENRES))
    vec[mask] = genre_sums[mask] / genre_counts[mask]
    return vec.astype(np.float32)


def get_user_watch_history(user_id: int, db: Session, limit: int = 20) -> list[int]:
    """Returns last `limit` movie IDs the user interacted with."""
    events = db.query(Event.movie_id)\
               .filter(Event.user_id == user_id)\
               .order_by(Event.occurred_at.desc())\
               .limit(limit)\
               .all()
    return [e.movie_id for e in events]


def build_user_feature_matrix(db: Session) -> pd.DataFrame:
    """
    Builds a DataFrame of user features for all users.
    Columns: user_id, avg_rating, n_ratings, genre_0..14
    """
    rows = db.query(
        User.user_id,
        func.coalesce(func.avg(Rating.rating), 0.0).label("avg_rating"),
        func.count(Rating.rating_id).label("n_ratings")
    ).outerjoin(Rating, User.user_id == Rating.user_id)\
     .group_by(User.user_id)\
     .all()

    records = []
    for row in rows:
        uid = row.user_id
        avg_r = row.avg_rating
        n_r = row.n_ratings
        genre_vec = get_user_genre_vector(uid, db)
        records.append({
            "user_id":      uid,
            "avg_rating":   float(avg_r),
            "n_ratings":    int(n_r),
            **{f"genre_{i}": float(genre_vec[i]) for i in range(len(GENRES))},
        })

    return pd.DataFrame(records).set_index("user_id")
