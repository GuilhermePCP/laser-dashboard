from sqlalchemy import create_engine, text
import pandas as pd
import streamlit as st
from datetime import datetime

# ----------------------------
# CONEXÃO COM O BANCO
# ----------------------------

DATABASE_URL = st.secrets["DATABASE_URL"]
engine = create_engine(DATABASE_URL)


# ----------------------------
# CRIAR TABELAS
# ----------------------------

def criar_tabela():

    with engine.begin() as conn:

        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS programacao (
            id SERIAL PRIMARY KEY,
            produto TEXT,
            quantidade INTEGER,
            operador TEXT,
            inicio TIMESTAMP,
            fim TIMESTAMP,
            prazo_limite TIMESTAMP,
            status TEXT,
            desenho BYTEA,
            nome_arquivo TEXT,
            data_finalizado TIMESTAMP
        )
        """))

        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS operadores (
            id SERIAL PRIMARY KEY,
            nome TEXT UNIQUE
        )
        """))


# ----------------------------
# CARREGAR DADOS
# ----------------------------

def carregar_dados():

    query = "SELECT * FROM programacao"

    return pd.read_sql(query, engine)


# ----------------------------
# SALVAR PROGRAMAÇÃO
# ----------------------------

def salvar_programacao(df):

    with engine.begin() as conn:

        for _, row in df.iterrows():

            conn.execute(
                text("""
                INSERT INTO programacao
                (
                    produto,
                    quantidade,
                    operador,
                    inicio,
                    fim,
                    prazo_limite,
                    status,
                    caminho_desenho,
                    nome_arquivo
                )
                VALUES
                (
                    :produto,
                    :quantidade,
                    :operador,
                    :inicio,
                    :fim,
                    :prazo_limite,
                    :status,
                    :caminho_desenho,
                    :nome_arquivo
                )
                """),
                {
                    "produto": row["produto"],
                    "quantidade": row["quantidade"],
                    "operador": row["operador"],
                    "inicio": row["inicio"],
                    "fim": row["fim"],
                    "prazo_limite": row["prazo_limite"],
                    "status": row["status"],
                    "caminho_desenho": row["caminho_desenho"],
                    "nome_arquivo": row["nome_arquivo"]
                }
            )


# ----------------------------
# FINALIZAR PROGRAMAÇÃO
# ----------------------------

def finalizar_programacao(id_programacao):

    with engine.begin() as conn:

        conn.execute(
            text("""
            UPDATE programacao
            SET status = 'Finalizado',
                data_finalizado = :data
            WHERE id = :id
            """),
            {
                "id": id_programacao,
                "data": datetime.now()
            }
        )


# ----------------------------
# OPERADORES
# ----------------------------

def carregar_operadores():

    return pd.read_sql("SELECT * FROM operadores", engine)


def adicionar_operador(nome):

    with engine.begin() as conn:

        conn.execute(
            text("""
            INSERT INTO operadores (nome)
            VALUES (:nome)
            ON CONFLICT DO NOTHING
            """),
            {"nome": nome}
        )


def remover_operador(nome):

    with engine.begin() as conn:

        conn.execute(
            text("DELETE FROM operadores WHERE nome = :nome"),
            {"nome": nome}
        )


# ----------------------------
# ATUALIZAR PROGRAMAÇÃO
# ----------------------------

def atualizar_programacao(df_editado):

    with engine.begin() as conn:

        for _, row in df_editado.iterrows():

            conn.execute(
                text("""
                UPDATE programacao
                SET produto = :produto,
                    quantidade = :quantidade,
                    inicio = :inicio,
                    fim = :fim,
                    prazo_limite = :prazo,
                    status = :status,
                    operador = :operador,
                    data_finalizado = :data_finalizado
                WHERE id = :id
                """),
                {
                    "id": row["id"],
                    "produto": row["produto"],
                    "quantidade": row["quantidade"],
                    "inicio": row["inicio"],
                    "fim": row["fim"],
                    "prazo": row["prazo_limite"],
                    "status": row["status"],
                    "operador": row["operador"],
                    "data_finalizado": row["data_finalizado"]
                }
            )