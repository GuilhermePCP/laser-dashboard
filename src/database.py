from sqlalchemy import create_engine, text
import pandas as pd
import streamlit as st
from datetime import datetime

# -------------------------------------------------
# CONEXÃO COM BANCO
# -------------------------------------------------

DATABASE_URL = st.secrets.get("DATABASE_URL")

if DATABASE_URL is None:
    st.error("DATABASE_URL não configurado no Streamlit Secrets")
    st.stop()

engine = create_engine(DATABASE_URL)


# -------------------------------------------------
# CRIAR TABELAS
# -------------------------------------------------

def criar_tabelas():

    with engine.begin() as conn:

        # PROGRAMACAO
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

        # OPERADORES
        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS operadores (
            id SERIAL PRIMARY KEY,
            nome TEXT UNIQUE
        )
        """))

        # CHAT
        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS chat (
            id SERIAL PRIMARY KEY,
            remetente TEXT,
            destinatario TEXT,
            mensagem TEXT,
            data TIMESTAMP DEFAULT NOW()
        )
        """))


# -------------------------------------------------
# CARREGAR PROGRAMACAO
# -------------------------------------------------

def carregar_dados():

    query = "SELECT * FROM programacao ORDER BY inicio"

    return pd.read_sql(query, engine)


# -------------------------------------------------
# SALVAR PROGRAMACAO
# -------------------------------------------------

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
                    desenho
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
                    :desenho
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
                    "desenho": row["desenho"]
                }
            )


# -------------------------------------------------
# FINALIZAR PROGRAMACAO
# -------------------------------------------------

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


# -------------------------------------------------
# ATUALIZAR PROGRAMACAO
# -------------------------------------------------

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


# -------------------------------------------------
# OPERADORES
# -------------------------------------------------

def carregar_operadores():

    return pd.read_sql("SELECT * FROM operadores ORDER BY nome", engine)


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
            text("""
            DELETE FROM operadores
            WHERE nome = :nome
            """),
            {"nome": nome}
        )


# -------------------------------------------------
# CHAT
# -------------------------------------------------

def enviar_mensagem(remetente, destinatario, mensagem):

    with engine.begin() as conn:

        conn.execute(
            text("""
            INSERT INTO chat
            (remetente, destinatario, mensagem)
            VALUES
            (:remetente, :destinatario, :mensagem)
            """),
            {
                "remetente": remetente,
                "destinatario": destinatario,
                "mensagem": mensagem
            }
        )


def carregar_chat(usuario, destino):

    query = text("""
    SELECT *
    FROM chat
    WHERE
        (remetente = :usuario AND destinatario = :destino)
        OR
        (remetente = :destino AND destinatario = :usuario)
    ORDER BY data
    """)

    with engine.begin() as conn:

        result = conn.execute(query, {
            "usuario": usuario,
            "destino": destino
        })

        rows = result.fetchall()

        return rows