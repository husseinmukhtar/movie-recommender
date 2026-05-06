"""Update synthetic movies with real titles and TMDB poster paths."""
import sqlite3, json

MOVIES = [
    (1,  "The Shawshank Redemption", 1994, ["Drama"],                          "/q6y0Go1tsGEsmtFryDOJo3dEmqu.jpg"),
    (2,  "The Godfather",            1972, ["Crime", "Drama"],                  "/3bhkrj58Vtu7enYsLegHzgMKBpA.jpg"),
    (3,  "The Dark Knight",          2008, ["Action", "Crime", "Drama"],        "/qJ2tW6WMUDux911r6m7haRef0WH.jpg"),
    (4,  "Pulp Fiction",             1994, ["Crime", "Drama"],                  "/d5iIlFn5s0ImszYzBPb8JPIfbXD.jpg"),
    (5,  "Schindler's List",         1993, ["Drama", "History", "War"],         "/sF1U4EUQS8YHUYjNl3pMGNIQyr0.jpg"),
    (6,  "The Lord of the Rings: The Return of the King", 2003, ["Fantasy", "Adventure"], "/rCzpDGLbOoPwLjy3OAm5NUPOTrC.jpg"),
    (7,  "Forrest Gump",             1994, ["Comedy", "Drama", "Romance"],      "/arw2vcBveWOVZr6pxd9XTd1TdQa.jpg"),
    (8,  "Inception",                2010, ["Action", "Science Fiction"],       "/9gk7adHYeDvHkCSEqAvQNLV5Uge.jpg"),
    (9,  "The Matrix",               1999, ["Action", "Science Fiction"],       "/f89U3ADr1oiB1s9GkdPOEpXUk5H.jpg"),
    (10, "Goodfellas",               1990, ["Drama", "Crime"],                  "/aKuFiU82s5ISJpGZp7YkIr3kCUd.jpg"),
    (11, "Fight Club",               1999, ["Drama", "Thriller"],               "/pB8BM7pdSp6B6Ih7QZ4DrQ3PmJK.jpg"),
    (12, "The Silence of the Lambs", 1991, ["Crime", "Drama", "Thriller"],      "/uS9m8OBk1A8eM9I042bx8XXpqAq.jpg"),
    (13, "The Lord of the Rings: The Fellowship of the Ring", 2001, ["Fantasy", "Adventure"], "/6oom5QYQ2yQTMJIbnvbkBL9cHo6.jpg"),
    (14, "Interstellar",             2014, ["Drama", "Science Fiction"],        "/gEU2QniE6E77NI6lCU6MxlNBvIx.jpg"),
    (15, "The Green Mile",           1999, ["Fantasy", "Drama", "Crime"],       "/velWPhVMQeQKcxggNEU8YmIo52R.jpg"),
    (16, "Saving Private Ryan",      1998, ["Drama", "History", "War"],         "/uqx37cS8cpHg8U35f9U5IBlrCV3.jpg"),
    (17, "The Usual Suspects",       1995, ["Drama", "Crime", "Mystery"],       "/bWE2MxrKKsmr8vGzknEFU5MIK61.jpg"),
    (18, "Spirited Away",            2001, ["Animation", "Family", "Fantasy"],  "/39wmItIWsg5sZMyRUHLkWBcuVCM.jpg"),
    (19, "Parasite",                 2019, ["Comedy", "Drama", "Thriller"],     "/7IiTTgloJzvGI1TAYymCfbfl3vT.jpg"),
    (20, "Whiplash",                 2014, ["Drama", "Music"],                  "/7fn624j5lj3xTme2SgiLCeuedmO.jpg"),
    (21, "The Prestige",             2006, ["Drama", "Mystery", "Science Fiction"], "/bdN3gXuIZYaJP4oMbHlzUBd6jNn.jpg"),
    (22, "The Lion King",            1994, ["Animation", "Family", "Drama"],    "/sKCr78MXSuC3wAA4c9HPiOhb4GX.jpg"),
    (23, "Gladiator",                2000, ["Action", "Drama", "Adventure"],    "/ty8TGRuvJLPUmAR1H1nRIsgwvim.jpg"),
    (24, "The Departed",             2006, ["Drama", "Thriller", "Crime"],      "/nT97ifVT2J1yMQmeq20Qblg61T.jpg"),
    (25, "Avengers: Endgame",        2019, ["Action", "Adventure", "Science Fiction"], "/or06FN3Dka5tukK1e9sl16pB3iy.jpg"),
    (26, "The Lord of the Rings: The Two Towers", 2002, ["Fantasy", "Adventure"], "/5VTN0pR8gcqV3EPUHHfMGnJYi9L.jpg"),
    (27, "Back to the Future",       1985, ["Adventure", "Comedy", "Science Fiction"], "/fNOH9f1aA7XRTzl1sAOx9iF553Q.jpg"),
    (28, "Django Unchained",         2012, ["Drama", "Western"],               "/7oWY8VDWW7thTzWh3OKYRkWcKBl.jpg"),
    (29, "The Wolf of Wall Street",  2013, ["Crime", "Drama", "Comedy"],        "/34m2tygAYBGqA9MXKhRDtzOd4Th.jpg"),
    (30, "Toy Story",                1995, ["Animation", "Comedy", "Family"],   "/uXDfjJbdP4ijW5hWSBrPl9KcertP.jpg"),
]

conn = sqlite3.connect("recommender.db")
cur  = conn.cursor()

for movie_id, title, year, genres, poster_path in MOVIES:
    cur.execute(
        "UPDATE movies SET title=?, release_year=?, genres=?, metadata=? WHERE movie_id=?",
        (title, year, json.dumps(genres), json.dumps({"poster_url": poster_path}), movie_id),
    )
    print(f"  {movie_id:2d}. {title}")

conn.commit()
conn.close()
print("Done.")
