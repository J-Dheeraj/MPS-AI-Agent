import Database from 'better-sqlite3';
import path from 'path';

const dbPath = path.join(process.env.GROUP_DIR || '/workspace/group', 'mnemon.db');
const db = new Database(dbPath);

db.exec(`
  CREATE TABLE IF NOT EXISTS facts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity TEXT,
    predicate TEXT,
    value TEXT,
    source TEXT,
    timestamp INTEGER
  );
  CREATE VIRTUAL TABLE IF NOT EXISTS facts_fts USING fts5(entity, predicate, value, content=facts, content_rowid=id);
`);

export const mnemon = {
  addFact(entity: string, predicate: string, value: string, source: string): void {
    const stmt = db.prepare(`INSERT INTO facts (entity, predicate, value, source, timestamp) VALUES (?, ?, ?, ?, ?)`);
    const info = stmt.run(entity, predicate, value, source, Date.now());
    db.prepare(`INSERT INTO facts_fts(rowid, entity, predicate, value) VALUES (?, ?, ?, ?)`).run(info.lastInsertRowid, entity, predicate, value);
  },

  searchFacts(query: string): string[] {
    try {
      const rows = db.prepare(`
        SELECT f.entity, f.predicate, f.value FROM facts_fts
        JOIN facts f ON f.id = facts_fts.rowid
        WHERE facts_fts MATCH ? LIMIT 10
      `).all(query) as any[];
      return rows.map(r => `${r.entity} ${r.predicate}: ${r.value}`);
    } catch {
      return [];
    }
  },
};
