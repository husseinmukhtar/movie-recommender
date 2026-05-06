"""
ml/evaluation/metrics.py
Offline recommendation quality metrics.

All functions accept:
  recommendations: dict[user_id → list[movie_id]]   (ordered, top-K)
  ground_truth:    dict[user_id → set[movie_id]]     (relevant items)
"""
import logging
import math
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


# ─── Core metric functions ────────────────────────────────────────────────────

def precision_at_k(
    recommendations: dict[int, list[int]],
    ground_truth:    dict[int, set[int]],
    k: int = 10,
) -> float:
    """Fraction of top-K recommendations that are relevant, averaged over users."""
    scores = []
    for user_id, recs in recommendations.items():
        relevant = ground_truth.get(user_id, set())
        if not relevant:
            continue
        hits = sum(1 for mid in recs[:k] if mid in relevant)
        scores.append(hits / k)
    return float(np.mean(scores)) if scores else 0.0


def recall_at_k(
    recommendations: dict[int, list[int]],
    ground_truth:    dict[int, set[int]],
    k: int = 50,
) -> float:
    """Fraction of relevant items captured in top-K recommendations."""
    scores = []
    for user_id, recs in recommendations.items():
        relevant = ground_truth.get(user_id, set())
        if not relevant:
            continue
        hits = sum(1 for mid in recs[:k] if mid in relevant)
        scores.append(hits / len(relevant))
    return float(np.mean(scores)) if scores else 0.0


def ndcg_at_k(
    recommendations: dict[int, list[int]],
    ground_truth:    dict[int, set[int]],
    k: int = 10,
) -> float:
    """Normalized Discounted Cumulative Gain at K."""
    def dcg(hits: list[int]) -> float:
        return sum(h / math.log2(i + 2) for i, h in enumerate(hits))

    scores = []
    for user_id, recs in recommendations.items():
        relevant = ground_truth.get(user_id, set())
        if not relevant:
            continue
        hits    = [1 if mid in relevant else 0 for mid in recs[:k]]
        ideal   = [1] * min(k, len(relevant)) + [0] * max(0, k - len(relevant))
        ideal_dcg = dcg(ideal)
        if ideal_dcg == 0:
            continue
        scores.append(dcg(hits) / ideal_dcg)

    return float(np.mean(scores)) if scores else 0.0


def mean_reciprocal_rank(
    recommendations: dict[int, list[int]],
    ground_truth:    dict[int, set[int]],
) -> float:
    """Mean Reciprocal Rank of the first relevant item."""
    scores = []
    for user_id, recs in recommendations.items():
        relevant = ground_truth.get(user_id, set())
        if not relevant:
            continue
        rr = 0.0
        for rank, mid in enumerate(recs, start=1):
            if mid in relevant:
                rr = 1.0 / rank
                break
        scores.append(rr)
    return float(np.mean(scores)) if scores else 0.0


def catalog_coverage(
    recommendations: dict[int, list[int]],
    all_movie_ids:   set[int],
) -> float:
    """Fraction of the catalog recommended to at least one user."""
    recommended = set(mid for recs in recommendations.values() for mid in recs)
    return len(recommended & all_movie_ids) / len(all_movie_ids) if all_movie_ids else 0.0


def novelty(
    recommendations: dict[int, list[int]],
    popularity: dict[int, int],   # movie_id → interaction count
    n_users: int,
) -> float:
    """
    Mean self-information of recommended items.
    Higher = more novel (less popular) recommendations.
    """
    scores = []
    for recs in recommendations.values():
        for mid in recs:
            pop = popularity.get(mid, 1)
            prob = pop / n_users
            scores.append(-math.log2(max(prob, 1e-10)))
    return float(np.mean(scores)) if scores else 0.0


# ─── Convenience wrapper ──────────────────────────────────────────────────────

def evaluate_all(
    recommendations: dict[int, list[int]],
    ground_truth:    dict[int, set[int]],
    all_movie_ids:   set[int],
    popularity:      dict[int, int] | None = None,
    n_users:         int = 1,
) -> dict[str, Any]:
    """
    Runs all metrics and returns a summary dict.
    Targets from the project spec are included for reference.
    """
    metrics = {
        "precision@10": precision_at_k(recommendations, ground_truth, k=10),
        "recall@50":    recall_at_k(recommendations, ground_truth, k=50),
        "ndcg@10":      ndcg_at_k(recommendations, ground_truth, k=10),
        "mrr":          mean_reciprocal_rank(recommendations, ground_truth),
        "coverage":     catalog_coverage(recommendations, all_movie_ids),
    }
    if popularity:
        metrics["novelty"] = novelty(recommendations, popularity, n_users)

    # Targets from project spec
    targets = {
        "precision@10": 0.35,
        "recall@50":    0.60,
        "ndcg@10":      0.42,
        "mrr":          0.28,
        "coverage":     0.40,
    }

    passed = {k: (v >= targets[k]) for k, v in metrics.items() if k in targets}
    metrics["targets_passed"] = passed
    metrics["all_targets_met"] = all(passed.values())

    logger.info("=== Evaluation Results ===")
    for k, v in metrics.items():
        if isinstance(v, float):
            target_str = f" (target ≥ {targets[k]:.2f})" if k in targets else ""
            status = "✓" if passed.get(k, True) else "✗"
            logger.info("  %s %s: %.4f%s", status, k, v, target_str)

    return metrics


# ─── Holdout split helper ─────────────────────────────────────────────────────

def train_test_split_temporal(
    ratings_df: pd.DataFrame,
    test_frac: float = 0.2,
) -> tuple[pd.DataFrame, dict[int, set[int]]]:
    """
    Temporal split: most recent `test_frac` of each user's ratings → test set.
    Returns (train_df, ground_truth_dict).
    """
    ratings_df = ratings_df.dropna(subset=["rated_at"])
    ratings_df = ratings_df.sort_values("rated_at")
    train_rows, test_rows = [], []

    for _, group in ratings_df.groupby("user_id"):
        n_test = max(1, int(len(group) * test_frac))
        train_rows.append(group.iloc[:-n_test])
        test_rows.append(group.iloc[-n_test:])

    train_df = pd.concat(train_rows)
    test_df  = pd.concat(test_rows)

    # Only treat highly-rated items as relevant (≥ 4.0)
    ground_truth = (
        test_df[test_df["rating"] >= 4.0]
        .groupby("user_id")["movie_id"]
        .apply(set)
        .to_dict()
    )
    return train_df, ground_truth
