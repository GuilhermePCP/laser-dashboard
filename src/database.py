import sqlite3
import pandas as pd


DB_PATH = "data/programacao.db"


def conectar():
    return sqlite3.connect(DB_PATH)


def criar_tabela():
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS operadores (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT UNIQUE NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS programacao (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            produto TEXT,
            operador TEXT,
            inicio TEXT,
            Fim TEXT,
            prazo_limite TEXT,
            status TEXT,
            data_finalizado TEXT
        )
    """)

    conn.commit()
    conn.close()

def carregar_operadores():
    conn = conectar()
    df = pd.read_sql("SELECT * FROM operadores ORDER BY nome", conn)
    conn.close()
    return df


def adicionar_operador(nome):
    conn = conectar()
    cursor = conn.cursor()

    try:
        cursor.execute("INSERT INTO operadores (nome) VALUES (?)", (nome,))
        conn.commit()
    except:
        pass

    conn.close()


def remover_operador(nome):
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM operadores WHERE nome = ?", (nome,))
    conn.commit()
    conn.close()


def carregar_dados():
    conn = conectar()
    df = pd.read_sql("SELECT * FROM programacao", conn)
    conn.close()

    return df


def salvar_programacao(dados):
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO programacao 
        (produto, operador, inicio, Fim, prazo_limite, status, data_finalizado)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        dados["Produto"],
        dados["Operador"],
        str(dados["Inicio"]),
        str(dados["Fim"]),
        str(dados["Prazo Limite"]),
        dados["Status"],
        dados.get("Data Finalizado")
    ))

    conn.commit()
    conn.close()