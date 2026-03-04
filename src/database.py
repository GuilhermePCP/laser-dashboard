from sqlalchemy import create_engine, text
import pandas as pd
import os
import streamlit as st
import sqlalchemy # ou psycopg2

# O Streamlit busca automaticamente no .streamlit/secrets.toml (local)
# ou na aba Secrets (nuvem)
conn_string = st.secrets["DATABASE_URL"]

def get_connection():
    engine = sqlalchemy.create_engine(conn_string)
    return engine.connect()

# Agora você pode usar essa conexão para ler seu banco

# 🔥 Conexão com banco externo (Supabase)
DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)


# ----------------------------
# CRIAR TABELAS (caso não existam)
# ----------------------------

def criar_tabela():

    with engine.connect() as conn:

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS programacao (
                id SERIAL PRIMARY KEY,
                produto TEXT,
                inicio TIMESTAMP,
                fim TIMESTAMP,
                prazo_limite TIMESTAMP,
                status TEXT,
                operador TEXT,
                data_finalizado TIMESTAMP
            )
        """))

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS operadores (
                id SERIAL PRIMARY KEY,
                nome TEXT UNIQUE
            )
        """))

        conn.commit()


# ----------------------------
# CARREGAR DADOS
# ----------------------------

def carregar_dados():
    query = "SELECT * FROM programacao"
    return pd.read_sql(query, engine)


# ----------------------------
# SALVAR PROGRAMAÇÃO
# ----------------------------

def salvar_programacao(dados):
    df = pd.DataFrame([dados])
    df.to_sql("programacao", engine, if_exists="append", index=False)


# ----------------------------
# OPERADORES
# ----------------------------

def carregar_operadores():
    query = "SELECT * FROM operadores"
    return pd.read_sql(query, engine)


def adicionar_operador(nome):
    with engine.connect() as conn:
        conn.execute(
            text("INSERT INTO operadores (nome) VALUES (:nome) ON CONFLICT DO NOTHING"),
            {"nome": nome}
        )
        conn.commit()


def remover_operador(nome):
    with engine.connect() as conn:
        conn.execute(
            text("DELETE FROM operadores WHERE nome = :nome"),
            {"nome": nome}
        )
        conn.commit()