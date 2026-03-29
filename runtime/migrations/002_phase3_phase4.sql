ALTER TABLE tasks ADD COLUMN source TEXT NOT NULL DEFAULT 'manual';
ALTER TABLE tasks ADD COLUMN workflow_id TEXT NOT NULL DEFAULT '';
ALTER TABLE tasks ADD COLUMN idempotency_key TEXT NOT NULL DEFAULT '';
ALTER TABLE tasks ADD COLUMN affected_files_json TEXT NOT NULL DEFAULT '[]';
ALTER TABLE tasks ADD COLUMN affected_skills_json TEXT NOT NULL DEFAULT '[]';

CREATE INDEX IF NOT EXISTS idx_tasks_workflow_id ON tasks(workflow_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_tasks_idempotency_key
  ON tasks(idempotency_key)
  WHERE idempotency_key != '';

ALTER TABLE notifications ADD COLUMN event_id INTEGER NOT NULL DEFAULT 0;

CREATE INDEX IF NOT EXISTS idx_notifications_task_id ON notifications(task_id);
CREATE INDEX IF NOT EXISTS idx_notifications_event_id ON notifications(event_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_notifications_unique_event_channel
  ON notifications(event_id, channel)
  WHERE event_id != 0;

CREATE TABLE IF NOT EXISTS notification_deliveries (
  delivery_id INTEGER PRIMARY KEY AUTOINCREMENT,
  notification_id INTEGER NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending',
  delivered_at TEXT NOT NULL DEFAULT '',
  error_message TEXT NOT NULL DEFAULT '',
  external_id TEXT NOT NULL DEFAULT '',
  FOREIGN KEY (notification_id) REFERENCES notifications(notification_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_notification_deliveries_notification_id
  ON notification_deliveries(notification_id);

CREATE TABLE IF NOT EXISTS watch_sources (
  path TEXT PRIMARY KEY,
  content_hash TEXT NOT NULL DEFAULT '',
  last_seen_at TEXT NOT NULL,
  last_changed_at TEXT NOT NULL DEFAULT ''
);

