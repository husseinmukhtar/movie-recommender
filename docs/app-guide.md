# Movie Recommender App Guide

## Run The App

1. Create and activate a Python environment.
2. Install dependencies with `pip install -r requirements.txt`.
3. Seed or train data as needed for your local workflow.
4. Start the API and static frontend:

```bash
uvicorn api.main:app --host 127.0.0.1 --port 8000
```

5. Open `http://127.0.0.1:8000/`.

## Recommendation Flow

- Users authenticate with `/auth/login`.
- The dashboard requests `/v1/recommendations?n=20` using the bearer token.
- The backend returns recommendation items with fields such as `movie_id`, `title`, `genres`, `release_year`, `score`, `strategy`, and `explanation`.
- The frontend maps those fields into a Netflix-style grid. If a real poster URL is unavailable, the UI generates a poster-like SVG fallback with the movie title.
- Clicking a card opens an in-page details modal; no movie detail route is required.

## Ratings Flow

- On dashboard load, the UI calls `GET /v1/ratings` and prefills any existing user ratings.
- Clicking a star updates the UI optimistically and sends `POST /v1/ratings` with `{ "movie_id": number, "rating": number }`.
- The backend upserts the rating in the `ratings` table, so rating the same movie again updates the existing row.
- The UI stores a local copy in `localStorage` as a fallback and refresh aid.
- Success and failure messages appear as toast notifications.

## UX States

- Loading: skeleton movie cards.
- Empty: "No recommendations available".
- Error: retry button.
- Missing image: generated fallback poster.
- Saved rating: gold stars and success toast.

## Screenshots

Add screenshots here before publishing the portfolio:

- Auth screen
- Recommendation dashboard
- Movie details modal
- Mobile layout
