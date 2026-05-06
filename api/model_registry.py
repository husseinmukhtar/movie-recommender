"""
api/model_registry.py
Singleton that loads ML models once at startup and provides them to routes.
Hot-reloads are supported via reload().
"""
import logging
import os
from pathlib import Path
from typing import Optional

import pandas as pd

from ml.models.als_model import ALSTrainer
from ml.models.content_model import ContentModel
from ml.models.hybrid_engine import HybridEngine
from ml.models.ranker import Ranker

logger = logging.getLogger(__name__)

_engine: Optional[HybridEngine] = None
_model_dir: str = os.environ.get("MODEL_DIR", "models")


def load_engine(model_dir: str = _model_dir) -> HybridEngine:
    """Load all models from disk and return a HybridEngine."""
    global _model_dir
    _model_dir = model_dir

    als_path     = Path(model_dir) / "als"
    content_path = Path(model_dir) / "content"
    ranker_path  = Path(model_dir) / "ranker"

    # Validate paths exist
    if not als_path.exists():
        raise FileNotFoundError(
            f"ALS model not found at {als_path}. "
            "Run: python -m ml.training.train_all first."
        )

    logger.info("Loading ALS model from %s …", als_path)
    als = ALSTrainer.load(str(als_path))

    logger.info("Loading ContentModel from %s …", content_path)
    content = ContentModel.load(str(content_path))

    logger.info("Loading Ranker from %s …", ranker_path)
    ranker = Ranker.load(str(ranker_path))

    # Load feature DFs for ranker (optional — improves quality)
    user_df, item_df = _load_feature_cache(model_dir)

    engine = HybridEngine(
        als=als,
        content=content,
        ranker=ranker,
        user_feature_df=user_df,
        item_feature_df=item_df,
    )
    logger.info("HybridEngine ready ✓")
    return engine


def _load_feature_cache(model_dir: str):
    """Try to load pre-computed feature DataFrames; return (None, None) on miss."""
    user_path = Path(model_dir) / "user_features.pkl"
    item_path = Path(model_dir) / "item_features.pkl"

    user_df = pd.read_pickle(user_path) if user_path.exists() else None
    item_df = pd.read_pickle(item_path) if item_path.exists() else None

    if user_df is not None:
        logger.info("User feature cache loaded (%d users)", len(user_df))
    if item_df is not None:
        logger.info("Item feature cache loaded (%d movies)", len(item_df))

    return user_df, item_df


def get_engine() -> HybridEngine:
    """FastAPI dependency: returns the global engine; raises 503 if not loaded."""
    if _engine is None:
        raise RuntimeError("ML engine not initialised. Check startup logs.")
    return _engine


def reload_engine(model_dir: str | None = None) -> HybridEngine:
    """Hot-reload models from disk without restarting the server."""
    global _engine
    _engine = load_engine(model_dir or _model_dir)
    logger.info("Engine reloaded successfully")
    return _engine


def try_load_engine(model_dir: str = _model_dir) -> bool:
    """
    Called at startup — tries to load models; logs warning if unavailable.
    Returns True on success.
    """
    global _engine
    try:
        _engine = load_engine(model_dir)
        return True
    except FileNotFoundError as e:
        logger.warning("Models not found at startup: %s", e)
        logger.warning("API will start but /recommendations will return 503 until models are trained.")
        return False
    except Exception as e:
        logger.error("Failed to load ML engine: %s", e, exc_info=True)
        return False
