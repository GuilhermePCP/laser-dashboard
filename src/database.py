from sqlalchemy import create_engine, text
import pandas as pd
import streamlit as st
from datetime import datetime
from sqlalchemy import text

def finalizar_programacao(id_programacao):
    with engine.connect() as conn:
        conn.execute(
            text("""
                UPDATE programacao
                SET status = 'Finalizado',
                    data_finalizado = :data_finalizado
                WHERE id = :id
            """),
            {
                "id": id_programacao,
                "data_finalizado": datetime.now()
            }
        )
        conn.commit()


# ----------------------------
# CONEXÃO COM O BANCO (SUPABASE)
# ----------------------------

DATABASE_URL = st.secrets["DATABASE_URL"]
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