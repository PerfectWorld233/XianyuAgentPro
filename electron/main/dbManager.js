const path = require('path')
let db = null

function initDbManager(dataDir) {
  const Database = require('better-sqlite3')
  const dbPath = path.join(dataDir, 'app_config.db')
  db = new Database(dbPath)
  db.pragma('journal_mode = WAL')

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
    CREATE TABLE IF NOT EXISTS knowledge (
      id          INTEGER PRIMARY KEY AUTOINCREMENT,
      item_id     TEXT,
      question    TEXT NOT NULL,
      answer      TEXT NOT NULL,
      embedding   BLOB,
      created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
      updated_at  DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    CREATE INDEX IF NOT EXISTS idx_knowledge_item_id ON knowledge(item_id);
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

function listKnowledge(itemId) {
  if (itemId) {
    return db.prepare('SELECT id, item_id, question, answer, created_at, updated_at FROM knowledge WHERE item_id = ? ORDER BY id DESC').all(itemId)
  }
  return db.prepare('SELECT id, item_id, question, answer, created_at, updated_at FROM knowledge ORDER BY id DESC').all()
}

function addKnowledge({ question, answer, itemId }) {
  const stmt = db.prepare(
    `INSERT INTO knowledge (item_id, question, answer) VALUES (?, ?, ?)`
  )
  const result = stmt.run(itemId ?? null, question, answer)
  return { id: result.lastInsertRowid }
}

function updateKnowledge({ id, question, answer }) {
  const result = db.prepare(
    `UPDATE knowledge SET question = ?, answer = ?, embedding = NULL, updated_at = datetime('now') WHERE id = ?`
  ).run(question, answer, id)
  return result.changes
}

function deleteKnowledge(id) {
  const result = db.prepare(`DELETE FROM knowledge WHERE id = ?`).run(id)
  return result.changes
}

function batchAddKnowledge(entries, itemId) {
  const stmt = db.prepare(
    `INSERT INTO knowledge (item_id, question, answer) VALUES (?, ?, ?)`
  )
  const run = db.transaction((items) => {
    const ids = []
    for (const { question, answer } of items) {
      const result = stmt.run(itemId ?? null, question, answer)
      ids.push({ id: result.lastInsertRowid })
    }
    return ids
  })
  return run(entries)
}

module.exports = {
  initDbManager,
  getConfig,
  saveConfig,
  getPrompts,
  savePrompts,
  listKnowledge,
  addKnowledge,
  updateKnowledge,
  deleteKnowledge,
  batchAddKnowledge,
}
