"""
ml/models/ranker.py
LightGBM re-ranker: takes candidate (user, movie) pairs with features
and outputs a ranked list. Trained on logged impression/click data.
"""
import logging
import pickle
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


# Features used by the ranker — must match feature engineering below
RANKER_FEATURES = [
    "als_score",          # score from collaborative filter
    "content_score",      # score from content model
    "movie_avg_rating",   # global movie quality signal
    "movie_rating_count_log",
    "movie_release_year_norm",
    "user_avg_rating",    # user behaviour signals
    "user_n_ratings",
    # Genre match features (user pref × movie genre)
    *[f"genre_match_{i}" for i in range(15)],
]


def build_ranker_features(
    candidates: list[tuple[int, float]],   # [(movie_id, als_score)]
    content_scores: dict[int, float],       # movie_id → content score
    user_features: pd.Series,              # from user feature matrix
    item_features: pd.DataFrame,            # full item feature matrix
) -> pd.DataFrame:
    """
    Assembles the feature matrix for the re-ranker.
    Returns a DataFrame with columns = RANKER_FEATURES.
    """
    rows = []
    for movie_id, als_score in candidates:
        if movie_id not in item_features.index:
            continue
        item = item_features.loc[movie_id]

        # Genre match: dot product between user genre prefs and item genre vec
        user_genre = np.array([user_features.get(f"genre_{i}", 0.0) for i in range(15)])
        item_genre = np.array([item.get(f"genre_{i}", 0.0)          for i in range(15)])
        genre_match = user_genre * item_genre  # element-wise

        row = {
            "movie_id":               movie_id,
            "als_score":              als_score,
            "content_score":          content_scores.get(movie_id, 0.0),
            "movie_avg_rating":       item.get("avg_rating", 0.0),
            "movie_rating_count_log": item.get("rating_count_log", 0.0),
            "movie_release_year_norm":item.get("release_year", 0.5),
            "user_avg_rating":        user_features.get("avg_rating", 3.0),
            "user_n_ratings":         user_features.get("n_ratings", 0),
            **{f"genre_match_{i}": float(genre_match[i]) for i in range(15)},
        }
        rows.append(row)

    if not rows:
        return pd.DataFrame(columns=["movie_id"] + RANKER_FEATURES)

    df = pd.DataFrame(rows)
    return df


class Ranker:
    """
    Wraps a LightGBM ranking model.
    """

    def __init__(
        self,
        n_estimators: int = 500,
        learning_rate: float = 0.05,
        num_leaves: int = 63,
    ):
        self.n_estimators  = n_estimators
        self.learning_rate = learning_rate
        self.num_leaves    = num_leaves
        self.model: lgb.Booster | None = None

    # ── Training ──────────────────────────────────────────────────────────────

    def fit(
        self,
        X: pd.DataFrame,         # feature matrix (RANKER_FEATURES columns)
        y: np.ndarray,            # relevance labels (0/1 or 0-4)
        group: np.ndarray,        # query group sizes for LTR
        X_val: pd.DataFrame | None = None,
        y_val: np.ndarray | None = None,
        group_val: np.ndarray | None = None,
    ) -> "Ranker":
        train_data = lgb.Dataset(X[RANKER_FEATURES], label=y, group=group)
        valid_sets = []
        if X_val is not None:
            val_data = lgb.Dataset(X_val[RANKER_FEATURES], label=y_val, group=group_val)
            valid_sets = [val_data]

        params = {
            "objective":    "lambdarank",
            "metric":       "ndcg",
            "ndcg_eval_at": [10],
            "num_leaves":   self.num_leaves,
            "learning_rate": self.learning_rate,
            "min_data_in_leaf": 20,
            "verbosity":    -1,
        }
        callbacks = [lgb.early_stopping(50, verbose=False), lgb.log_evaluation(50)]

        self.model = lgb.train(
            params,
            train_data,
            num_boost_round=self.n_estimators,
            valid_sets=valid_sets or None,
            callbacks=callbacks if valid_sets else [lgb.log_evaluation(100)],
        )
        logger.info("Ranker trained with %d trees", self.model.num_trees())
        return self

    # ── Inference ─────────────────────────────────────────────────────────────

    def rank(
        self,
        features_df: pd.DataFrame,
        n: int = 50,
    ) -> list[tuple[int, float]]:
        """
        Returns [(movie_id, ranker_score), …] sorted descending.
        features_df must have 'movie_id' + RANKER_FEATURES columns.
        """
        if self.model is None:
            # Fallback: sort by ALS score if ranker not trained
            logger.warning("Ranker not trained — using ALS score fallback")
            df = features_df.sort_values("als_score", ascending=False).head(n)
            return list(zip(df["movie_id"].tolist(), df["als_score"].tolist()))

        missing = set(RANKER_FEATURES) - set(features_df.columns)
        if missing:
            raise ValueError(f"Missing ranker features: {missing}")

        scores = self.model.predict(features_df[RANKER_FEATURES])
        features_df = features_df.copy()
        features_df["_score"] = scores
        top = features_df.nlargest(n, "_score")
        return list(zip(top["movie_id"].tolist(), top["_score"].tolist()))

    # ── Persistence ───────────────────────────────────────────────────────────

    def save(self, path: str) -> None:
        p = Path(path)
        p.mkdir(parents=True, exist_ok=True)
        if self.model:
            self.model.save_model(str(p / "ranker.lgb"))
        with open(p / "ranker_meta.pkl", "wb") as f:
            pickle.dump({
                "n_estimators":  self.n_estimators,
                "learning_rate": self.learning_rate,
                "num_leaves":    self.num_leaves,
            }, f)
        logger.info("Ranker saved to %s", path)

    @classmethod
    def load(cls, path: str) -> "Ranker":
        p = Path(path)
        with open(p / "ranker_meta.pkl", "rb") as f:
            meta = pickle.load(f)
        instance = cls(**meta)
        model_path = p / "ranker.lgb"
        if model_path.exists():
            instance.model = lgb.Booster(model_file=str(model_path))
        logger.info("Ranker loaded from %s", path)
        return instance
