PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    display_name TEXT,
    fetched_at TEXT
);

CREATE TABLE IF NOT EXISTS films (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    letterboxd_id TEXT UNIQUE,
    title TEXT NOT NULL,
    year INTEGER
);

CREATE TABLE IF NOT EXISTS interactions (
    user_id INTEGER NOT NULL,
    film_id INTEGER NOT NULL,
    rating REAL,
    liked INTEGER DEFAULT 0,
    watched INTEGER DEFAULT 0,
    watchlist INTEGER DEFAULT 0,
    watch_date TEXT,
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
