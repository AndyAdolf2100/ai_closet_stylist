PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS stylist_companion_profiles (
  owner_id TEXT PRIMARY KEY, profile_json TEXT NOT NULL,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS stylist_sessions (
  id TEXT PRIMARY KEY, owner_id TEXT NOT NULL, version INTEGER NOT NULL DEFAULT 0,
  state_json TEXT NOT NULL, active_claim TEXT, lease_until REAL NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS stylist_sessions_owner ON stylist_sessions(owner_id, updated_at);
CREATE TABLE IF NOT EXISTS stylist_requests (
  owner_id TEXT NOT NULL, request_id TEXT NOT NULL, conversation_id TEXT NOT NULL,
  digest TEXT NOT NULL, status TEXT NOT NULL, response_json TEXT,
  PRIMARY KEY(owner_id, request_id),
  FOREIGN KEY(conversation_id) REFERENCES stylist_sessions(id)
);
CREATE TABLE IF NOT EXISTS stylist_messages (
  id INTEGER PRIMARY KEY AUTOINCREMENT, conversation_id TEXT NOT NULL, owner_id TEXT NOT NULL,
  version INTEGER NOT NULL, user_message TEXT NOT NULL, reply_json TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(conversation_id, version), FOREIGN KEY(conversation_id) REFERENCES stylist_sessions(id)
);
CREATE TABLE IF NOT EXISTS stylist_image_actions (
  id TEXT PRIMARY KEY, owner_id TEXT NOT NULL, conversation_id TEXT NOT NULL, version INTEGER NOT NULL,
  quote_json TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'quoted', result_json TEXT,
  expires_at REAL NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(conversation_id) REFERENCES stylist_sessions(id)
);

CREATE TABLE IF NOT EXISTS stylist_memory_books (
  owner_id TEXT PRIMARY KEY, revision INTEGER NOT NULL, book_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS stylist_outfit_images (
  id TEXT PRIMARY KEY, owner_id TEXT NOT NULL, conversation_id TEXT NOT NULL,
  status TEXT NOT NULL, claim TEXT NOT NULL, lease_until REAL NOT NULL DEFAULT 0,
  image_digest TEXT NOT NULL, image_url TEXT NOT NULL DEFAULT '',
  FOREIGN KEY(conversation_id) REFERENCES stylist_sessions(id)
);
