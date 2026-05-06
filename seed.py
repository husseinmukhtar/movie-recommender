import random
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import bcrypt

from data.models import Base, User, Movie, Rating, Event


def main():
    print("Connecting to SQLite database (recommender.db)...")
    engine = create_engine('sqlite:///recommender.db')
    
    # Create all tables cleanly
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    
    Session = sessionmaker(bind=engine)
    with Session() as db:
        
        print("Creating 50 users...")
        users = []
        salt = bcrypt.gensalt()
        hashed_pw = bcrypt.hashpw(b'pass1234', salt).decode('utf-8')
        for i in range(1, 51):
            user = User(
                username=f'user_{i}',
                email=f'user_{i}@example.com',
                hashed_pw=hashed_pw,
                is_active=True
            )
            users.append(user)
        
        db.add_all(users)
        db.commit()

        print("Creating 30 movies...")
        movies = []
        for i in range(1, 31):
            movie = Movie(
                title=f'Movie {i}',
                release_year=random.randint(1990, 2023),
                genres=['Action', 'Drama'] if i % 2 == 0 else ['Comedy'],
                language='en',
                metadata_={'director': 'Various', 'cast': [], 'overview': ''}
            )
            movies.append(movie)

        db.add_all(movies)
        db.commit()

        print("Creating random ratings and events...")
        ratings = []
        events = []
        
        for u in users:
            # Each user interacts with 10 random movies
            interacted_movies = random.sample(movies, k=10)
            for m in interacted_movies:
                r = Rating(
                    user_id=u.user_id,
                    movie_id=m.movie_id,
                    rating=random.uniform(0.5, 5.0)
                )
                ratings.append(r)
                
                e = Event(
                    user_id=u.user_id,
                    movie_id=m.movie_id,
                    event_type='watch',
                    watch_pct=random.uniform(10.0, 100.0)
                )
                events.append(e)

        db.add_all(ratings)
        db.add_all(events)
        db.commit()
        
        print(f"Success! Seeded {len(users)} users, {len(movies)} movies, {len(ratings)} ratings, and {len(events)} events.")


if __name__ == '__main__':
    main()
