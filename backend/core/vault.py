import sqlite3
from datetime import datetime
import os

DB_PATH = "vault.db"

def init_vault():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    cursor = conn.cursor()

    # Histórico
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS search_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        cep TEXT,
        term TEXT,
        results_count INTEGER,
        timestamp DATETIME
    )
    """)
    # Categorias (Legado)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS learned_categories (
        term TEXT PRIMARY KEY,
        tag_key TEXT,
        tag_value TEXT,
        confidence INTEGER DEFAULT 1
    )
    """)
    # Etiquetas (Cérebro do Sistema)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS etiquetas (
        termo TEXT PRIMARY KEY,
        tag_key TEXT,
        tag_value TEXT,
        fonte TEXT,
        timestamp DATETIME
    )
    """)
    # Traduções
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS translations (
        portuguese TEXT PRIMARY KEY,
        english TEXT,
        timestamp DATETIME
    )
    """)
    conn.commit()
    conn.close()

def log_search(cep, term, count):
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO search_history (cep, term, results_count, timestamp) VALUES (?, ?, ?, ?)",
            (cep, term, count, datetime.now())
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Erro ao logar busca: {e}")

def get_learned_tag(term):
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT tag_key, tag_value FROM learned_categories WHERE term = ?", (term.lower().strip(),))
        row = cursor.fetchone()
        conn.close()
        return row if row else None
    except:
        return None

def save_learned_tag(term, key, value):
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
        INSERT INTO learned_categories (term, tag_key, tag_value, confidence)
        VALUES (?, ?, ?, 1)
        ON CONFLICT(term) DO UPDATE SET confidence = confidence + 1
        """, (term.lower().strip(), key, value))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Erro ao salvar tag aprendida: {e}")

def get_etiqueta(termo):
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT tag_key, tag_value FROM etiquetas WHERE termo = ?", (termo.lower().strip(),))
        row = cursor.fetchone()
        conn.close()
        return {"key": row[0], "value": row[1]} if row else None
    except:
        return None

def save_etiqueta(termo, key, value, fonte="Auto"):
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO etiquetas (termo, tag_key, tag_value, fonte, timestamp) VALUES (?, ?, ?, ?, ?)",
            (termo.lower().strip(), key, value, fonte, datetime.now())
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Erro ao salvar etiqueta: {e}")

def get_translation(term):
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT english FROM translations WHERE portuguese = ?", (term.lower().strip(),))
        row = cursor.fetchone()
        conn.close()
        return row[0] if row else None
    except:
        return None

def save_translation(portuguese, english):
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO translations (portuguese, english, timestamp) VALUES (?, ?, ?)",
            (portuguese.lower().strip(), english.lower().strip(), datetime.now())
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Erro ao salvar tradução: {e}")
