PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS stylist_media_actions (
  id TEXT PRIMARY KEY, owner_id TEXT NOT NULL, kind TEXT NOT NULL, digest TEXT NOT NULL,
  status TEXT NOT NULL, snapshot_json TEXT NOT NULL, result_json TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS stylist_media_owner ON stylist_media_actions(owner_id,created_at);
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
CREATE TABLE IF NOT EXISTS stylist_deleted_conversations (
 owner_id TEXT NOT NULL, conversation_id TEXT NOT NULL,
 deleted_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 PRIMARY KEY(owner_id, conversation_id)
);
CREATE INDEX IF NOT EXISTS stylist_deleted_conversations_owner ON stylist_deleted_conversations(owner_id, deleted_at);
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

CREATE TABLE IF NOT EXISTS stylist_model_usage (
 event_id TEXT PRIMARY KEY, owner_id TEXT NOT NULL,
 conversation_id TEXT NOT NULL, request_id TEXT NOT NULL,
 message_version INTEGER, provider_request_id VARCHAR(256), payload_json TEXT NOT NULL,
 state VARCHAR(16) NOT NULL, created_at REAL NOT NULL,
 next_attempt REAL NOT NULL DEFAULT 0,
 lease VARCHAR(64), lease_until REAL NOT NULL DEFAULT 0,
 attempts INTEGER NOT NULL DEFAULT 0, last_error VARCHAR(64) NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS stylist_usage_delivery ON stylist_model_usage(state,next_attempt,lease_until);
CREATE INDEX IF NOT EXISTS stylist_usage_request ON stylist_model_usage(owner_id,conversation_id,request_id);

CREATE TABLE IF NOT EXISTS stylist_outfit_feedback (
 owner_id TEXT NOT NULL, conversation_id TEXT NOT NULL, version INTEGER NOT NULL,
 look_index INTEGER NOT NULL, vote VARCHAR(16) NOT NULL, style_name VARCHAR(16) NOT NULL,
 gender VARCHAR(8) NOT NULL, personal INTEGER NOT NULL,
 updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 PRIMARY KEY(owner_id,conversation_id,version,look_index),
 FOREIGN KEY(conversation_id) REFERENCES stylist_sessions(id)
);

CREATE TABLE IF NOT EXISTS stylist_outfit_saves (
 id TEXT PRIMARY KEY, owner_id TEXT NOT NULL, conversation_id TEXT NOT NULL,
 status VARCHAR(16) NOT NULL, outfit_id BIGINT, created_at REAL NOT NULL,
 FOREIGN KEY(conversation_id) REFERENCES stylist_sessions(id)
);

-- History reads filter by account and conversation, then paginate/order by version.
CREATE INDEX IF NOT EXISTS stylist_messages_owner_conversation_version ON stylist_messages(owner_id, conversation_id, version);
