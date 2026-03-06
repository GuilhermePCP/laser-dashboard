import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import streamlit as st
import pandas as pd
import base64
from datetime import datetime

from src.analytics import calcular_metricas, filtrar_dados
from src.visuals import grafico_gantt
from src.database import (
    criar_tabela,
    carregar_dados,
    salvar_programacao,
    carregar_operadores,
    adicionar_operador,
    remover_operador,
    finalizar_programacao,
    engine
)

from sqlalchemy import text

def mostrar_pdf(caminho):
    if os.path.exists(caminho):

        with open(caminho, "rb") as f:
            pdf_bytes = f.read()

        st.download_button(
            "📄 Baixar desenho",
            data=pdf_bytes,
            file_name=os.path.basename(caminho),
            mime="application/pdf"
        )

        st.markdown("### Preview")

        pdf_base64 = base64.b64encode(pdf_bytes).decode("utf-8")

        pdf_display = f"""
        <embed 
        src="data:application/pdf;base64,{pdf_base64}" 
        width="100%" 
        height="900px" 
        type="application/pdf">
        """

        st.markdown(pdf_display, unsafe_allow_html=True)

    else:
        st.warning("Desenho não encontrado.")


# -------------------------------------------------
# CONFIG
# -------------------------------------------------

st.set_page_config(
    page_title="Programação Laser",
    layout="wide"
)

PASTA_DESENHOS = "desenhos"
os.makedirs(PASTA_DESENHOS, exist_ok=True)

criar_tabela()

# -------------------------------------------------
# FUNÇÕES
# -------------------------------------------------

def carregar():

    df = carregar_dados()

    df.columns = (
        df.columns
        .str.strip()
        .str.lower()
        .str.replace(" ", "_")
    )

    datas = ["inicio","fim","prazo_limite","data_finalizado"]

    for col in datas:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")

    return df


# -------------------------------------------------
# CARREGAR DADOS
# -------------------------------------------------

df = carregar()

# -------------------------------------------------
# SIDEBAR NOVA PROGRAMAÇÃO
# -------------------------------------------------

st.sidebar.subheader("➕ Nova Programação")

with st.sidebar.form("nova_op"):

    operadores = carregar_operadores()

    operador = st.selectbox(
        "Operador",
        operadores["nome"] if not operadores.empty else []
    )

    produto = st.text_input("Produto")

    quantidade = st.number_input(
        "Quantidade",
        min_value=1,
        step=1
    )

    inicio = st.date_input("Início")
    fim = st.date_input("Fim")
    prazo = st.date_input("Prazo limite")

    status = st.selectbox(
        "Status",
        ["Programado","Em produção","Finalizado"]
    )

    pdf_file = st.file_uploader(
        "Desenho (PDF)",
        type=["pdf"]
    )

    salvar = st.form_submit_button("Salvar")

    if salvar:

        nome_pdf = None

        if pdf_file:

            nome_pdf = f"{produto}_{datetime.now().timestamp()}.pdf"

            with open(f"{PASTA_DESENHOS}/{nome_pdf}", "wb") as f:
                f.write(pdf_file.getbuffer())

        nova = dict(
            produto=produto,
            quantidade=quantidade,
            operador=operador,
            inicio=inicio,
            fim=fim,
            prazo_limite=prazo,
            status=status,
            desenho=nome_pdf,
            data_finalizado=None
        )

        salvar_programacao(nova)

        st.success("Programação criada")
        st.rerun()

# -------------------------------------------------
# GERENCIAR OPERADORES
# -------------------------------------------------

st.sidebar.divider()
st.sidebar.subheader("⚙️ Operadores")

novo = st.sidebar.text_input("Novo operador")

if st.sidebar.button("Adicionar operador"):

    if novo:
        adicionar_operador(novo)
        st.rerun()

ops = carregar_operadores()

if not ops.empty:

    remover = st.sidebar.selectbox(
        "Remover operador",
        ops["nome"]
    )

    if st.sidebar.button("Remover operador"):

        remover_operador(remover)
        st.rerun()

# -------------------------------------------------
# FILTROS
# -------------------------------------------------

st.sidebar.divider()
st.sidebar.subheader("Filtros")

maquina = st.sidebar.selectbox(
    "Operador",
    ["Todas"] + list(df["operador"].dropna().unique())
)

status = st.sidebar.selectbox(
    "Status",
    ["Todos"] + list(df["status"].dropna().unique())
)

df_filtrado = filtrar_dados(df, maquina, status)

df_ativos = df_filtrado[df_filtrado["status"] != "Finalizado"]
df_finalizados = df_filtrado[df_filtrado["status"] == "Finalizado"]

# -------------------------------------------------
# KPIs
# -------------------------------------------------

metricas = calcular_metricas(df_filtrado)

c1,c2,c3 = st.columns(3)

c1.metric("Total OPs", metricas["total_ops"])
c2.metric("Operadores ativos", metricas["maquinas_ocupadas"])
c3.metric("Próxima máquina", metricas["proxima_maquina"])

st.divider()

# -------------------------------------------------
# TABELA + PREVIEW PDF
# -------------------------------------------------

st.subheader("Sequência de fabricação")

col_tabela, col_pdf = st.columns([2,1])

with col_tabela:

    if not df_ativos.empty:

        df_view = df_ativos[
            [
                "id",
                "produto",
                "quantidade",
                "operador",
                "status",
                "inicio",
                "fim",
                "prazo_limite"
            ]
        ].copy()

        tabela = st.dataframe(
            df_view,
            use_container_width=True,
            selection_mode="single-row",
            on_select="rerun"
        )

        if tabela["selection"]["rows"]:

            index = tabela["selection"]["rows"][0]

            linha = df_ativos.iloc[index]

            st.session_state["pdf_selecionado"] = linha["desenho"]

with col_pdf:

    st.subheader("📄 Desenho da peça")

    if "pdf_selecionado" in st.session_state:

        caminho_pdf = f"{PASTA_DESENHOS}/{st.session_state['pdf_selecionado']}"

        mostrar_pdf(caminho_pdf)

    else:

        st.info("Clique em uma peça para visualizar o desenho")

# -------------------------------------------------
# GANTT
# -------------------------------------------------

st.divider()

df_grafico = df_ativos.copy()

df_grafico["inicio"] = pd.to_datetime(df_grafico["inicio"])
df_grafico["fim"] = pd.to_datetime(df_grafico["fim"])

fig = grafico_gantt(df_grafico.sort_values("inicio"))

st.plotly_chart(fig, use_container_width=True)

# -------------------------------------------------
# FINALIZAR OP
# -------------------------------------------------

st.divider()
st.subheader("Finalizar programação")

df_abertos = df[df["status"] != "Finalizado"]

if not df_abertos.empty:

    opcoes = (
        df_abertos["id"].astype(str)
        +" | "+
        df_abertos["produto"]
        +" | "+
        df_abertos["operador"]
    )

    escolha = st.selectbox(
        "Selecionar OP",
        opcoes
    )

    if st.button("Finalizar OP"):

        id_finalizar = int(escolha.split("|")[0])

        finalizar_programacao(id_finalizar)

        st.success("OP finalizada")
        st.rerun()

else:

    st.info("Nenhuma OP aberta")

# -------------------------------------------------
# HISTÓRICO
# -------------------------------------------------

st.divider()
st.subheader("Programações finalizadas")

if not df_finalizados.empty:

    df_hist = df_finalizados.copy()

    df_hist["inicio"] = df_hist["inicio"].dt.date
    df_hist["fim"] = df_hist["fim"].dt.date
    df_hist["prazo_limite"] = df_hist["prazo_limite"].dt.date
    df_hist["data_finalizado"] = df_hist["data_finalizado"].dt.date

    st.dataframe(
        df_hist[
            [
                "produto",
                "operador",
                "inicio",
                "fim",
                "prazo_limite",
                "data_finalizado"
            ]
        ],
        use_container_width=True
    )

else:

    st.info("Nenhuma finalizada")