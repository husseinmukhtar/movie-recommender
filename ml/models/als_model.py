import pickle
import logging
from pathlib import Path

import numpy as np
import scipy.sparse as sparse

logger = logging.getLogger(__name__)

class ALSTrainer:
    def __init__(self, factors=64, regularization=0.01, iterations=20, confidence_weight=40.0):
        self.factors = factors
        self.regularization = regularization
        self.iterations = iterations
        self.confidence_weight = confidence_weight
        
        self.user_factors = None
        self.item_factors = None
        self.user_id_to_idx = {}
        self.movie_id_to_idx = {}
        self.idx_to_user_id = {}
        self.idx_to_movie_id = {}
        self.user_item_matrix = None

    def _build_matrix(self, ratings_df):
        users = ratings_df["user_id"].astype("category")
        movies = ratings_df["movie_id"].astype("category")
        
        self.user_id_to_idx = {uid: i for i, uid in enumerate(users.cat.categories)}
        self.movie_id_to_idx = {mid: i for i, mid in enumerate(movies.cat.categories)}
        self.idx_to_user_id = {i: uid for uid, i in self.user_id_to_idx.items()}
        self.idx_to_movie_id = {i: mid for mid, i in self.movie_id_to_idx.items()}
        
        # Calculate confidence: 1 + alpha * r
        # ALS for implicit feedback treats all observed ratings as positive interactions 
        # with confidence proportional to the rating
        confidence = 1.0 + self.confidence_weight * ratings_df["rating"].values
        
        matrix = sparse.coo_matrix(
            (confidence, (users.cat.codes.values, movies.cat.codes.values)),
            shape=(len(self.user_id_to_idx), len(self.movie_id_to_idx)),
            dtype=np.float32
        ).tocsr()
        return matrix

    def _als_step(self, fixed_factors, matrix):
        n_solve, factors = matrix.shape[0], self.factors
        YtY = fixed_factors.T @ fixed_factors
        reg_eye = self.regularization * np.eye(factors)
        
        result = np.zeros((n_solve, factors), dtype=np.float32)
        
        for i in range(n_solve):
            row = matrix.getrow(i)
            if row.nnz == 0:
                continue
            
            idx = row.indices
            conf = row.data
            
            Y_i = fixed_factors[idx]
            
            # A = YtY + Y_i^T * (C_i - I) * Y_i + lambda * I
            A = YtY + (Y_i.T * (conf - 1)) @ Y_i + reg_eye
            
            # b = Y_i^T * C_i * p_i (p_i is 1 for observed interactions)
            b = (Y_i.T * conf).sum(axis=1)
            
            result[i] = np.linalg.solve(A, b)
            
        return result

    def fit(self, ratings_df):
        logger.info("Building user-item matrix...")
        self.user_item_matrix = self._build_matrix(ratings_df)
        n_users, n_items = self.user_item_matrix.shape
        
        logger.info(f"Matrix shape: {n_users} users, {n_items} items")
        
        rng = np.random.default_rng(42)
        self.user_factors = rng.standard_normal((n_users, self.factors)).astype(np.float32)
        self.item_factors = rng.standard_normal((n_items, self.factors)).astype(np.float32)
        
        item_user_matrix = self.user_item_matrix.T.tocsr()
        
        logger.info(f"Training ALS: factors={self.factors} iterations={self.iterations}")
        for it in range(self.iterations):
            # Update user factors
            self.user_factors = self._als_step(self.item_factors, self.user_item_matrix)
            # Update item factors
            self.item_factors = self._als_step(self.user_factors, item_user_matrix)
            
            if (it + 1) % 5 == 0:
                logger.info(f"  ALS iteration {it + 1}/{self.iterations}")
            
        logger.info("ALS training complete")
        return self

    def recommend(self, user_id, n=500, filter_seen=True):
        if self.user_factors is None:
            raise RuntimeError("Model not trained.")
        
        if user_id not in self.user_id_to_idx:
            raise KeyError(f"user_id {user_id} not in ALS model")
            
        u_idx = self.user_id_to_idx[user_id]
        
        scores = self.item_factors @ self.user_factors[u_idx]
        
        if filter_seen:
            seen_idx = self.user_item_matrix[u_idx].indices
            scores[seen_idx] = -np.inf
            
        top_indices = np.argsort(scores)[::-1][:n]
        
        results = []
        for idx in top_indices:
            if scores[idx] > -np.inf:
                movie_id = self.idx_to_movie_id[idx]
                results.append((movie_id, float(scores[idx])))
                
        return results

    def similar_items(self, movie_id, n=20):
        if self.item_factors is None:
            raise RuntimeError("Model not trained.")
            
        if movie_id not in self.movie_id_to_idx:
            raise KeyError(f"movie_id {movie_id} not in ALS model")
            
        m_idx = self.movie_id_to_idx[movie_id]
        
        # Calculate cosine similarity for items
        norms = np.linalg.norm(self.item_factors, axis=1)
        norms[norms == 0] = 1e-10
        normalized_items = self.item_factors / norms[:, np.newaxis]
        
        target_factor = normalized_items[m_idx]
        scores = normalized_items @ target_factor
        
        scores[m_idx] = -np.inf  # Don't recommend the item itself
        
        top_indices = np.argsort(scores)[::-1][:n]
        
        results = []
        for idx in top_indices:
            if scores[idx] > -np.inf:
                rec_movie_id = self.idx_to_movie_id[idx]
                results.append((rec_movie_id, float(scores[idx])))
                
        return results

    def save(self, path):
        path_obj = Path(path)
        path_obj.mkdir(parents=True, exist_ok=True)
        
        np.savez(
            path_obj / "als_factors.npz", 
            user_factors=self.user_factors, 
            item_factors=self.item_factors
        )
        sparse.save_npz(path_obj / "user_item.npz", self.user_item_matrix)
        
        with open(path_obj / "metadata.pkl", "wb") as f:
            pickle.dump({
                "user_id_to_idx": self.user_id_to_idx,
                "movie_id_to_idx": self.movie_id_to_idx,
                "idx_to_user_id": self.idx_to_user_id,
                "idx_to_movie_id": self.idx_to_movie_id,
                "factors": self.factors,
                "regularization": self.regularization,
                "iterations": self.iterations,
                "confidence_weight": self.confidence_weight
            }, f)

    @classmethod
    def load(cls, path):
        path_obj = Path(path)
        
        with open(path_obj / "metadata.pkl", "rb") as f:
            meta = pickle.load(f)
            
        conf_weight = meta.get("confidence_weight", 40.0)
            
        inst = cls(
            factors=meta["factors"], 
            regularization=meta["regularization"], 
            iterations=meta["iterations"],
            confidence_weight=conf_weight
        )
        
        inst.user_id_to_idx = meta["user_id_to_idx"]
        inst.movie_id_to_idx = meta["movie_id_to_idx"]
        inst.idx_to_user_id = meta["idx_to_user_id"]
        inst.idx_to_movie_id = meta["idx_to_movie_id"]
        
        data = np.load(path_obj / "als_factors.npz")
        inst.user_factors = data["user_factors"]
        inst.item_factors = data["item_factors"]
        
        inst.user_item_matrix = sparse.load_npz(path_obj / "user_item.npz")
        
        return inst
