PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    display_name TEXT,
    follower_count INTEGER,
    following_count INTEGER,
    watched_count INTEGER,
    fetched_at TEXT
);

CREATE TABLE IF NOT EXISTS films (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    letterboxd_id TEXT UNIQUE,
    title TEXT NOT NULL,
    year INTEGER,
    genres TEXT
);

CREATE TABLE IF NOT EXISTS interactions (
    user_id INTEGER NOT NULL,
    film_id INTEGER NOT NULL,
    rating REAL,
    liked BOOLEAN DEFAULT 0,
    watched BOOLEAN DEFAULT 0,
    watchlist BOOLEAN DEFAULT 0,
    watch_date DATE,
    PRIMARY KEY (user_id, film_id),
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (film_id) REFERENCES films(id)
);

CREATE TABLE IF NOT EXISTS film_features (
    film_id INTEGER PRIMARY KEY,
    genres TEXT,
    directors TEXT,
    cast TEXT,
    tags TEXT,
    FOREIGN KEY (film_id) REFERENCES films(id)
);

CREATE TABLE IF NOT EXISTS availability (
    film_id INTEGER NOT NULL,
    provider TEXT NOT NULL,
    region TEXT NOT NULL,
    url TEXT,
    updated_at TEXT,
    PRIMARY KEY (film_id, provider, region),
    FOREIGN KEY (film_id) REFERENCES films(id)
);

CREATE TABLE IF NOT EXISTS graph_edges (
    src_user_id INTEGER NOT NULL,
    dst_user_id INTEGER NOT NULL,
    depth INTEGER NOT NULL,
    PRIMARY KEY (src_user_id, dst_user_id),
    FOREIGN KEY (src_user_id) REFERENCES users(id),
    FOREIGN KEY (dst_user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS recommendations (
    user_id INTEGER NOT NULL,
    film_id INTEGER NOT NULL,
    score_total REAL NOT NULL,
    score_content REAL,
    score_social REAL,
    model_version TEXT,
    PRIMARY KEY (user_id, film_id, model_version),
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (film_id) REFERENCES films(id)
);

CREATE TABLE IF NOT EXISTS film_availability_flags (
    film_id INTEGER PRIMARY KEY,
    region TEXT NOT NULL DEFAULT 'CA',
    stream BOOLEAN NOT NULL DEFAULT 0,
    netflix BOOLEAN NOT NULL DEFAULT 0,
    disney_plus BOOLEAN NOT NULL DEFAULT 0,
    prime_video BOOLEAN NOT NULL DEFAULT 0,
    apple_tv_plus BOOLEAN NOT NULL DEFAULT 0,
    crave BOOLEAN NOT NULL DEFAULT 0,
    mubi BOOLEAN NOT NULL DEFAULT 0,
    criterion_channel BOOLEAN NOT NULL DEFAULT 0,
    max BOOLEAN NOT NULL DEFAULT 0,
    hulu BOOLEAN NOT NULL DEFAULT 0,
    paramount_plus BOOLEAN NOT NULL DEFAULT 0,
    peacock BOOLEAN NOT NULL DEFAULT 0,
    tubi BOOLEAN NOT NULL DEFAULT 0,
    youtube BOOLEAN NOT NULL DEFAULT 0,
    plex BOOLEAN NOT NULL DEFAULT 0,
    amazon BOOLEAN NOT NULL DEFAULT 0,
    apple_itunes BOOLEAN NOT NULL DEFAULT 0,
    google_play_movies BOOLEAN NOT NULL DEFAULT 0,
    cineplex BOOLEAN NOT NULL DEFAULT 0,
    cosmogo BOOLEAN NOT NULL DEFAULT 0,
    last_updated TEXT NOT NULL,
    FOREIGN KEY (film_id) REFERENCES films(id)
);
