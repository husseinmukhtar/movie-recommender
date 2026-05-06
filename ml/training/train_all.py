"""
ml/training/train_all.py
End-to-end training pipeline:
  1. Loads data from DB
  2. Splits train/test temporally
  3. Trains ALS + ContentModel + Ranker
  4. Evaluates offline metrics
  5. Saves models

Run: python -m ml.training.train_all [--model-dir models/] [--run-name baseline]
"""
import argparse
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from config import get_settings
from data.database import db_session
from ml.evaluation.metrics import evaluate_all, train_test_split_temporal
from ml.features.item_features import build_content_soup, build_item_feature_matrix
from ml.features.user_features import build_user_feature_matrix
from ml.models.als_model import ALSTrainer
from ml.models.content_model import ContentModel
from ml.models.ranker import Ranker, build_ranker_features, RANKER_FEATURES

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)
settings = get_settings()


def load_ratings(db) -> pd.DataFrame:
    rows = db.execute(text(
        "SELECT user_id, movie_id, rating, rated_at FROM ratings ORDER BY rated_at"
    )).fetchall()
    ratings_df = pd.DataFrame(rows, columns=["user_id", "movie_id", "rating", "rated_at"])
    ratings_df["rated_at"] = pd.to_datetime(ratings_df["rated_at"], errors="coerce", utc=True)
    return ratings_df


def load_events(db) -> pd.DataFrame:
    rows = db.execute(text(
        "SELECT user_id, movie_id, event_type, watch_pct, occurred_at FROM events"
    )).fetchall()
    events_df = pd.DataFrame(rows, columns=["user_id", "movie_id", "event_type", "watch_pct", "occurred_at"])
    events_df["occurred_at"] = pd.to_datetime(events_df["occurred_at"], errors="coerce", utc=True)
    return events_df


def build_implicit_feedback(ratings_df: pd.DataFrame, events_df: pd.DataFrame) -> pd.DataFrame:
    """
    Augments ratings with implicit signals (clicks, watch%) to produce
    a richer interaction DataFrame for ALS training.
    """
    watch_events = events_df[events_df["event_type"] == "watch"].copy()
    watch_events["rating"] = (watch_events["watch_pct"].fillna(0) / 100) * 4 + 0.5
    watch_events["rated_at"] = pd.Timestamp.now('UTC')

    combined = pd.concat(
        [ratings_df[["user_id", "movie_id", "rating", "rated_at"]], 
         watch_events[["user_id", "movie_id", "rating", "rated_at"]]],
        ignore_index=True,
    )
    combined = (
        combined.sort_values("rating", ascending=False)
        .drop_duplicates(subset=["user_id", "movie_id"])
        .reset_index(drop=True)
    )
    logger.info("Combined feedback: %d interactions", len(combined))
    return combined


def build_ranker_training_data(
    cf_model: ALSTrainer,
    content_model: ContentModel,
    user_df: pd.DataFrame,
    item_df: pd.DataFrame,
    ground_truth: dict[int, set[int]],
    n_candidates: int = 100,
) -> tuple[pd.DataFrame, np.ndarray, np.ndarray]:
    """
    Builds training data for the re-ranker.
    """
    all_X, all_y, groups = [], [], []
    users_with_truth = [uid for uid in ground_truth if ground_truth[uid]]

    for uid in users_with_truth[:500]:
        try:
            cf_cands = cf_model.recommend(uid, n=n_candidates)
        except KeyError:
            continue

        cf_map = dict(cf_cands)
        user_history = list(cf_map.keys())[:10]
        content_cands = content_model.candidates_for_user(user_history, n=50)
        content_map = dict(content_cands)

        if uid not in user_df.index:
            continue
        user_feats = user_df.loc[uid]

        candidates = list(cf_cands)
        feats = build_ranker_features(candidates, content_map, user_feats, item_df)
        if feats.empty:
            continue

        labels = feats["movie_id"].isin(ground_truth[uid]).astype(int).values
        all_X.append(feats)
        all_y.append(labels)
        groups.append(len(feats))

    if not all_X:
        logger.warning("No ranker training data built — skipping ranker training")
        return pd.DataFrame(), np.array([]), np.array([])

    X = pd.concat(all_X, ignore_index=True)
    y = np.concatenate(all_y)
    group = np.array(groups)
    logger.info("Ranker training data: %d rows, %d queries", len(X), len(groups))
    return X, y, group


def run_training(model_dir: str = "models", run_name: str = "run"):
    logger.info("=" * 60)
    logger.info("Starting training pipeline — run: %s", run_name)
    logger.info("=" * 60)

    model_path = Path(model_dir)
    model_path.mkdir(parents=True, exist_ok=True)

    with db_session() as db:
        logger.info("[1/6] Loading data from database …")
        ratings_df = load_ratings(db)
        events_df  = load_events(db)
        logger.info("  %d ratings, %d events", len(ratings_df), len(events_df))

        if ratings_df.empty:
            logger.error("No ratings found. Run the seed script first.")
            return

        logger.info("[2/6] Building feature matrices …")
        user_df  = build_user_feature_matrix(db)
        item_df  = build_item_feature_matrix(db)
        soup_df  = build_content_soup(db)
        logger.info("  user_df: %s  item_df: %s", user_df.shape, item_df.shape)

    logger.info("[3/6] Splitting train/test …")
    combined_df = build_implicit_feedback(ratings_df, events_df)
    train_df, ground_truth = train_test_split_temporal(combined_df, test_frac=0.15)
    logger.info("  train: %d  test users with truth: %d", len(train_df), len(ground_truth))

    logger.info("[4/6] Training models …")

    als = ALSTrainer()
    als.fit(train_df)
    als.save(str(model_path / "als"))

    content = ContentModel()
    content.fit(soup_df)
    content.save(str(model_path / "content"))

    logger.info("  Building ranker training data …")
    X, y, group = build_ranker_training_data(als, content, user_df, item_df, ground_truth)
    ranker = Ranker(n_estimators=settings.ranker_n_estimators,
                    learning_rate=settings.ranker_learning_rate)
    if len(X) > 0 and y.sum() > 0:
        ranker.fit(X[RANKER_FEATURES], y, group)
    else:
        logger.warning("  Skipping ranker training — insufficient positive labels")
    ranker.save(str(model_path / "ranker"))

    # Save features for model registry
    user_df.to_pickle(model_path / "user_features.pkl")
    item_df.to_pickle(model_path / "item_features.pkl")

    logger.info("[5/6] Running offline evaluation …")
    all_movie_ids = set(item_df.index.tolist())
    sample_users  = list(ground_truth.keys())[:200]

    recommendations: dict[int, list[int]] = {}
    for uid in sample_users:
        try:
            cands = als.recommend(uid, n=50)
            recommendations[uid] = [mid for mid, _ in cands]
        except KeyError:
            pass

    if recommendations:
        metrics = evaluate_all(recommendations, ground_truth, all_movie_ids)
    else:
        logger.warning("No recommendations generated for evaluation")
        metrics = {}

    logger.info("[6/6] Training complete!")
    logger.info("  Models saved to: %s", model_dir)
    if metrics:
        logger.info("  precision@10 : %.4f", metrics.get("precision@10", 0))
        logger.info("  ndcg@10      : %.4f", metrics.get("ndcg@10", 0))
        logger.info("  coverage     : %.4f", metrics.get("coverage", 0))
        logger.info("  All targets met: %s", metrics.get("all_targets_met", False))

    return metrics


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train recommendation models")
    parser.add_argument("--model-dir", default="models", help="Directory to save models")
    parser.add_argument("--run-name", default="run", help="Name for this training run")
    args = parser.parse_args()
    run_training(model_dir=args.model_dir, run_name=args.run_name)
