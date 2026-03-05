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

# -------------------------------------------------
# CONFIGURAÇÃO DA PÁGINA
# -------------------------------------------------

st.set_page_config(
    page_title="Programação Laser",
    layout="wide"
)

# -------------------------------------------------
# CRIAR TABELA
# -------------------------------------------------

criar_tabela()

# -------------------------------------------------
# FUNÇÃO CARREGAR DADOS
# -------------------------------------------------

def carregar():
    df = carregar_dados()

    df.columns = (
        df.columns
        .str.strip()
        .str.lower()
        .str.replace(" ", "_")
    )

    datas = ["inicio", "fim", "prazo_limite", "data_finalizado"]

    for col in datas:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")

    return df


df = carregar()

# -------------------------------------------------
# FOOTER
# -------------------------------------------------

def get_base64_image(path):
    with open(path, "rb") as img:
        return base64.b64encode(img.read()).decode()

logo = get_base64_image("assets/logo2.png")

st.markdown(f"""
<style>
.footer {{
position: fixed;
bottom: 15px;
right: 20px;
display: flex;
align-items: center;
gap: 10px;
background: rgba(20,20,20,0.8);
padding: 8px 12px;
border-radius: 10px;
font-size:12px;
}}

.footer img {{
height:32px;
}}
</style>

<div class="footer">
<img src="data:image/png;base64,{logo}">
<div>
<b>Guilherme Luiz</b><br>
Auxiliar PCP
</div>
</div>
""", unsafe_allow_html=True)

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

    inicio = st.date_input("Início")
    fim = st.date_input("Fim")
    prazo = st.date_input("Prazo limite")

    status = st.selectbox(
        "Status",
        ["Programado","Em produção","Finalizado"]
    )

    pdf_desenho = st.file_uploader(
    "Desenho do Produto (PDF)",
    type=["pdf"]
)

    salvar = st.form_submit_button("Salvar")

    if salvar:

        nome_pdf = None

        if pdf_desenho is not None:

            nome_pdf = pdf_desenho.name

            # cria pasta se não existir
            os.makedirs("desenhos", exist_ok=True)

            caminho_pdf = os.path.join("desenhos", nome_pdf)

            with open(caminho_pdf, "wb") as f:
                f.write(pdf_desenho.getbuffer())

        nova = dict(
            produto=produto,
            operador=operador,
            inicio=str(inicio),
            fim=str(fim),
            prazo_limite=str(prazo),
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
# TABELA EDITÁVEL
# -------------------------------------------------

st.subheader("Sequência de fabricação")

df_tabela = df_ativos.copy()

if not df_tabela.empty:

    # converter datas
    df_tabela["inicio"] = df_tabela["inicio"].dt.date
    df_tabela["fim"] = df_tabela["fim"].dt.date
    df_tabela["prazo_limite"] = df_tabela["prazo_limite"].dt.date

    # criar link do desenho
    def link_pdf(nome):
        if pd.notna(nome) and nome != "":
            return f"desenhos/{nome}"
        return ""

    if "desenho" in df_tabela.columns:
        df_tabela["desenho"] = df_tabela["desenho"].apply(link_pdf)
    else:
        df_tabela["desenho"] = ""

    # ordem das colunas
    colunas = [
        "id",
        "produto",
        "operador",
        "status",
        "inicio",
        "fim",
        "prazo_limite",
        "desenho"
    ]

    df_tabela = df_tabela[colunas]

    # tabela editável
    df_editado = st.data_editor(
        df_tabela,
        use_container_width=True,
        hide_index=True,
        num_rows="dynamic",
        disabled=["id", "desenho"],
        column_config={
            "id": st.column_config.NumberColumn(
                "ID",
                width="small"
            ),
            "desenho": st.column_config.LinkColumn(
                "Desenho",
                display_text="📄 Abrir PDF"
            )
        }
    )

    # botão salvar
    if st.button("💾 Salvar alterações"):

        for _, row in df_editado.iterrows():

            query = """
            UPDATE programacao
            SET produto=:produto,
                operador=:operador,
                status=:status,
                inicio=:inicio,
                fim=:fim,
                prazo_limite=:prazo
            WHERE id=:id
            """

            with engine.connect() as conn:
                conn.execute(
                    text(query),
                    dict(
                        produto=row["produto"],
                        operador=row["operador"],
                        status=row["status"],
                        inicio=row["inicio"],
                        fim=row["fim"],
                        prazo=row["prazo_limite"],
                        id=row["id"]
                    )
                )
                conn.commit()

        st.success("Alterações salvas")
        st.rerun()

else:

    st.info("Nenhuma programação ativa")

# -------------------------------------------------
# GANTT
# -------------------------------------------------

st.divider()

fig = grafico_gantt(df_ativos.sort_values("inicio"))

st.plotly_chart(fig,use_container_width=True)

# -------------------------------------------------
# FINALIZAR
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