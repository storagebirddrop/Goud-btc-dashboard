CREATE TABLE IF NOT EXISTS sources (id TEXT PRIMARY KEY, name TEXT NOT NULL, url TEXT, fetched_at TEXT);
CREATE TABLE IF NOT EXISTS series (id TEXT PRIMARY KEY, source_id TEXT NOT NULL REFERENCES sources(id), label TEXT NOT NULL, unit TEXT NOT NULL, currency TEXT, frequency TEXT NOT NULL DEFAULT 'M', description TEXT);
CREATE TABLE IF NOT EXISTS observations (series_id TEXT NOT NULL REFERENCES series(id), period TEXT NOT NULL, value REAL NOT NULL CHECK(value > 0), imported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY(series_id, period));
CREATE INDEX IF NOT EXISTS idx_observations_period ON observations(period);
CREATE TABLE IF NOT EXISTS import_runs (id TEXT PRIMARY KEY, started_at TEXT NOT NULL, status TEXT NOT NULL, details TEXT);
INSERT OR IGNORE INTO sources(id,name,url) VALUES ('cbs','Statistics Netherlands','https://opendata.cbs.nl/'),('gold','Gold price source',NULL),('ecb','European Central Bank','https://data-api.ecb.europa.eu/');
INSERT OR IGNORE INTO series(id,source_id,label,unit,currency,description) VALUES ('gold_eur_oz','gold','Gold price monthly mean','troy_oz','EUR','Monthly mean of daily EUR gold quotes'),('nl_house_avg_eur','cbs','Average existing home sale price','house','EUR','Composition-sensitive monthly average'),('nl_hpi','cbs','Existing home price index','index',NULL,'CBS/Kadaster price index; source base year may change');
