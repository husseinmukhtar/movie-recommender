"""
ml/models/content_model.py
Content-based filtering using TF-IDF cosine similarity.
"""
import logging
import pickle
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity

from ml.features.item_features import fit_tfidf

logger = logging.getLogger(__name__)


class ContentModel:
    """
    Computes item-item similarity from movie metadata (genres, cast, director).
    Used to generate content-based candidate sets.
    """

    def __init__(self, max_features: int = 10_000):
        self.max_features    = max_features
        self.tfidf           = None
        self.tfidf_matrix    = None          # sparse (n_movies, max_features)
        self.movie_id_to_idx: dict = {}
        self.idx_to_movie_id: dict = {}
        self.movie_ids: list  = []

    # ── Fitting ───────────────────────────────────────────────────────────────

    def fit(self, soup_df: pd.DataFrame) -> "ContentModel":
        """
        soup_df: DataFrame with index=movie_id, column='soup' (raw text).
        """
        self.movie_ids       = list(soup_df.index)
        self.movie_id_to_idx = {mid: i for i, mid in enumerate(self.movie_ids)}
        self.idx_to_movie_id = {i: mid for i, mid in enumerate(self.movie_ids)}

        self.tfidf_matrix, self.tfidf = fit_tfidf(soup_df, self.max_features)
        logger.info(
            "ContentModel fitted: %d movies, %d TF-IDF features",
            len(self.movie_ids), self.max_features,
        )
        return self

    # ── Inference ─────────────────────────────────────────────────────────────

    def similar_to_movie(
        self, movie_id: int, n: int = 200
    ) -> list[tuple[int, float]]:
        """
        Returns [(movie_id, similarity_score), …] most similar to movie_id.
        """
        if movie_id not in self.movie_id_to_idx:
            raise KeyError(f"movie_id {movie_id} not in content model")

        idx = self.movie_id_to_idx[movie_id]
        sims = cosine_similarity(
            self.tfidf_matrix[idx], self.tfidf_matrix
        ).flatten()

        top_idx = np.argsort(sims)[::-1]
        results = []
        for i in top_idx:
            if i == idx:
                continue
            results.append((self.idx_to_movie_id[i], float(sims[i])))
            if len(results) >= n:
                break
        return results

    def candidates_for_user(
        self,
        watch_history: list[int],
        n: int = 200,
    ) -> list[tuple[int, float]]:
        """
        Aggregates content similarity across a user's watch history.
        Returns the top-n unseen content-similar candidates.
        """
        if not watch_history:
            return []

        seen_set = set(watch_history)
        score_map: dict[int, float] = {}

        for mid in watch_history:
            if mid not in self.movie_id_to_idx:
                continue
            for candidate_id, score in self.similar_to_movie(mid, n=50):
                if candidate_id not in seen_set:
                    score_map[candidate_id] = max(
                        score_map.get(candidate_id, 0.0), score
                    )

        sorted_candidates = sorted(score_map.items(), key=lambda x: x[1], reverse=True)
        return sorted_candidates[:n]

    # ── Persistence ───────────────────────────────────────────────────────────

    def save(self, path: str) -> None:
        p = Path(path)
        p.mkdir(parents=True, exist_ok=True)
        with open(p / "content_model.pkl", "wb") as f:
            pickle.dump({
                "tfidf":           self.tfidf,
                "tfidf_matrix":    self.tfidf_matrix,
                "movie_id_to_idx": self.movie_id_to_idx,
                "idx_to_movie_id": self.idx_to_movie_id,
                "movie_ids":       self.movie_ids,
                "max_features":    self.max_features,
            }, f)
        logger.info("ContentModel saved to %s", path)

    @classmethod
    def load(cls, path: str) -> "ContentModel":
        p = Path(path)
        with open(p / "content_model.pkl", "rb") as f:
            data = pickle.load(f)
        instance = cls(max_features=data["max_features"])
        instance.tfidf           = data["tfidf"]
        instance.tfidf_matrix    = data["tfidf_matrix"]
        instance.movie_id_to_idx = data["movie_id_to_idx"]
        instance.idx_to_movie_id = data["idx_to_movie_id"]
        instance.movie_ids       = data["movie_ids"]
        logger.info("ContentModel loaded from %s", path)
        return instance
