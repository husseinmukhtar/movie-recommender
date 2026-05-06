# Code Quality and Stability Notes

## Error handling conventions

- ML layer raises domain exceptions for missing entities:
  - `ALSTrainer.recommend()` raises `KeyError` for unknown users.
  - `ALSTrainer.similar_items()` raises `KeyError` for unknown movies.
  - `ContentModel.similar_to_movie()` raises `KeyError` for unknown movies.
- API layer translates model errors into HTTP responses:
  - Recommendation `KeyError` is translated to `404` with structured JSON:
    - `{"detail": {"code": "USER_NOT_IN_MODEL", "message": "..."}}`
- Service-level fallback behavior remains unchanged:
  - cold-start paths in `HybridEngine` still return empty recommendations and allow
    fallback strategies such as `"popular"`.

## Test setup and DB lifecycle

- Test DB is an isolated SQLite file created under pytest `tmp_path_factory`.
- Schema is created once per session and dropped on teardown.
- API tests always use dependency override for `get_db`, so app endpoints use the
  isolated test session instead of runtime DB settings.
- `TestClient` is created with a context manager and cleanly closed to avoid
  leaked connections/file locks.

## Warning policy

- `pytest.ini` enforces warnings as errors (`-W error`) to prevent regressions.
- A single third-party pending deprecation warning from Starlette multipart import
  is explicitly filtered until upstream removes the deprecated import path.

## Non-obvious ALS behavior

- Unknown users are considered model misses, not empty-personalization cases.
- For direct ALS usage this is surfaced as `KeyError`.
- In API recommendation routes this is translated into a typed `404` response.
