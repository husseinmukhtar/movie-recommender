"""
data/seeds/seed_data.py
Generates synthetic but realistic seed data for development and testing.
Run: python -m data.seeds.seed_data
"""
import random
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from datetime import datetime, timedelta

from api.middleware.auth import hash_password
from data.database import init_db, db_session
from data.models import User, Movie, Rating, Event

GENRES = [
    "Action", "Adventure", "Animation", "Comedy", "Crime",
    "Documentary", "Drama", "Fantasy", "Horror", "Mystery",
    "Romance", "Sci-Fi", "Thriller", "Western", "Family",
]

SAMPLE_MOVIES = [
    ("The Shawshank Redemption", 1994, ["Drama"], 4.9),
    ("The Godfather", 1972, ["Crime", "Drama"], 4.8),
    ("The Dark Knight", 2008, ["Action", "Crime", "Drama"], 4.8),
    ("Schindler's List", 1993, ["Drama", "History"], 4.7),
    ("Pulp Fiction", 1994, ["Crime", "Drama"], 4.7),
    ("The Lord of the Rings: The Return of the King", 2003, ["Adventure", "Fantasy"], 4.7),
    ("Forrest Gump", 1994, ["Drama", "Romance"], 4.7),
    ("Inception", 2010, ["Sci-Fi", "Thriller"], 4.6),
    ("The Matrix", 1999, ["Sci-Fi", "Action"], 4.6),
    ("Goodfellas", 1990, ["Crime", "Drama"], 4.6),
    ("Interstellar", 2014, ["Sci-Fi", "Drama"], 4.6),
    ("Se7en", 1995, ["Crime", "Drama", "Mystery"], 4.5),
    ("The Silence of the Lambs", 1991, ["Crime", "Horror", "Thriller"], 4.5),
    ("Parasite", 2019, ["Drama", "Thriller"], 4.5),
    ("The Lion King", 1994, ["Animation", "Family"], 4.5),
    ("Gladiator", 2000, ["Action", "Adventure", "Drama"], 4.4),
    ("The Departed", 2006, ["Crime", "Drama", "Thriller"], 4.4),
    ("Avengers: Endgame", 2019, ["Action", "Adventure", "Sci-Fi"], 4.3),
    ("Joker", 2019, ["Crime", "Drama", "Thriller"], 4.3),
    ("1917", 2019, ["Drama", "Action"], 4.3),
    ("Knives Out", 2019, ["Crime", "Drama", "Mystery"], 4.3),
    ("Get Out", 2017, ["Horror", "Mystery", "Thriller"], 4.3),
    ("La La Land", 2016, ["Drama", "Romance"], 4.2),
    ("Whiplash", 2014, ["Drama"], 4.5),
    ("Mad Max: Fury Road", 2015, ["Action", "Adventure", "Sci-Fi"], 4.2),
    ("The Grand Budapest Hotel", 2014, ["Adventure", "Comedy", "Drama"], 4.2),
    ("Her", 2013, ["Drama", "Romance", "Sci-Fi"], 4.2),
    ("Coco", 2017, ["Animation", "Family", "Adventure"], 4.4),
    ("Spider-Man: Into the Spider-Verse", 2018, ["Animation", "Action"], 4.3),
    ("Everything Everywhere All at Once", 2022, ["Comedy", "Drama", "Sci-Fi"], 4.5),
]


def seed(n_users: int = 200, n_extra_movies: int = 70, n_ratings_per_user: int = 40):
    print("Initialising database …")
    init_db()

    with db_session() as db:
        # ── Movies ────────────────────────────────────────────────────────
        print("Seeding movies …")
        movies = []
        for title, year, genres, avg_r in SAMPLE_MOVIES:
            m = Movie(
                title=title,
                release_year=year,
                genres=genres,
                language="en",
                avg_rating=avg_r,
                rating_count=random.randint(1000, 50000),
                metadata_={
                    "director": random.choice(["Christopher Nolan", "Martin Scorsese",
                                               "Quentin Tarantino", "Steven Spielberg",
                                               "David Fincher", "Bong Joon-ho"]),
                    "cast": random.sample(["Tom Hanks", "Brad Pitt", "Leonardo DiCaprio",
                                           "Scarlett Johansson", "Meryl Streep",
                                           "Morgan Freeman", "Cate Blanchett"], 3),
                    "poster_url": f"https://image.tmdb.org/t/p/w500/placeholder_{year}.jpg",
                    "overview": f"A compelling {genres[0].lower()} film from {year}.",
                }
            )
            db.add(m)
            movies.append(m)

        # Extra random movies for breadth
        for i in range(n_extra_movies):
            genres = random.sample(GENRES, random.randint(1, 3))
            year = random.randint(1980, 2024)
            m = Movie(
                title=f"Movie {i + len(SAMPLE_MOVIES) + 1}",
                release_year=year,
                genres=genres,
                language=random.choice(["en", "fr", "es", "de", "ko", "ja"]),
                avg_rating=round(random.uniform(2.5, 4.8), 1),
                rating_count=random.randint(10, 5000),
                metadata_={"director": "Various", "cast": [], "overview": ""},
            )
            db.add(m)
            movies.append(m)

        db.flush()  # get IDs
        print(f"  {len(movies)} movies created")

        # ── Users ─────────────────────────────────────────────────────────
        print("Seeding users …")
        users = []
        for i in range(n_users):
            genre_weights = {g: round(random.random(), 2) for g in random.sample(GENRES, 5)}
            u = User(
                username=f"user_{i+1:04d}",
                email=f"user_{i+1:04d}@example.com",
                hashed_pw=hash_password("pass1234"),
                preferences={"genre_weights": genre_weights, "language_pref": "en"},
                created_at=datetime.utcnow() - timedelta(days=random.randint(1, 730)),
                last_active=datetime.utcnow() - timedelta(hours=random.randint(0, 720)),
            )
            db.add(u)
            users.append(u)

        db.flush()
        print(f"  {len(users)} users created")

        # ── Ratings ───────────────────────────────────────────────────────
        print("Seeding ratings …")
        n_ratings = 0
        seen = set()
        for user in users:
            # Each user rates a random subset of movies
            user_movies = random.sample(movies, min(n_ratings_per_user, len(movies)))
            for movie in user_movies:
                key = (user.user_id, movie.movie_id)
                if key in seen:
                    continue
                seen.add(key)
                # Bias rating toward movie's avg_rating ± 1
                rating_val = min(5.0, max(0.5, round(
                    random.gauss(movie.avg_rating, 0.8) * 2) / 2))
                r = Rating(
                    user_id=user.user_id,
                    movie_id=movie.movie_id,
                    rating=rating_val,
                    rated_at=datetime.utcnow() - timedelta(days=random.randint(0, 365)),
                )
                db.add(r)
                n_ratings += 1

        print(f"  {n_ratings} ratings created")

        # ── Events ────────────────────────────────────────────────────────
        print("Seeding events …")
        event_types = ["click", "watch", "skip", "bookmark"]
        n_events = 0
        for user in users:
            event_movies = random.sample(movies, min(60, len(movies)))
            for movie in event_movies:
                etype = random.choice(event_types)
                watch_pct = round(random.uniform(5, 100), 1) if etype == "watch" else None
                e = Event(
                    user_id=user.user_id,
                    movie_id=movie.movie_id,
                    event_type=etype,
                    watch_pct=watch_pct,
                    occurred_at=datetime.utcnow() - timedelta(days=random.randint(0, 180)),
                )
                db.add(e)
                n_events += 1

        print(f"  {n_events} events created")

    print("\nSeed complete!")
    print(f"  Movies : {len(movies)}")
    print(f"  Users  : {n_users}")
    print(f"  Ratings: {n_ratings}")
    print(f"  Events : {n_events}")


if __name__ == "__main__":
    seed()
