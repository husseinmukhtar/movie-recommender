"""
tests/test_all.py
Full test suite: unit tests for ML models, metrics, and API integration tests.
Run: pytest tests/test_all.py -v
"""
import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from api.main import create_app
from data.database import get_db
from data.models import Base, Event, Movie, Rating, User

# ─── Test database setup ─────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def test_db_url(tmp_path_factory):
    db_dir = tmp_path_factory.mktemp("db")
    db_path = db_dir / "test_recommender.db"
    return f"sqlite:///{db_path.as_posix()}"

@pytest.fixture(scope="session")
def test_engine(test_db_url):
    engine = create_engine(test_db_url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture(scope="session")
def TestSession(test_engine):
    return sessionmaker(bind=test_engine, autocommit=False, autoflush=False)


@pytest.fixture
def db(TestSession):
    session = TestSession()
    yield session
    session.rollback()
    session.close()


@pytest.fixture(scope="session")
def seeded_db(test_engine, TestSession):
    """One-time DB seed for the session."""
    from api.middleware.auth import hash_password
    session = TestSession()

    # Movies
    movies = []
    for i in range(1, 21):
        m = Movie(
            movie_id=i,
            title=f"Test Movie {i}",
            release_year=2000 + i,
            genres=["Action"] if i % 2 == 0 else ["Drama"],
            avg_rating=round(3.0 + (i % 5) * 0.4, 1),
            rating_count=100 * i,
            metadata_={},
        )
        session.add(m)
        movies.append(m)

    # Users
    users = []
    for j in range(1, 6):
        u = User(
            user_id=j,
            username=f"testuser{j}",
            email=f"test{j}@example.com",
            hashed_pw=hash_password("password123"),
            preferences={},
        )
        session.add(u)
        users.append(u)

    session.flush()

    # Ratings
    for u in users:
        for m in movies[:15]:
            session.add(Rating(user_id=u.user_id, movie_id=m.movie_id,
                               rating=round(3.0 + (m.movie_id % 5) * 0.4, 1)))

    # Events
    for u in users:
        for m in movies[:10]:
            session.add(Event(user_id=u.user_id, movie_id=m.movie_id,
                              event_type="watch", watch_pct=80.0))

    session.commit()
    session.close()
    return TestSession


# ─── Unit Tests: Metrics ─────────────────────────────────────────────────────

class TestMetrics:
    def test_precision_at_k_perfect(self):
        from ml.evaluation.metrics import precision_at_k
        recs   = {1: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]}
        truth  = {1: {1, 2, 3, 4, 5, 6, 7, 8, 9, 10}}
        result = precision_at_k(recs, truth, k=10)
        assert result == pytest.approx(1.0)

    def test_precision_at_k_zero(self):
        from ml.evaluation.metrics import precision_at_k
        recs  = {1: [11, 12, 13]}
        truth = {1: {1, 2, 3}}
        assert precision_at_k(recs, truth, k=3) == pytest.approx(0.0)

    def test_precision_at_k_partial(self):
        from ml.evaluation.metrics import precision_at_k
        recs  = {1: [1, 99, 2, 99, 99]}
        truth = {1: {1, 2}}
        result = precision_at_k(recs, truth, k=5)
        assert result == pytest.approx(2/5)

    def test_recall_at_k(self):
        from ml.evaluation.metrics import recall_at_k
        recs  = {1: [1, 2, 3, 99, 99]}
        truth = {1: {1, 2, 3, 4, 5}}
        assert recall_at_k(recs, truth, k=5) == pytest.approx(3/5)

    def test_ndcg_perfect(self):
        from ml.evaluation.metrics import ndcg_at_k
        recs  = {1: [1, 2, 3]}
        truth = {1: {1, 2, 3}}
        assert ndcg_at_k(recs, truth, k=3) == pytest.approx(1.0)

    def test_ndcg_worst(self):
        from ml.evaluation.metrics import ndcg_at_k
        recs  = {1: [4, 5, 6]}
        truth = {1: {1, 2, 3}}
        assert ndcg_at_k(recs, truth, k=3) == pytest.approx(0.0)

    def test_mrr_first_hit(self):
        from ml.evaluation.metrics import mean_reciprocal_rank
        recs  = {1: [99, 1, 99]}
        truth = {1: {1}}
        assert mean_reciprocal_rank(recs, truth) == pytest.approx(1/2)

    def test_coverage(self):
        from ml.evaluation.metrics import catalog_coverage
        recs     = {1: [1, 2], 2: [3, 4]}
        all_ids  = {1, 2, 3, 4, 5, 6, 7, 8}
        result   = catalog_coverage(recs, all_ids)
        assert result == pytest.approx(4/8)

    def test_temporal_split(self):
        from ml.evaluation.metrics import train_test_split_temporal
        df = pd.DataFrame({
            "user_id":  [1]*10,
            "movie_id": list(range(10)),
            "rating":   [4.5]*10,
            "rated_at": pd.date_range("2024-01-01", periods=10, freq="D"),
        })
        train, truth = train_test_split_temporal(df, test_frac=0.2)
        assert len(train) == 8
        assert 1 in truth  # user 1 should have relevant items


# ─── Unit Tests: ALS Model ───────────────────────────────────────────────────

class TestALSModel:
    @pytest.fixture
    def ratings_df(self):
        rows = []
        for uid in range(1, 11):
            for mid in range(1, 21):
                if (uid + mid) % 3 != 0:
                    rows.append({"user_id": uid, "movie_id": mid,
                                 "rating": round(2.5 + (uid*mid % 5)*0.5, 1)})
        return pd.DataFrame(rows)

    def test_fit_and_recommend(self, ratings_df):
        from ml.models.als_model import ALSTrainer
        trainer = ALSTrainer(factors=16, iterations=5)
        trainer.fit(ratings_df)
        recs = trainer.recommend(1, n=5)
        assert len(recs) > 0
        assert all(isinstance(mid, int) for mid, _ in recs)
        assert all(isinstance(score, float) for _, score in recs)

    def test_similar_items(self, ratings_df):
        from ml.models.als_model import ALSTrainer
        trainer = ALSTrainer(factors=16, iterations=5)
        trainer.fit(ratings_df)
        similar = trainer.similar_items(1, n=5)
        assert len(similar) > 0
        assert all(mid != 1 for mid, _ in similar)

    def test_save_and_load(self, ratings_df, tmp_path):
        from ml.models.als_model import ALSTrainer
        trainer = ALSTrainer(factors=16, iterations=5)
        trainer.fit(ratings_df)
        save_path = str(tmp_path / "als_test")
        trainer.save(save_path)
        loaded = ALSTrainer.load(save_path)
        # After load, user_item_matrix is a zero matrix — recommend still works
        recs = loaded.recommend(1, n=5)
        assert len(recs) > 0   # should return items even with zero history matrix

    def test_unknown_user_raises(self, ratings_df):
        from ml.models.als_model import ALSTrainer
        trainer = ALSTrainer(factors=16, iterations=5)
        trainer.fit(ratings_df)
        with pytest.raises(KeyError):
            trainer.recommend(99999, n=5)


# ─── Unit Tests: Content Model ───────────────────────────────────────────────

class TestContentModel:
    @pytest.fixture
    def soup_df(self):
        data = {
            "movie_id": list(range(1, 11)),
            "title":    [f"Movie {i}" for i in range(1, 11)],
            "soup":     [
                "Action Thriller Christopher_Nolan Leonardo_DiCaprio",
                "Sci-Fi Drama Ridley_Scott Matt_Damon",
                "Action Adventure Steven_Spielberg Harrison_Ford",
                "Comedy Romance Richard_Curtis Hugh_Grant",
                "Drama Crime Martin_Scorsese Robert_De_Niro",
                "Action Christopher_Nolan Christian_Bale",
                "Sci-Fi Thriller James_Cameron Arnold_Schwarzenegger",
                "Comedy Adam_Sandler Drew_Barrymore",
                "Horror Thriller Alfred_Hitchcock",
                "Animation Family Pixar",
            ],
        }
        return pd.DataFrame(data).set_index("movie_id")

    def test_fit_and_similar(self, soup_df):
        from ml.models.content_model import ContentModel
        model = ContentModel(max_features=100)
        model.fit(soup_df)
        similar = model.similar_to_movie(1, n=3)
        assert len(similar) == 3
        assert all(mid != 1 for mid, _ in similar)
        # Action/Nolan movie (id=6) should be most similar to id=1
        similar_ids = [mid for mid, _ in similar]
        assert 6 in similar_ids

    def test_candidates_for_user(self, soup_df):
        from ml.models.content_model import ContentModel
        model = ContentModel(max_features=100)
        model.fit(soup_df)
        cands = model.candidates_for_user(watch_history=[1, 2], n=5)
        assert len(cands) > 0
        assert all(mid not in {1, 2} for mid, _ in cands)

    def test_save_and_load(self, soup_df, tmp_path):
        from ml.models.content_model import ContentModel
        model = ContentModel(max_features=100)
        model.fit(soup_df)
        model.save(str(tmp_path / "content"))
        loaded = ContentModel.load(str(tmp_path / "content"))
        orig   = model.similar_to_movie(1, n=3)
        reloaded = loaded.similar_to_movie(1, n=3)
        assert [m for m, _ in orig] == [m for m, _ in reloaded]


# ─── Unit Tests: Ranker ──────────────────────────────────────────────────────

class TestRanker:
    def _make_features(self, n=20):
        from ml.models.ranker import RANKER_FEATURES
        data = {"movie_id": list(range(1, n+1))}
        for col in RANKER_FEATURES:
            data[col] = np.random.rand(n).tolist()
        return pd.DataFrame(data)

    def test_rank_fallback_no_model(self):
        from ml.models.ranker import Ranker
        ranker = Ranker()   # not trained
        feats  = self._make_features(10)
        ranked = ranker.rank(feats, n=5)
        assert len(ranked) == 5
        assert all(isinstance(mid, int) for mid, _ in ranked)

    def test_rank_order(self):
        """Ranker output should be sorted descending by score."""
        from ml.models.ranker import Ranker
        ranker = Ranker()
        feats  = self._make_features(20)
        ranked = ranker.rank(feats, n=10)
        scores = [s for _, s in ranked]
        assert scores == sorted(scores, reverse=True)


# ─── Integration Tests: API ───────────────────────────────────────────────────

@pytest.fixture(scope="module")
def client(seeded_db):
    """TestClient with overridden DB dependency."""
    app = create_app()

    def override_db():
        session = seeded_db()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as test_client:
        yield test_client


class TestAuthAPI:
    def test_register(self, client):
        resp = client.post("/auth/register", json={
            "username": "newuser_test",
            "email":    "newuser_test@example.com",
            "password": "securepass123",
        })
        assert resp.status_code == 201
        assert resp.json()["username"] == "newuser_test"

    def test_register_duplicate(self, client):
        payload = {"username": "dupuser", "email": "dup@example.com", "password": "pass12345"}
        client.post("/auth/register", json=payload)
        resp = client.post("/auth/register", json=payload)
        assert resp.status_code == 409

    def test_login_success(self, client):
        resp = client.post("/auth/login", json={"username": "testuser1", "password": "password123"})
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data

    def test_login_wrong_password(self, client):
        resp = client.post("/auth/login", json={"username": "testuser1", "password": "wrongpass"})
        assert resp.status_code == 401

    def test_me_authenticated(self, client):
        login = client.post("/auth/login", json={"username": "testuser1", "password": "password123"})
        token = login.json()["access_token"]
        resp  = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert resp.json()["username"] == "testuser1"

    def test_me_unauthenticated(self, client):
        resp = client.get("/auth/me")
        assert resp.status_code in (401, 403)   # HTTPBearer returns 403 when no token provided

    def test_refresh_token(self, client):
        login   = client.post("/auth/login", json={"username": "testuser1", "password": "password123"})
        refresh = login.json()["refresh_token"]
        resp    = client.post("/auth/refresh", json={"refresh_token": refresh})
        assert resp.status_code == 200
        assert "access_token" in resp.json()


class TestRatingsAPI:
    @pytest.fixture
    def auth_headers(self, client):
        r = client.post("/auth/login", json={"username": "testuser2", "password": "password123"})
        return {"Authorization": f"Bearer {r.json()['access_token']}"}

    def test_submit_rating(self, client, auth_headers):
        resp = client.post("/v1/ratings", json={"movie_id": 1, "rating": 4.5},
                           headers=auth_headers)
        assert resp.status_code == 201
        assert resp.json()["rating"] == 4.5

    def test_rating_rounds_to_half(self, client, auth_headers):
        resp = client.post("/v1/ratings", json={"movie_id": 2, "rating": 3.7},
                           headers=auth_headers)
        assert resp.status_code == 201
        assert resp.json()["rating"] == 3.5   # rounded to nearest 0.5

    def test_rating_update_reuses_existing_row(self, client, auth_headers):
        first = client.post("/v1/ratings", json={"movie_id": 3, "rating": 2.0},
                            headers=auth_headers)
        assert first.status_code == 201
        second = client.post("/v1/ratings", json={"movie_id": 3, "rating": 5.0},
                             headers=auth_headers)
        assert second.status_code == 201
        assert second.json()["rating_id"] == first.json()["rating_id"]
        assert second.json()["rating"] == 5.0

    def test_rating_out_of_range(self, client, auth_headers):
        resp = client.post("/v1/ratings", json={"movie_id": 1, "rating": 6.0},
                           headers=auth_headers)
        assert resp.status_code == 422

    def test_list_ratings(self, client, auth_headers):
        resp = client.get("/v1/ratings", headers=auth_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_rating_nonexistent_movie(self, client, auth_headers):
        resp = client.post("/v1/ratings", json={"movie_id": 99999, "rating": 3.0},
                           headers=auth_headers)
        assert resp.status_code == 404


class TestEventsAPI:
    @pytest.fixture
    def auth_headers(self, client):
        r = client.post("/auth/login", json={"username": "testuser3", "password": "password123"})
        return {"Authorization": f"Bearer {r.json()['access_token']}"}

    def test_log_event(self, client, auth_headers):
        resp = client.post("/v1/events",
                           json={"movie_id": 1, "event_type": "watch", "watch_pct": 75.0},
                           headers=auth_headers)
        assert resp.status_code == 201
        assert resp.json()["event_type"] == "watch"

    def test_invalid_event_type(self, client, auth_headers):
        resp = client.post("/v1/events",
                           json={"movie_id": 1, "event_type": "invalid_type"},
                           headers=auth_headers)
        assert resp.status_code == 422

    def test_list_events(self, client, auth_headers):
        resp = client.get("/v1/events", headers=auth_headers)
        assert resp.status_code == 200


class TestHealthAPI:
    def test_health(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_root(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        assert "text/html" in resp.headers.get("content-type", "")
        body = resp.text.lower()
        assert "<!doctype html>" in body
        assert '<script src="/static/js/app.js"></script>' in body


class TestRecommendationsAPI:
    """
    Recommendations endpoint returns 503 when models not loaded,
    which is expected in test environment without trained models.
    """
    @pytest.fixture
    def auth_headers(self, client):
        r = client.post("/auth/login", json={"username": "testuser1", "password": "password123"})
        return {"Authorization": f"Bearer {r.json()['access_token']}"}

    def test_recommendations_requires_auth(self, client):
        resp = client.get("/v1/recommendations")
        assert resp.status_code in (401, 403)

    def test_recommendations_invalid_strategy(self, client, auth_headers):
        resp = client.get("/v1/recommendations?strategy=invalid", headers=auth_headers)
        assert resp.status_code in (400, 503)   # 400 if validation fires before engine check

    def test_recommendations_n_validation(self, client, auth_headers):
        resp = client.get("/v1/recommendations?n=999", headers=auth_headers)
        assert resp.status_code == 422   # exceeds max

    def test_similar_requires_auth(self, client):
        resp = client.get("/v1/recommendations/similar/1")
        assert resp.status_code in (401, 403)

    def test_recommendations_keyerror_translated_to_404(self, client, auth_headers, monkeypatch):
        from api.routers import recommendations as rec_router

        class _FailingEngine:
            @staticmethod
            def recommend(**kwargs):
                raise KeyError("user_id 1 not in ALS model")

        monkeypatch.setattr(rec_router, "get_engine", lambda: _FailingEngine())
        resp = client.get("/v1/recommendations?strategy=hybrid", headers=auth_headers)
        assert resp.status_code == 404
        assert resp.json()["detail"]["code"] == "USER_NOT_IN_MODEL"
