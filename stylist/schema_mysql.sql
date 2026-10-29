CREATE TABLE IF NOT EXISTS stylist_companion_profiles (
  owner_id VARCHAR(191) NOT NULL PRIMARY KEY,
  profile_json LONGTEXT NOT NULL,
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;
CREATE TABLE IF NOT EXISTS stylist_sessions (
  id VARCHAR(191) NOT NULL PRIMARY KEY, owner_id VARCHAR(191) NOT NULL,
  version INTEGER NOT NULL DEFAULT 0, state_json LONGTEXT NOT NULL,
  active_claim VARCHAR(64), lease_until DOUBLE NOT NULL DEFAULT 0,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  INDEX stylist_sessions_owner(owner_id, updated_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;
CREATE TABLE IF NOT EXISTS stylist_requests (
  owner_id VARCHAR(191) NOT NULL, request_id VARCHAR(191) NOT NULL,
  conversation_id VARCHAR(191) NOT NULL, digest VARCHAR(64) NOT NULL,
  status VARCHAR(32) NOT NULL, response_json LONGTEXT,
  PRIMARY KEY(owner_id,request_id),
  FOREIGN KEY(conversation_id) REFERENCES stylist_sessions(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;
CREATE TABLE IF NOT EXISTS stylist_messages (
  id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  conversation_id VARCHAR(191) NOT NULL, owner_id VARCHAR(191) NOT NULL,
  version INTEGER NOT NULL, user_message LONGTEXT NOT NULL, reply_json LONGTEXT NOT NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  UNIQUE(conversation_id,version), FOREIGN KEY(conversation_id) REFERENCES stylist_sessions(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;
CREATE TABLE IF NOT EXISTS stylist_image_actions (
  id VARCHAR(191) NOT NULL PRIMARY KEY, owner_id VARCHAR(191) NOT NULL,
  conversation_id VARCHAR(191) NOT NULL, version INTEGER NOT NULL,
  quote_json LONGTEXT NOT NULL, status VARCHAR(32) NOT NULL DEFAULT 'quoted', result_json LONGTEXT,
  expires_at DOUBLE NOT NULL, created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  FOREIGN KEY(conversation_id) REFERENCES stylist_sessions(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;
CREATE TABLE IF NOT EXISTS stylist_checkpoints (
  thread_id VARCHAR(191) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  checkpoint_ns VARCHAR(191) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  checkpoint_id VARCHAR(191) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  parent_checkpoint_id VARCHAR(191), type VARCHAR(32) NOT NULL,
  checkpoint LONGBLOB NOT NULL, metadata LONGTEXT NOT NULL,
  PRIMARY KEY(thread_id,checkpoint_ns,checkpoint_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;
CREATE TABLE IF NOT EXISTS stylist_checkpoint_writes (
  thread_id VARCHAR(191) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  checkpoint_ns VARCHAR(191) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  checkpoint_id VARCHAR(191) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  task_id VARCHAR(191) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  idx INTEGER NOT NULL, channel VARCHAR(191) NOT NULL, type VARCHAR(32) NOT NULL,
  value LONGBLOB NOT NULL,
  PRIMARY KEY(thread_id,checkpoint_ns,checkpoint_id,task_id,idx)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE IF NOT EXISTS stylist_memory_books (
  owner_id VARCHAR(191) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin PRIMARY KEY,
  revision INTEGER NOT NULL, book_json LONGTEXT NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;
