import React, { useEffect, useMemo, useState } from "react";

const ENDPOINT = "/v1/recommendations?n=10";
const TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p/w500";

function escapeSvgText(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function splitTitle(value, maxChars = 18, maxLines = 3) {
  const words = String(value || "Untitled movie").split(/\s+/).filter(Boolean);
  const lines = [];
  let current = "";

  words.forEach((word) => {
    const next = current ? `${current} ${word}` : word;
    if (next.length > maxChars && current) {
      lines.push(current);
      current = word;
    } else {
      current = next;
    }
  });

  if (current) lines.push(current);
  return lines.slice(0, maxLines);
}

function makeFallbackPoster(movie) {
  const title = movie?.title || "Untitled movie";
  const genres = Array.isArray(movie?.genres) && movie.genres.length ? movie.genres : ["Unknown genre"];
  const seed = Array.from(title).reduce((sum, char) => sum + char.charCodeAt(0), 0);
  const hue = seed % 360;
  const hue2 = (hue + 48) % 360;
  const titleLines = splitTitle(title)
    .map((line, index) => (
      `<tspan x="150" dy="${index === 0 ? 0 : 34}">${escapeSvgText(line)}</tspan>`
    ))
    .join("");

  const svg = `
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 300 450">
      <defs>
        <linearGradient id="bg" x1="0" x2="1" y1="0" y2="1">
          <stop offset="0" stop-color="hsl(${hue}, 68%, 22%)"/>
          <stop offset="0.58" stop-color="#171923"/>
          <stop offset="1" stop-color="hsl(${hue2}, 72%, 34%)"/>
        </linearGradient>
      </defs>
      <rect width="300" height="450" fill="url(#bg)"/>
      <rect x="22" y="22" width="256" height="406" rx="16" fill="rgba(0,0,0,0.28)" stroke="rgba(255,255,255,0.22)"/>
      <text x="150" y="72" text-anchor="middle" fill="#facc15" font-family="Arial, sans-serif" font-size="16" font-weight="700">${escapeSvgText(genres[0])}</text>
      <circle cx="150" cy="138" r="42" fill="none" stroke="rgba(255,255,255,0.72)" stroke-width="8"/>
      <polygon points="142,118 142,158 175,138" fill="#facc15"/>
      <text x="150" y="238" text-anchor="middle" fill="#ffffff" font-family="Arial, sans-serif" font-size="25" font-weight="700">${titleLines}</text>
      <text x="150" y="384" text-anchor="middle" fill="rgba(255,255,255,0.7)" font-family="Arial, sans-serif" font-size="13" font-weight="700">RECOMMENDED</text>
    </svg>
  `;

  return `data:image/svg+xml;charset=UTF-8,${encodeURIComponent(svg)}`;
}

function getMovieId(movie) {
  return movie?.movie_id ?? movie?.id ?? movie?.tmdb_id ?? movie?.imdb_id ?? movie?.title;
}

function getPosterUrl(movie) {
  const raw = movie?.poster_url || movie?.image_url || movie?.poster_path || movie?.poster;

  if (!raw) return makeFallbackPoster(movie);
  if (/^https?:\/\//i.test(raw) || raw.startsWith("data:")) return raw;
  if (raw.startsWith("/static/") || raw.startsWith("./") || raw.startsWith("../")) return raw;
  if (raw.startsWith("/")) return `${TMDB_IMAGE_BASE}${raw}`;
  return raw;
}

function getGenres(movie) {
  return Array.isArray(movie?.genres) && movie.genres.length ? movie.genres : ["Unknown genre"];
}

function StarRating({ movie, rating, hoverRating, onHover, onLeave, onRate }) {
  return (
    <div className="rec-rating" role="group" aria-label={`Rate ${movie.title || "movie"}`}>
      {[1, 2, 3, 4, 5].map((value) => {
        const filled = value <= (hoverRating || rating || 0);
        return (
          <button
            key={value}
            type="button"
            className={`rec-star ${filled ? "is-active" : ""}`}
            aria-label={`Rate ${movie.title || "movie"} ${value} out of 5`}
            onMouseEnter={(event) => {
              event.stopPropagation();
              onHover(value);
            }}
            onFocus={(event) => {
              event.stopPropagation();
              onHover(value);
            }}
            onMouseLeave={(event) => {
              event.stopPropagation();
              onLeave();
            }}
            onBlur={onLeave}
            onClick={(event) => {
              event.preventDefault();
              event.stopPropagation();
              onRate(value);
            }}
          >
            &#9733;
          </button>
        );
      })}
    </div>
  );
}

export default function RecommendationsGrid() {
  const [movies, setMovies] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [selectedMovie, setSelectedMovie] = useState(null);
  const [ratings, setRatings] = useState({});
  const [hoverRatings, setHoverRatings] = useState({});
  const [failedImages, setFailedImages] = useState({});

  async function loadRecommendations() {
    setLoading(true);
    setError("");

    try {
      const token = localStorage.getItem("access_token");
      const response = await fetch(ENDPOINT, {
        headers: token ? { Authorization: `Bearer ${token}` } : undefined,
      });

      if (!response.ok) {
        throw new Error(`Recommendations request failed: ${response.status}`);
      }

      const data = await response.json();
      const recommendations = Array.isArray(data?.recommendations) ? data.recommendations : [];
      if (recommendations[0]) {
        console.log("[recommendations] sample movie", recommendations[0]);
      }
      setMovies(recommendations);
    } catch (err) {
      console.error(err);
      setError("Unable to load recommendations.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadRecommendations();
  }, []);

  const modalPoster = useMemo(
    () => (selectedMovie ? getPosterUrl(selectedMovie) : ""),
    [selectedMovie],
  );

  if (loading) {
    return (
      <section className="rec-shell">
        <div className="rec-grid" aria-busy="true">
          {Array.from({ length: 10 }).map((_, index) => (
            <div className="rec-skeleton" key={index} />
          ))}
        </div>
        <RecommendationsStyles />
      </section>
    );
  }

  if (error) {
    return (
      <section className="rec-shell">
        <div className="rec-state">
          <p>{error}</p>
          <button type="button" className="rec-retry" onClick={loadRecommendations}>
            Retry
          </button>
        </div>
        <RecommendationsStyles />
      </section>
    );
  }

  if (movies.length === 0) {
    return (
      <section className="rec-shell">
        <div className="rec-state">No recommendations available</div>
        <RecommendationsStyles />
      </section>
    );
  }

  return (
    <section className="rec-shell">
      <div className="rec-grid">
        {movies.map((movie) => {
          const movieId = getMovieId(movie);
          const genres = getGenres(movie);
          const poster = failedImages[movieId] ? makeFallbackPoster(movie) : getPosterUrl(movie);
          const description = movie?.description || movie?.overview || movie?.explanation || "Recommended for your current taste profile.";

          return (
            <article
              key={movieId}
              className="rec-card"
              role="button"
              tabIndex={0}
              onClick={() => setSelectedMovie(movie)}
              onKeyDown={(event) => {
                if (event.key === "Enter" || event.key === " ") {
                  event.preventDefault();
                  setSelectedMovie(movie);
                }
              }}
            >
              <img
                className="rec-poster"
                src={poster}
                alt={`${movie?.title || "Movie"} poster`}
                loading="lazy"
                onError={() => {
                  setFailedImages((current) => ({ ...current, [movieId]: true }));
                }}
              />
              <div className="rec-body">
                <div>
                  <h3>{movie?.title || "Untitled movie"}</h3>
                  <p className="rec-meta">{genres.slice(0, 2).join(", ")}</p>
                  <p className="rec-description">{description}</p>
                </div>
                <StarRating
                  movie={movie}
                  rating={ratings[movieId] || 0}
                  hoverRating={hoverRatings[movieId] || 0}
                  onHover={(value) => setHoverRatings((current) => ({ ...current, [movieId]: value }))}
                  onLeave={() => setHoverRatings((current) => ({ ...current, [movieId]: 0 }))}
                  onRate={(value) => setRatings((current) => ({ ...current, [movieId]: value }))}
                />
              </div>
            </article>
          );
        })}
      </div>

      {selectedMovie && (
        <div className="rec-modal" role="dialog" aria-modal="true" aria-labelledby="rec-modal-title">
          <button type="button" className="rec-backdrop" aria-label="Close details" onClick={() => setSelectedMovie(null)} />
          <div className="rec-modal-panel">
            <button type="button" className="rec-close" aria-label="Close details" onClick={() => setSelectedMovie(null)}>
              &times;
            </button>
            <img
              className="rec-modal-poster"
              src={modalPoster}
              alt={`${selectedMovie?.title || "Movie"} poster`}
              onError={(event) => {
                event.currentTarget.src = makeFallbackPoster(selectedMovie);
              }}
            />
            <div>
              <p className="rec-kicker">{getGenres(selectedMovie).join(", ")}</p>
              <h2 id="rec-modal-title">{selectedMovie?.title || "Untitled movie"}</h2>
              <p className="rec-modal-copy">
                {selectedMovie?.description || selectedMovie?.overview || selectedMovie?.explanation || "Recommended for your current taste profile."}
              </p>
            </div>
          </div>
        </div>
      )}

      <RecommendationsStyles />
    </section>
  );
}

function RecommendationsStyles() {
  return (
    <style>{`
      .rec-shell {
        width: 100%;
        padding: 24px 0;
        color: #fff;
      }

      .rec-grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(190px, 1fr));
        gap: 22px;
      }

      .rec-card {
        min-height: 100%;
        overflow: hidden;
        border: 1px solid rgba(255,255,255,0.12);
        border-radius: 10px;
        background: #141414;
        cursor: pointer;
        transition: transform 180ms ease, box-shadow 180ms ease, border-color 180ms ease;
      }

      .rec-card:hover,
      .rec-card:focus-visible {
        transform: scale(1.035);
        border-color: rgba(250,204,21,0.42);
        box-shadow: 0 18px 45px rgba(0,0,0,0.55);
        outline: none;
      }

      .rec-poster {
        display: block;
        width: 100%;
        aspect-ratio: 2 / 3;
        object-fit: cover;
        background: #202020;
      }

      .rec-body {
        min-height: 190px;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        gap: 14px;
        padding: 14px;
      }

      .rec-body h3 {
        margin: 0 0 6px;
        font-size: 16px;
        line-height: 1.25;
      }

      .rec-meta,
      .rec-description,
      .rec-kicker,
      .rec-modal-copy {
        color: #a3a3a3;
      }

      .rec-meta {
        margin: 0 0 10px;
        font-size: 13px;
      }

      .rec-description {
        display: -webkit-box;
        margin: 0;
        overflow: hidden;
        -webkit-line-clamp: 3;
        -webkit-box-orient: vertical;
        font-size: 13px;
        line-height: 1.45;
      }

      .rec-rating {
        display: flex;
        gap: 2px;
      }

      .rec-star {
        width: 28px;
        height: 28px;
        border: 0;
        border-radius: 999px;
        background: transparent;
        color: #9ca3af;
        cursor: pointer;
        font-size: 20px;
        line-height: 1;
        transition: transform 140ms ease, color 140ms ease, background 140ms ease;
      }

      .rec-star:hover,
      .rec-star:focus-visible,
      .rec-star.is-active {
        color: #facc15;
        background: rgba(250,204,21,0.12);
      }

      .rec-star:hover,
      .rec-star:focus-visible {
        transform: scale(1.12);
        outline: none;
      }

      .rec-modal {
        position: fixed;
        inset: 0;
        z-index: 1000;
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 24px;
      }

      .rec-backdrop {
        position: absolute;
        inset: 0;
        border: 0;
        background: rgba(0,0,0,0.72);
        cursor: pointer;
      }

      .rec-modal-panel {
        position: relative;
        z-index: 1;
        display: grid;
        grid-template-columns: minmax(150px, 230px) minmax(0, 1fr);
        gap: 22px;
        width: min(780px, 100%);
        max-height: 88vh;
        overflow: auto;
        border-radius: 12px;
        border: 1px solid rgba(255,255,255,0.16);
        background: #181818;
        padding: 22px;
        box-shadow: 0 28px 80px rgba(0,0,0,0.68);
      }

      .rec-close {
        position: absolute;
        top: 12px;
        right: 12px;
        width: 36px;
        height: 36px;
        border: 1px solid rgba(255,255,255,0.16);
        border-radius: 999px;
        background: rgba(0,0,0,0.45);
        color: #fff;
        cursor: pointer;
        font-size: 24px;
        line-height: 1;
      }

      .rec-modal-poster {
        width: 100%;
        aspect-ratio: 2 / 3;
        border-radius: 8px;
        object-fit: cover;
        background: #202020;
      }

      .rec-kicker {
        margin: 0 0 10px;
        color: #facc15;
        font-size: 13px;
        font-weight: 700;
        text-transform: uppercase;
      }

      .rec-modal-panel h2 {
        margin: 0 0 12px;
        font-size: 32px;
        line-height: 1.1;
      }

      .rec-modal-copy {
        margin: 0;
        line-height: 1.65;
      }

      .rec-state {
        min-height: 260px;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        gap: 14px;
        color: #d4d4d4;
        text-align: center;
      }

      .rec-retry {
        border: 1px solid #facc15;
        border-radius: 999px;
        background: transparent;
        color: #facc15;
        cursor: pointer;
        padding: 10px 18px;
        font-weight: 700;
      }

      .rec-skeleton {
        aspect-ratio: 2 / 3.95;
        border-radius: 10px;
        background: linear-gradient(90deg, #181818, #252525, #181818);
        animation: rec-pulse 1.4s infinite ease-in-out;
      }

      @keyframes rec-pulse {
        0%, 100% { opacity: 0.5; }
        50% { opacity: 1; }
      }

      @media (max-width: 640px) {
        .rec-grid {
          grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
          gap: 16px;
        }

        .rec-modal-panel {
          grid-template-columns: 1fr;
        }

        .rec-modal-poster {
          max-width: 220px;
        }
      }
    `}</style>
  );
}
