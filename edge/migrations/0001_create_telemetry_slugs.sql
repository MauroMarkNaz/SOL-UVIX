CREATE TABLE IF NOT EXISTS telemetry_slugs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    token TEXT NOT NULL,
    price REAL NOT NULL,
    volume REAL NOT NULL,
    timestamp INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_telemetry_slugs_token_timestamp
    ON telemetry_slugs (token, timestamp);
