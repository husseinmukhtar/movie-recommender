"""
ml/models/hybrid_engine.py
Orchestrates ALS + Content + Ranker into the unified recommendation pipeline.

Pipeline:
  1. ALS generates up to `pool` candidates (collaborative signal)
  2. ContentModel adds content-similar candidates from watch history
  3. Candidates are merged and de-duplicated
  4. Ranker scores and re-orders the merged pool
  5. Top-n enriched results returned
"""
import logging
from dataclasses import dataclass, field
from typing import Optional

import pandas as pd

from ml.models.als_model import ALSTrainer
from ml.models.content_model import ContentModel
from ml.models.ranker import Ranker, build_ranker_features

logger = logging.getLogger(__name__)


@dataclass
class HybridEngine:
    als:     ALSTrainer
    content: ContentModel
    ranker:  Ranker

    # Optional caches (injected at runtime for performance)
    user_feature_df: Optional[pd.DataFrame] = field(default=None)
    item_feature_df: Optional[pd.DataFrame] = field(default=None)

    # ── Main entry point ──────────────────────────────────────────────────────

    def recommend(
        self,
        user_id:      int,
        watch_history: list[int],
        n:            int = 10,
        strategy:     str = "hybrid",   # hybrid | cf | content | popular
        seen_ids:     set[int] | None = None,
        genre_filter: str | None = None,
    ) -> list[dict]:
        """
        Returns a ranked list of recommendation dicts:
          [{ movie_id, score, strategy, explanation }, ...]
        """
        seen_ids = seen_ids or set()

        if strategy == "cf":
            return self._cf_only(user_id, n, seen_ids, genre_filter)
        if strategy == "content":
            return self._content_only(watch_history, n, seen_ids, genre_filter)
        if strategy == "popular":
            return self._popular(n, seen_ids, genre_filter)

        return self._hybrid(user_id, watch_history, n, seen_ids, genre_filter)

    # ── Strategy implementations ──────────────────────────────────────────────

    def _hybrid(
        self,
        user_id: int,
        watch_history: list[int],
        n: int,
        seen_ids: set[int],
        genre_filter: str | None,
    ) -> list[dict]:
        # 1. CF candidates
        try:
            cf_candidates = self.als.recommend(user_id, n=400, filter_seen=True)
        except KeyError:
            logger.warning("User %d not in ALS model — cold start fallback", user_id)
            cf_candidates = []

        cf_map = dict(cf_candidates)

        # 2. Content candidates
        content_candidates = self.content.candidates_for_user(watch_history, n=200)
        content_map = dict(content_candidates)

        # 3. Merge + de-duplicate
        all_ids = list({**cf_map, **content_map}.keys() - seen_ids)

        if not all_ids:
            logger.warning("Empty candidate pool for user %d", user_id)
            return []

        # 4. Build ranker feature matrix
        if self.user_feature_df is not None and user_id in self.user_feature_df.index:
            user_feats = self.user_feature_df.loc[user_id]
        else:
            user_feats = pd.Series({"avg_rating": 3.0, "n_ratings": 0,
                                    **{f"genre_{i}": 0.0 for i in range(15)}})

        item_feats = self.item_feature_df if self.item_feature_df is not None else pd.DataFrame()

        candidates = [(mid, cf_map.get(mid, 0.0)) for mid in all_ids]
        features_df = build_ranker_features(candidates, content_map, user_feats, item_feats)

        # 5. Rank
        ranked = self.ranker.rank(features_df, n=n * 3)

        # 6. Genre filter + trim
        results = []
        for movie_id, score in ranked:
            if genre_filter and not self._movie_has_genre(movie_id, genre_filter):
                continue
            results.append({
                "movie_id": movie_id,
                "score":    round(float(score), 4),
                "strategy": "hybrid",
                "explanation": self._explain(movie_id, user_id, cf_map, content_map),
            })
            if len(results) >= n:
                break

        return results

    def _cf_only(self, user_id, n, seen_ids, genre_filter) -> list[dict]:
        try:
            candidates = self.als.recommend(user_id, n=n * 3)
        except KeyError:
            return []
        results = []
        for mid, score in candidates:
            if mid in seen_ids:
                continue
            if genre_filter and not self._movie_has_genre(mid, genre_filter):
                continue
            results.append({"movie_id": mid, "score": round(score, 4),
                             "strategy": "cf", "explanation": "Users like you also enjoyed this"})
            if len(results) >= n:
                break
        return results

    def _content_only(self, watch_history, n, seen_ids, genre_filter) -> list[dict]:
        candidates = self.content.candidates_for_user(watch_history, n=n * 3)
        results = []
        for mid, score in candidates:
            if mid in seen_ids:
                continue
            if genre_filter and not self._movie_has_genre(mid, genre_filter):
                continue
            results.append({"movie_id": mid, "score": round(score, 4),
                             "strategy": "content", "explanation": "Similar to movies you watched"})
            if len(results) >= n:
                break
        return results

    def _popular(self, n, seen_ids, genre_filter) -> list[dict]:
        """Fallback: highest-rated movies not yet seen."""
        if self.item_feature_df is None:
            return []
        df = self.item_feature_df.copy()
        df = df[~df.index.isin(seen_ids)]
        if genre_filter:
            df = df[df.index.map(lambda mid: self._movie_has_genre(mid, genre_filter))]
        df = df.nlargest(n, "avg_rating")
        return [
            {"movie_id": mid, "score": round(float(row["avg_rating"]), 4),
             "strategy": "popular", "explanation": "Highly rated by everyone"}
            for mid, row in df.iterrows()
        ]

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _movie_has_genre(self, movie_id: int, genre: str) -> bool:
        if self.item_feature_df is None or movie_id not in self.item_feature_df.index:
            return True   # can't filter, allow through
        # Genre columns are binary 0/1 flags
        col = f"genre_{self._genre_idx(genre)}"
        return bool(self.item_feature_df.at[movie_id, col] > 0) if col in self.item_feature_df.columns else True

    @staticmethod
    def _genre_idx(genre: str) -> int:
        from ml.features.user_features import GENRE_INDEX
        return GENRE_INDEX.get(genre, -1)

    @staticmethod
    def _explain(movie_id, user_id, cf_map, content_map) -> str:
        in_cf      = movie_id in cf_map
        in_content = movie_id in content_map
        if in_cf and in_content:
            return "Loved by users like you and matches your taste"
        if in_cf:
            return "Users with similar taste enjoyed this"
        return "Similar to movies you watched"
