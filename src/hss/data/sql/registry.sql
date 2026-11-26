CREATE TABLE IF NOT EXISTS modules (id TEXT PRIMARY KEY, installed_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS bindings (component TEXT PRIMARY KEY, command TEXT NOT NULL, managed INTEGER NOT NULL DEFAULT 0, location TEXT, environment TEXT NOT NULL DEFAULT '{}');
CREATE TABLE IF NOT EXISTS assets (module TEXT NOT NULL, path TEXT NOT NULL, content TEXT NOT NULL, PRIMARY KEY(module,path));
CREATE TABLE IF NOT EXISTS module_components (module TEXT NOT NULL, component TEXT NOT NULL, PRIMARY KEY(module,component));
CREATE TABLE IF NOT EXISTS connections (id TEXT PRIMARY KEY, config TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS preparations (
    id TEXT PRIMARY KEY, status TEXT NOT NULL, request TEXT NOT NULL,
    result TEXT, message TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
    started_at TEXT, cancel_requested INTEGER NOT NULL DEFAULT 0
);
