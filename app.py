import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import streamlit as st
from src.analytics import calcular_metricas, filtrar_dados
from src.visuals import grafico_gantt
from datetime import datetime
import pandas as pd
from src.database import (
    criar_tabela,
    carregar_dados,
    salvar_programacao,
    carregar_operadores,
    adicionar_operador,
    remover_operador
)

criar_tabela()

st.set_page_config(layout="wide")

st.title("Programação Máquinas Laser")

# Carregar dados
df = carregar_dados()

# 🔥 Padronizar colunas (minúsculo + underscore)
df.columns = (
    df.columns
        .str.strip()
        .str.lower()
        .str.replace(" ", "_")
)

# 🔥 Converter colunas de data com segurança
colunas_data = ["inicio", "fim", "prazo_limite", "data_finalizado"]

for col in colunas_data:
    if col in df.columns:
        df[col] = pd.to_datetime(df[col], format="mixed", errors="coerce")


# DEBUG (pode remover depois)
#st.write("COLUNAS DO DF:", df.columns)

st.sidebar.divider()
st.sidebar.subheader("➕ Nova Programação")

with st.sidebar.form("form_programacao"):

    df_operadores = carregar_operadores()

    operador_novo = st.selectbox(
        "Operador",
        df_operadores["nome"] if not df_operadores.empty else []
    )
    produto_novo = st.text_input("Produto")
    inicio_novo = st.date_input("Data Início")
    fim_novo = st.date_input("Data Fim")
    prazo_limite_novo = st.date_input("Prazo Limite")
    status_novo = st.selectbox("Status", ["Programado", "Em produção", "Finalizado"])

    submit = st.form_submit_button("Salvar")

    if submit:

        # 🔎 VALIDAÇÕES
        if not operador_novo:
            st.error("Selecione um operador.")
        elif not produto_novo.strip():
            st.error("Digite o produto.")
        elif not inicio_novo:
            st.error("Selecione a data de início.")
        elif not fim_novo:
            st.error("Selecione a data de fim.")
        elif not status_novo:
            st.error("Selecione o status.")
        elif fim_novo < inicio_novo:
            st.error("A data final não pode ser menor que a data inicial.")
        elif prazo_limite_novo < fim_novo:
            st.error("O prazo limite não pode ser menor que a data final.")
        else:
            nova_linha = {
                "produto": produto_novo.strip(),
                "inicio": str(inicio_novo),
                "fim": str(fim_novo),
                "prazo_limite": str(prazo_limite_novo),
                "status": status_novo,
                "operador": operador_novo,
                "data_finalizado": None
            }

            salvar_programacao(nova_linha)

            st.success("Programação adicionada com sucesso!")
            st.rerun()

st.sidebar.divider()
st.sidebar.subheader("⚙️ Gerenciar Operadores")

from src.database import carregar_operadores, adicionar_operador, remover_operador

df_operadores = carregar_operadores()

# ➕ Adicionar operador
novo_operador = st.sidebar.text_input("Novo Operador")

if st.sidebar.button("Adicionar Operador"):
    if novo_operador.strip():
        adicionar_operador(novo_operador.strip())
        st.sidebar.success("Operador adicionado!")
        st.rerun()

# ❌ Remover operador
if not df_operadores.empty:
    operador_remover = st.sidebar.selectbox(
        "Remover Operador",
        df_operadores["nome"]
    )

    if st.sidebar.button("Remover Operador"):
        remover_operador(operador_remover)
        st.sidebar.warning("Operador removido!")
        st.rerun()

# Sidebar filtros
st.sidebar.header("Filtros")

maquina = st.sidebar.selectbox(
    "Operadores",
    ["Todas"] + list(df["operador"].unique())
)

status = st.sidebar.selectbox(
    "Status",
    ["Todos"] + list(df["status"].unique())
)

df_filtrado = filtrar_dados(df, maquina, status)

df_ativos = df_filtrado[df_filtrado["status"] != "Finalizado"]
df_finalizados = df_filtrado[df_filtrado["status"] == "Finalizado"]

# KPIs
metricas = calcular_metricas(df_filtrado)

col1, col2, col3 = st.columns(3)

col1.metric("Total de OPs", metricas["total_ops"])
col2.metric("Operadores em Produção", metricas["maquinas_ocupadas"])
col3.metric("Próximo Operador a Iniciar", metricas["proxima_maquina"])

st.divider()

# Tabela
st.subheader("Sequência de fabricação")

# 🔥 PEGAR APENAS NÃO FINALIZADOS
df_exibir = df_filtrado[df_filtrado["status"] != "Finalizado"].copy()

if not df_exibir.empty:

    # 🔥 FORMATAR DATAS
    df_exibir["inicio"] = df_exibir["inicio"].dt.strftime("%d/%m/%Y").fillna("")
    df_exibir["fim"] = df_exibir["fim"].dt.strftime("%d/%m/%Y").fillna("")
    df_exibir["prazo_limite"] = df_exibir["prazo_limite"].dt.strftime("%d/%m/%Y").fillna("")

    # 🔥 ORDEM DAS COLUNAS
    colunas_exibir = ["produto", "operador", "status", "inicio", "fim", "prazo_limite"]

    # 🔥 PEGAR SOMENTE OPERADORES QUE TÊM PRODUÇÃO ATIVA
    operadores = (
        df_exibir["operador"]
        .dropna()
        .astype(str)
        .unique()
        .tolist()
    )

    if operadores:

        abas = st.tabs(operadores)

        for aba, operador in zip(abas, operadores):
            with aba:

                df_operador = df_exibir[
                    df_exibir["operador"].astype(str) == operador
                ]

                if not df_operador.empty:

                    df_operador = df_operador[colunas_exibir]

                    st.dataframe(
                        df_operador,
                        use_container_width=True,
                        hide_index=True
                    )

else:
    st.info("Nenhuma programação ativa.")

st.divider()
# Gantt
fig = grafico_gantt(df_ativos)
st.plotly_chart(fig, use_container_width=True)

st.divider()

st.subheader("✅ Finalizar Programação")

# 🔥 usar minúsculo
produtos_abertos = df_ativos["produto"].unique()

if len(produtos_abertos) > 0:

    op_finalizar = st.selectbox(
        "Selecione o produto para finalizar",
        produtos_abertos
    )

    if st.button("Marcar como Finalizado"):

        hoje = datetime.today()

        import sqlite3

        conn = sqlite3.connect("data/programacao.db")
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE programacao
            SET status = ?, data_finalizado = ?
            WHERE produto = ?
        """, ("Finalizado", str(hoje), op_finalizar))

        conn.commit()
        conn.close()

        st.success("Produto finalizado com sucesso!")
        st.rerun()

else:
    st.info("Nenhum produto ativo para finalizar.")

st.divider()

st.subheader("📋 Programações Finalizadas")

if not df_finalizados.empty:

    operadores = (
        df_finalizados["operador"]
        .dropna()
        .astype(str)
        .unique()
        .tolist()
    )

    abas = st.tabs(operadores)

    for aba, operador in zip(abas, operadores):

        with aba:

            df_operador = df_finalizados[
                df_finalizados["operador"].astype(str) == operador
            ].copy()

            # 🔥 FORMATAR DATAS
            df_operador["inicio"] = df_operador["inicio"].dt.strftime("%d/%m/%Y")
            df_operador["fim"] = df_operador["fim"].dt.strftime("%d/%m/%Y")
            df_operador["prazo_limite"] = df_operador["prazo_limite"].dt.strftime("%d/%m/%Y")
            df_operador["data_finalizado"] = (
                pd.to_datetime(df_operador["data_finalizado"])
                .dt.strftime("%d/%m/%Y")
            )

            # 🔥 ORDEM DAS COLUNAS
            colunas_exibir = [
                "produto",
                "inicio",
                "fim",
                "prazo_limite",
                "data_finalizado",
                "status"
            ]

            df_operador = df_operador[colunas_exibir]

            st.dataframe(
                df_operador,
                use_container_width=True,
                hide_index=True
            )

else:
    st.info("Nenhuma programação finalizada.")


    st.markdown(
        """
        <style>
        .footer {
            position: fixed;
            right: 20px;
            bottom: 10px;
            font-size: 12px;
            color: gray;
            opacity: 0.8;
        }
        </style>
        <div class="footer">
            Desenvolvido por <b>Guilherme Luiz</b> | PCP
        </div>
        """,
        unsafe_allow_html=True
    )
