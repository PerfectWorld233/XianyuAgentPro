const path = require('path')
let db = null

function initDbManager(dataDir) {
  const Database = require('better-sqlite3')
  const dbPath = path.join(dataDir, 'app_config.db')
  db = new Database(dbPath)

  // Ensure tables exist (mirrors Python config_manager.py schema)
  db.exec(`
    CREATE TABLE IF NOT EXISTS config (
      key TEXT PRIMARY KEY NOT NULL,
      value TEXT NOT NULL,
      updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS prompts (
      name TEXT PRIMARY KEY NOT NULL,
      content TEXT NOT NULL,
      updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
  `)
}

function getConfig() {
  const rows = db.prepare('SELECT key, value FROM config').all()
  const result = {}
  for (const row of rows) {
    result[row.key] = row.value
  }
  return result
}

function saveConfig(data) {
  const stmt = db.prepare(`
    INSERT INTO config (key, value, updated_at) VALUES (?, ?, datetime('now'))
    ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
  `)
  const run = db.transaction((entries) => {
    for (const [key, value] of entries) {
      stmt.run(key, String(value))
    }
  })
  run(Object.entries(data))
}

function getPrompts() {
  const rows = db.prepare('SELECT name, content FROM prompts').all()
  const result = {}
  for (const row of rows) {
    result[row.name] = row.content
  }
  return result
}

function savePrompts(data) {
  const stmt = db.prepare(`
    INSERT INTO prompts (name, content, updated_at) VALUES (?, ?, datetime('now'))
    ON CONFLICT(name) DO UPDATE SET content = excluded.content, updated_at = excluded.updated_at
  `)
  const run = db.transaction((entries) => {
    for (const [name, content] of entries) {
      stmt.run(name, String(content))
    }
  })
  run(Object.entries(data))
}

module.exports = { initDbManager, getConfig, saveConfig, getPrompts, savePrompts }
