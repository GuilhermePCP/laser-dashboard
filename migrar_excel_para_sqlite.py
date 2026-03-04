import pandas as pd
import sqlite3

# Caminhos
EXCEL_PATH = "data/programacao.xlsx"
DB_PATH = "data/programacao.db"

# Ler Excel
df = pd.read_excel(EXCEL_PATH)

# Conectar no banco
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# Criar tabela se não existir
cursor.execute("""
    CREATE TABLE IF NOT EXISTS programacao (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        produto TEXT,
        operador TEXT,
        inicio TEXT,
        fim TEXT,
        prazo_limite TEXT,
        status TEXT,
        data_finalizado TEXT
    )
""")

# Inserir dados
for _, row in df.iterrows():
    cursor.execute("""
        INSERT INTO programacao
        (produto, operador, inicio, fim, prazo_limite, status, data_finalizado)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        row.get("Produto"),
        row.get("Operador"),
        str(row.get("Inicio")),
        str(row.get("Fim")),
        str(row.get("Prazo Limite")),
        row.get("Status"),
        str(row.get("Data Finalizado")) if "Data Finalizado" in df.columns else None
    ))

conn.commit()
conn.close()

print("Migração concluída com sucesso!")