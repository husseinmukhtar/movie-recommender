"""
ml/features/item_features.py
Extracts and builds movie (item) feature vectors.
"""
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import MinMaxScaler
from sqlalchemy.orm import Session

from ml.features.user_features import GENRES, GENRE_INDEX


def get_genre_vector(genres: list[str]) -> np.ndarray:
    """One-hot encode genres into a 15-dim binary vector."""
    vec = np.zeros(len(GENRES), dtype=np.float32)
    for g in genres:
        if g in GENRE_INDEX:
            vec[GENRE_INDEX[g]] = 1.0
    return vec


def build_item_feature_matrix(db: Session) -> pd.DataFrame:
    """
    Builds a DataFrame of item features for all movies.
    Columns: movie_id, avg_rating, release_year_norm, rating_count_log,
             genre_0..14
    """
    from data.models import Movie
    movies = db.query(Movie).all()

    records = []
    for movie in movies:
        mid = movie.movie_id
        title = movie.title
        year = movie.release_year
        genres = movie.genres if isinstance(movie.genres, list) else []
        avg_r = movie.avg_rating
        r_count = movie.rating_count

        genre_vec = get_genre_vector(genres)

        records.append({
            "movie_id":          mid,
            "title":             title,
            "release_year":      year or 2000,
            "avg_rating":        float(avg_r or 0),
            "rating_count_log":  float(np.log1p(r_count or 0)),
            **{f"genre_{i}": float(genre_vec[i]) for i in range(len(GENRES))},
        })

    df = pd.DataFrame(records).set_index("movie_id")

    # Normalise year and avg_rating to [0, 1]
    scaler = MinMaxScaler()
    df[["release_year", "avg_rating"]] = scaler.fit_transform(
        df[["release_year", "avg_rating"]]
    )
    return df


def build_content_soup(db: Session) -> pd.DataFrame:
    """
    Returns a DataFrame with movie_id and a 'soup' text column for TF-IDF.
    Soup = genres + director + cast + title keywords.
    """
    from data.models import Movie
    
    movies = db.query(Movie).all()

    records = []
    for movie in movies:
        mid = movie.movie_id
        title = movie.title
        genres = movie.genres if isinstance(movie.genres, list) else []
        lang = movie.language
        meta = movie.metadata_ if isinstance(movie.metadata_, dict) else {}

        director = meta.get("director", "")
        cast_json = meta.get("cast", [])
        
        cast = cast_json if isinstance(cast_json, list) else []
        director = director or ""

        soup = " ".join([
            " ".join(genres),
            director.replace(" ", "_"),
            " ".join(str(c).replace(" ", "_") for c in cast),
            title,
            lang or "",
        ]).strip()

        records.append({"movie_id": mid, "title": title, "soup": soup})

    return pd.DataFrame(records).set_index("movie_id")


def fit_tfidf(soup_df: pd.DataFrame, max_features: int = 10_000):
    """Fit TF-IDF on the soup column and return (matrix, vectorizer)."""
    tfidf = TfidfVectorizer(stop_words="english", max_features=max_features)
    matrix = tfidf.fit_transform(soup_df["soup"].fillna(""))
    return matrix, tfidf
