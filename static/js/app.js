document.addEventListener('DOMContentLoaded', () => {
    const authView = document.getElementById('auth-view');
    const dashboardView = document.getElementById('dashboard-view');
    const authForm = document.getElementById('auth-form');
    const authError = document.getElementById('auth-error');
    const logoutBtn = document.getElementById('logout-btn');
    const welcomeMsg = document.getElementById('welcome-msg');
    const moviesContainer = document.getElementById('movies-container');
    const loader = document.getElementById('loader');
    const movieModal = document.getElementById('movie-modal');
    const modalBackdrop = document.getElementById('modal-backdrop');
    const modalClose = document.getElementById('modal-close');
    const modalPoster = document.getElementById('modal-poster');
    const modalTitle = document.getElementById('modal-title');
    const modalKicker = document.getElementById('modal-kicker');
    const modalMeta = document.getElementById('modal-meta');
    const modalRating = document.getElementById('modal-rating');
    const modalExplanation = document.getElementById('modal-explanation');
    const reviewTextarea   = document.getElementById('review-textarea');
    const reviewCharCount  = document.getElementById('review-char-count');
    const reviewSubmitBtn  = document.getElementById('review-submit-btn');
    const toast = document.getElementById('toast');
    const placeholderPosterUrl = '/static/img/poster-placeholder.svg';
    let ratingState = loadStoredRatings();
    let activeMovie = null;
    let toastTimer = null;

    // Check if already logged in
    const token = localStorage.getItem('access_token');
    if (token) {
        showDashboard();
    }

    const loginBtn = document.getElementById('login-btn');
    const registerBtn = document.getElementById('register-btn');

    loginBtn.addEventListener('click', async (e) => {
        e.preventDefault();
        const usernameInput = document.getElementById('username').value;
        const passwordInput = document.getElementById('password').value;
        
        if (!usernameInput || !passwordInput) {
            authError.textContent = 'Username and password are required.';
            return;
        }
        
        authError.textContent = '';

        try {
            // Attempt login
            const response = await fetch('/auth/login', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    username: usernameInput,
                    password: passwordInput
                })
            });

            if (response.ok) {
                const data = await response.json();
                localStorage.setItem('access_token', data.access_token);
                localStorage.setItem('username', usernameInput);
                showDashboard();
            } else {
                const errorData = await response.json();
                authError.textContent = errorData.detail || 'Authentication failed.';
            }
        } catch (err) {
            authError.textContent = 'Server error. Please try again later.';
        }
    });

    registerBtn.addEventListener('click', async (e) => {
        e.preventDefault();
        const usernameInput = document.getElementById('username').value;
        const passwordInput = document.getElementById('password').value;
        
        if (!usernameInput || !passwordInput) {
            authError.textContent = 'Username and password are required.';
            return;
        }

        if (usernameInput.length < 3) {
            authError.textContent = 'Username must be at least 3 characters.';
            return;
        }

        if (passwordInput.length < 8) {
            authError.textContent = 'Password must be at least 8 characters.';
            return;
        }

        authError.textContent = '';

        try {
            const regResponse = await fetch('/auth/register', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    username: usernameInput,
                    email: `${usernameInput}@example.com`,
                    password: passwordInput
                })
            });

            if (regResponse.ok) {
                loginBtn.click();
            } else {
                const errorData = await regResponse.json();
                const detail = errorData.detail;
                authError.textContent = Array.isArray(detail)
                    ? (detail[0]?.msg || 'Registration failed.')
                    : (detail || 'Registration failed.');
            }
        } catch (err) {
            authError.textContent = 'Server error. Please try again later.';
        }
    });

    logoutBtn.addEventListener('click', () => {
        localStorage.removeItem('access_token');
        localStorage.removeItem('username');
        authView.classList.add('active');
        dashboardView.classList.remove('active');
        moviesContainer.innerHTML = '';
        moviesContainer.classList.add('hidden');
        loader.classList.remove('hidden');
    });

    modalBackdrop.addEventListener('click', closeMovieDetails);
    modalClose.addEventListener('click', closeMovieDetails);
    document.addEventListener('keydown', event => {
        if (event.key === 'Escape' && !movieModal.classList.contains('hidden')) {
            closeMovieDetails();
        }
    });

    async function showDashboard() {
        authView.classList.remove('active');
        dashboardView.classList.add('active');
        const username = localStorage.getItem('username') || 'User';
        welcomeMsg.textContent = `Welcome, ${username}`;
        ratingState = loadStoredRatings();
        await loadRatings();
        
        await loadRecommendations();
    }

    async function loadRatings() {
        const token = localStorage.getItem('access_token');
        if (!token) {
            return;
        }

        try {
            const response = await fetch('/v1/ratings', {
                headers: {
                    'Authorization': `Bearer ${token}`,
                },
            });

            if (!response.ok) {
                return;
            }

            const ratings = await response.json();
            ratings.forEach(item => {
                ratingState[item.movie_id] = item.rating;
            });
            saveStoredRatings();
        } catch (err) {
            console.warn('Could not prefill ratings', err);
        }
    }

    async function loadRecommendations() {
        const token = localStorage.getItem('access_token');
        loader.classList.remove('hidden');
        moviesContainer.classList.add('hidden');
        moviesContainer.innerHTML = '';

        try {
            const response = await fetch('/v1/recommendations?n=20', {
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });

            if (response.ok) {
                const data = await response.json();
                console.debug('[recommendations] response', data);
                if (data.recommendations?.[0]) {
                    console.debug('[recommendations] sample movie', data.recommendations[0]);
                }
                renderMovies(data.recommendations || []);
            } else {
                if(response.status === 401) {
                    logoutBtn.click(); // Token expired
                } else {
                    console.error('Failed to load recommendations');
                    renderRecommendationsError();
                }
            }
        } catch (err) {
            console.error(err);
            renderRecommendationsError();
        }
    }

    function escapeHtml(value) {
        return String(value ?? '').replace(/[&<>"']/g, char => ({
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#39;',
        }[char]));
    }

    function svgTextLines(value, maxChars = 18, maxLines = 3) {
        const words = String(value || 'Untitled movie').split(/\s+/).filter(Boolean);
        const lines = [];
        let currentLine = '';

        words.forEach(word => {
            const testLine = currentLine ? `${currentLine} ${word}` : word;
            if (testLine.length > maxChars && currentLine) {
                lines.push(currentLine);
                currentLine = word;
            } else {
                currentLine = testLine;
            }
        });

        if (currentLine) {
            lines.push(currentLine);
        }

        return lines.slice(0, maxLines);
    }

    function generatedPoster(movie) {
        const title = movie?.title || 'Untitled movie';
        const hueSeed = Array.from(title).reduce((sum, char) => sum + char.charCodeAt(0), 0);
        const hue = hueSeed % 360;
        const secondaryHue = (hue + 42) % 360;
        const titleLines = svgTextLines(title);
        const titleMarkup = titleLines.map((line, index) => (
            `<tspan x="150" dy="${index === 0 ? 0 : 34}">${escapeHtml(line)}</tspan>`
        )).join('');
        const svg = `
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 300 450">
                <defs>
                    <linearGradient id="bg" x1="0" x2="1" y1="0" y2="1">
                        <stop offset="0" stop-color="hsl(${hue}, 66%, 22%)"/>
                        <stop offset="0.56" stop-color="#1f2833"/>
                        <stop offset="1" stop-color="hsl(${secondaryHue}, 70%, 36%)"/>
                    </linearGradient>
                </defs>
                <rect width="300" height="450" fill="url(#bg)"/>
                <rect x="22" y="22" width="256" height="406" rx="14" fill="rgba(11,12,16,0.32)" stroke="rgba(255,255,255,0.22)"/>
                <circle cx="150" cy="120" r="42" fill="none" stroke="rgba(255,255,255,0.78)" stroke-width="8"/>
                <polygon points="142,100 142,140 174,120" fill="#66fcf1"/>
                <text x="150" y="220" text-anchor="middle" fill="#ffffff" font-family="Arial, sans-serif" font-size="25" font-weight="700">${titleMarkup}</text>
                <text x="150" y="374" text-anchor="middle" fill="rgba(255,255,255,0.72)" font-family="Arial, sans-serif" font-size="13" font-weight="700">NEXUS.AI PICK</text>
            </svg>
        `;

        return `data:image/svg+xml;charset=UTF-8,${encodeURIComponent(svg)}`;
    }

    function resolvePosterUrl(movie) {
        const rawUrl = movie?.poster_url
            || movie?.image_url
            || movie?.poster
            || movie?.posterPath
            || movie?.poster_path
            || movie?.tmdb_poster_path;

        if (!rawUrl) {
            return generatedPoster(movie);
        }

        if (/^https?:\/\//i.test(rawUrl) || rawUrl.startsWith('data:')) {
            return rawUrl;
        }

        if (rawUrl.startsWith('/static/') || rawUrl.startsWith('./') || rawUrl.startsWith('../')) {
            return rawUrl;
        }

        if (rawUrl.startsWith('/')) {
            return `https://image.tmdb.org/t/p/w500${rawUrl}`;
        }

        return rawUrl;
    }

    function getMovieId(movie) {
        return movie?.movie_id || movie?.id || movie?.tmdb_id || movie?.imdb_id || '';
    }

    function ratingStorageKey() {
        return `movie_ratings:${localStorage.getItem('username') || 'anonymous'}`;
    }

    function loadStoredRatings() {
        try {
            return JSON.parse(localStorage.getItem(ratingStorageKey()) || '{}');
        } catch (err) {
            console.warn('Could not load stored ratings', err);
            return {};
        }
    }

    function saveStoredRatings() {
        localStorage.setItem(ratingStorageKey(), JSON.stringify(ratingState));
    }

    function formatScore(score) {
        if (!Number.isFinite(score)) {
            return 'Score N/A';
        }

        if (score >= 0 && score <= 1) {
            return `${Math.round(score * 100)}% Match`;
        }

        return `Score ${score.toFixed(2)}`;
    }

    function openMovieDetails(movie) {
        activeMovie = movie;
        const title = movie.title || 'Untitled movie';
        const genres = Array.isArray(movie.genres) && movie.genres.length > 0 ? movie.genres : ['Unknown genre'];
        const posterUrl = resolvePosterUrl(movie);
        const movieId = getMovieId(movie);
        const score = Number.isFinite(Number(movie.score)) ? Number(movie.score) : NaN;

        modalPoster.src = posterUrl;
        modalPoster.alt = `${title} poster`;
        modalPoster.onerror = () => {
            modalPoster.src = generatedPoster(movie);
        };
        modalTitle.textContent = title;
        modalKicker.textContent = movieId ? `Movie #${movieId}` : 'Recommendation';
        modalMeta.textContent = [
            movie.release_year || 'Year N/A',
            genres.join(', '),
            formatScore(score),
            movie.strategy || 'recommended',
        ].join(' • ');
        modalRating.innerHTML = renderRatingControl(movie, ratingState[movieId] || 0);
        bindRatingEvents(modalRating, movie);
        modalExplanation.textContent = movie.explanation || 'A recommended title from your current taste profile. Rate it to tune future picks.';

        reviewTextarea.value = '';
        reviewCharCount.textContent = '0 / 2000';
        loadReview(movieId);

        movieModal.classList.remove('hidden');
        modalClose.focus();
    }

    function closeMovieDetails() {
        movieModal.classList.add('hidden');
        activeMovie = null;
    }

    function renderRatingControl(movie, selectedRating) {
        const movieId = getMovieId(movie);
        const rating = Number(selectedRating) || 0;
        const label = rating > 0 ? `Your rating: ${rating} out of 5` : 'Rate this movie';
        const stars = [1, 2, 3, 4, 5].map(value => `
            <button
                type="button"
                class="star-btn${value <= rating ? ' active' : ''}"
                data-rating="${value}"
                data-movie-id="${escapeHtml(movieId)}"
                aria-label="Rate ${escapeHtml(movie.title || 'movie')} ${value} out of 5"
                title="${value} star${value === 1 ? '' : 's'}"
            >★</button>
        `).join('');

        return `
            <div class="rating-control" role="group" aria-label="${escapeHtml(label)}">
                <span class="rating-label">${escapeHtml(label)}</span>
                <div class="stars">${stars}</div>
            </div>
        `;
    }

    function updateRatingDisplay(container, rating) {
        container.querySelectorAll('.star-btn').forEach(star => {
            const value = Number(star.dataset.rating);
            star.classList.toggle('active', value <= rating);
            star.classList.remove('preview');
        });

        const label = container.querySelector('.rating-label');
        if (label) {
            label.textContent = rating > 0 ? `Your rating: ${rating} out of 5` : 'Rate this movie';
        }
    }

    function updateRatingPreview(container, previewRating) {
        const selectedRating = Number(container.dataset.selectedRating) || 0;
        const activeRating = previewRating || selectedRating;

        container.querySelectorAll('.star-btn').forEach(star => {
            const value = Number(star.dataset.rating);
            star.classList.toggle('preview', previewRating > 0 && value <= activeRating);
            star.classList.toggle('active', previewRating === 0 && value <= selectedRating);
        });
    }

    async function submitRating(movie, rating, container) {
        const movieId = getMovieId(movie);

        if (!movieId) {
            return;
        }

        const previousRating = ratingState[movieId];
        ratingState[movieId] = rating;
        saveStoredRatings();
        syncRatingDisplays(movieId, rating);

        const token = localStorage.getItem('access_token');
        if (!token) {
            showToast('Rating saved in this browser.', 'success');
            return;
        }

        try {
            const response = await fetch('/v1/ratings', {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    movie_id: Number(movieId),
                    rating,
                }),
            });

            if (!response.ok) {
                throw new Error(`Rating failed: ${response.status}`);
            }

            const saved = await response.json();
            ratingState[movieId] = saved.rating;
            saveStoredRatings();
            syncRatingDisplays(movieId, saved.rating);
            showToast('Rating saved.', 'success');
        } catch (err) {
            console.error(err);
            if (previousRating === undefined) {
                delete ratingState[movieId];
            } else {
                ratingState[movieId] = previousRating;
            }
            saveStoredRatings();
            syncRatingDisplays(movieId, ratingState[movieId] || 0);
            showToast('Could not save rating. Try again.', 'error');
        }
    }

    function syncRatingDisplays(movieId, rating) {
        document.querySelectorAll(`[data-rating-movie-id="${CSS.escape(String(movieId))}"]`).forEach(container => {
            container.dataset.selectedRating = String(rating || 0);
            updateRatingDisplay(container, rating || 0);
            const badge = container.querySelector('.rated-badge');
            if (badge) {
                badge.classList.toggle('hidden', !rating);
            }
        });
    }

    function showToast(message, type = 'success') {
        toast.textContent = message;
        toast.className = `toast ${type}`;
        clearTimeout(toastTimer);
        toastTimer = setTimeout(() => {
            toast.classList.add('hidden');
        }, 2600);
    }

    function renderRecommendationsError() {
        loader.classList.add('hidden');
        moviesContainer.classList.remove('hidden');
        moviesContainer.innerHTML = `
            <div class="recommendations-state">
                <p class="error-msg">Unable to load recommendations.</p>
                <button type="button" id="retry-recommendations" class="btn btn-outline">Retry</button>
            </div>
        `;
        document.getElementById('retry-recommendations').addEventListener('click', loadRecommendations);
    }

    function renderMovies(movies) {
        loader.classList.add('hidden');
        moviesContainer.classList.remove('hidden');
        moviesContainer.innerHTML = '';

        if (!movies || movies.length === 0) {
            moviesContainer.innerHTML = '<p class="recommendations-state">No recommendations available</p>';
            return;
        }

        movies.forEach(movie => {
            const card = document.createElement('article');
            card.className = 'movie-card';
            card.setAttribute('role', 'button');
            card.setAttribute('tabindex', '0');
            card.setAttribute('aria-label', `Open details for ${movie.title || 'movie'}`);

            const title = movie.title || 'Untitled movie';
            const genres = Array.isArray(movie.genres) && movie.genres.length > 0 ? movie.genres : ['Unknown genre'];
            const score = Number.isFinite(Number(movie.score)) ? Number(movie.score) : 0;
            const posterUrl = resolvePosterUrl(movie);
            const movieId = getMovieId(movie);
            const selectedRating = ratingState[movieId] || 0;
            card.dataset.selectedRating = String(selectedRating);

            card.innerHTML = `
                <div class="rated-badge${selectedRating > 0 ? '' : ' hidden'}" aria-label="Rated">✓</div>
                <img class="poster" src="${posterUrl}" alt="${escapeHtml(title)} poster" loading="lazy">
                <div class="movie-info">
                    <div>
                        <div class="movie-title">${escapeHtml(title)}</div>
                        <div class="movie-meta">
                            <span>${escapeHtml(movie.release_year || 'N/A')}</span>
                            <span>${escapeHtml(genres.slice(0, 2).join(', '))}</span>
                        </div>
                        <p class="movie-description">${escapeHtml(movie.explanation || 'Recommended from your profile. Open details or rate it to personalize future picks.')}</p>
                    </div>
                    ${renderRatingControl(movie, selectedRating)}
                    <div class="movie-meta" style="margin-top: 10px;">
                        <span class="match-score">${escapeHtml(formatScore(score))}</span>
                        <span style="font-size: 0.8rem; color: #888;">${escapeHtml(movie.strategy || 'recommended')}</span>
                    </div>
                </div>
            `;
            card.querySelector('.poster').addEventListener('error', event => {
                event.currentTarget.src = generatedPoster(movie);
            }, { once: true });
            card.addEventListener('click', () => openMovieDetails(movie));
            card.addEventListener('keydown', event => {
                if (event.target.closest('.star-btn')) {
                    return;
                }
                if (event.key === 'Enter' || event.key === ' ') {
                    event.preventDefault();
                    openMovieDetails(movie);
                }
            });
            bindRatingEvents(card, movie);
            moviesContainer.appendChild(card);
        });
    }

    reviewTextarea.addEventListener('input', () => {
        reviewCharCount.textContent = `${reviewTextarea.value.length} / 2000`;
    });

    reviewSubmitBtn.addEventListener('click', async () => {
        if (!activeMovie) return;
        const movieId = getMovieId(activeMovie);
        const text = reviewTextarea.value.trim();
        if (!text) return;

        reviewSubmitBtn.disabled = true;
        const token = localStorage.getItem('access_token');
        try {
            const res = await fetch('/v1/reviews', {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
                body: JSON.stringify({ movie_id: Number(movieId), review_text: text }),
            });
            if (res.ok) {
                showToast('Review saved.', 'success');
            } else {
                showToast('Could not save review.', 'error');
            }
        } catch {
            showToast('Could not save review.', 'error');
        } finally {
            reviewSubmitBtn.disabled = false;
        }
    });

    async function loadReview(movieId) {
        if (!movieId) return;
        const token = localStorage.getItem('access_token');
        try {
            const res = await fetch(`/v1/reviews/${movieId}`, {
                headers: { 'Authorization': `Bearer ${token}` },
            });
            if (res.ok) {
                const data = await res.json();
                reviewTextarea.value = data.review_text || '';
                reviewCharCount.textContent = `${reviewTextarea.value.length} / 2000`;
            }
        } catch { /* no review yet */ }
    }

    function bindRatingEvents(container, movie) {
        const movieId = getMovieId(movie);
        container.dataset.ratingMovieId = String(movieId);
        container.dataset.selectedRating = String(ratingState[movieId] || 0);
        container.querySelectorAll('.star-btn').forEach(star => {
                star.addEventListener('mouseenter', event => {
                    updateRatingPreview(container, Number(event.currentTarget.dataset.rating));
                });
                star.addEventListener('focus', event => {
                    updateRatingPreview(container, Number(event.currentTarget.dataset.rating));
                });
                star.addEventListener('mouseleave', () => {
                    updateRatingPreview(container, 0);
                });
                star.addEventListener('blur', () => {
                    updateRatingPreview(container, 0);
                });
                star.addEventListener('click', event => {
                    event.preventDefault();
                    event.stopPropagation();
                    submitRating(movie, Number(star.dataset.rating), container);
                });
            });
    }
});
