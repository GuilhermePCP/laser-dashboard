import streamlit as st
import pandas as pd
import base64
import io
import fitz
from PIL import Image
from datetime import datetime
from sqlalchemy import text

from src.database import (
    engine,
    criar_tabela,
    carregar_dados,
    salvar_programacao,
    carregar_operadores,
    adicionar_operador,
    remover_operador
)

from src.analytics import calcular_metricas, filtrar_dados
from src.visuals import grafico_gantt


# ------------------------------------------------
# CONFIGURAÇÃO DA PÁGINA
# ------------------------------------------------

st.set_page_config(
    page_title="Programação Laser",
    layout="wide"
)

# ------------------------------------------------
# SESSION STATE
# ------------------------------------------------

if "logado" not in st.session_state:
    st.session_state.logado = False

if "usuario" not in st.session_state:
    st.session_state.usuario = None

if "nivel" not in st.session_state:
    st.session_state.nivel = None


# ------------------------------------------------
# LOGIN
# ------------------------------------------------

def verificar_login(usuario, senha):

    query = """
    SELECT usuario, senha, nivel
    FROM usuarios
    WHERE usuario = :usuario
    AND senha = :senha
    """

    with engine.begin() as conn:

        result = conn.execute(
            text(query),
            {"usuario": usuario, "senha": senha}
        ).fetchone()

    return result


if not st.session_state.logado:

    st.title("🔐 Login do Sistema")

    usuario = st.text_input("Usuário")
    senha = st.text_input("Senha", type="password")

    if st.button("Entrar"):

        login = verificar_login(usuario, senha)

        if login:

            st.session_state.logado = True
            st.session_state.usuario = login.usuario
            st.session_state.nivel = login.nivel

            st.rerun()

        else:

            st.error("Usuário ou senha inválidos")

    st.stop()


# ------------------------------------------------
# PERMISSÕES
# ------------------------------------------------

is_admin = st.session_state.nivel == "admin"
is_pcp = st.session_state.nivel == "pcp"
is_operador = st.session_state.nivel == "operador"


# ------------------------------------------------
# BANCO
# ------------------------------------------------

criar_tabela()


# ------------------------------------------------
# CARREGAR DADOS
# ------------------------------------------------

def carregar():

    df = carregar_dados()

    if df.empty:
        return df

    df.columns = (
        df.columns
        .str.strip()
        .str.lower()
        .str.replace(" ", "_")
    )

    datas = [
        "inicio",
        "fim",
        "prazo_limite",
        "data_finalizado"
    ]

    for col in datas:

        if col in df.columns:

            df[col] = pd.to_datetime(
                df[col],
                errors="coerce"
            )

    return df


df = carregar()


# ------------------------------------------------
# SIDEBAR
# ------------------------------------------------

st.sidebar.title("Programação Laser")

st.sidebar.markdown("---")

st.sidebar.write("👤 **Usuário:**", st.session_state.usuario)
st.sidebar.write("🔑 **Perfil:**", st.session_state.nivel.upper())

if st.sidebar.button("🚪 Sair"):

    st.session_state.logado = False
    st.session_state.usuario = None
    st.session_state.nivel = None

    st.rerun()

st.sidebar.markdown("---")


# ------------------------------------------------
# NOVA PROGRAMAÇÃO
# ------------------------------------------------

if is_admin or is_pcp:

    st.sidebar.subheader("Nova programação")

    with st.sidebar.form("nova_op"):

        operadores = carregar_operadores()

        operador = st.selectbox(
            "Operador",
            operadores["nome"]
            if not operadores.empty
            else []
        )

        produto = st.text_input("Produto")

        quantidade = st.number_input(
            "Quantidade",
            min_value=1
        )

        inicio = st.date_input("Início")
        fim = st.date_input("Fim")
        prazo = st.date_input("Prazo limite")

        status = st.selectbox(
            "Status",
            [
                "Programado",
                "Em produção",
                "Finalizado"
            ]
        )

        desenho = st.file_uploader(
            "Desenho",
            type=["png", "jpg", "jpeg", "pdf"]
        )

        salvar = st.form_submit_button("Salvar")

        if salvar:

            nome_arquivo = None
            desenho_bytes = None

            if desenho:

                timestamp = datetime.now().timestamp()

                if desenho.type == "application/pdf":

                    pdf = fitz.open(
                        stream=desenho.read(),
                        filetype="pdf"
                    )

                    pagina = pdf.load_page(0)
                    pix = pagina.get_pixmap()

                    img_bytes = pix.tobytes("png")

                    img = Image.open(
                        io.BytesIO(img_bytes)
                    )

                    buffer = io.BytesIO()

                    img.save(
                        buffer,
                        format="JPEG"
                    )

                    desenho_bytes = buffer.getvalue()

                    nome_arquivo = (
                        f"{produto}_{timestamp}.jpg"
                    )

                else:

                    desenho_bytes = desenho.read()

                    nome_arquivo = (
                        f"{produto}_{timestamp}.png"
                    )

            nova = dict(

                produto=produto,
                quantidade=quantidade,
                operador=operador,
                inicio=str(inicio),
                fim=str(fim),
                prazo_limite=str(prazo),
                status=status,
                desenho=desenho_bytes,
                nome_desenho=nome_arquivo,
                data_finalizado=None
            )

            salvar_programacao(nova)

            st.success("Programação criada")

            st.rerun()


# ------------------------------------------------
# GERENCIAR OPERADORES
# ------------------------------------------------

if is_admin or is_pcp:

    st.sidebar.markdown("---")

    st.sidebar.subheader("Operadores")

    novo = st.sidebar.text_input(
        "Novo operador"
    )

    if st.sidebar.button(
        "Adicionar operador"
    ):

        if novo:

            adicionar_operador(novo)

            st.rerun()

    ops = carregar_operadores()

    if not ops.empty:

        remover = st.sidebar.selectbox(
            "Remover operador",
            ops["nome"]
        )

        if st.sidebar.button(
            "Remover operador"
        ):

            remover_operador(remover)

            st.rerun()


# ------------------------------------------------
# FILTROS
# ------------------------------------------------

st.sidebar.markdown("---")

st.sidebar.subheader("Filtros")

maquina = st.sidebar.selectbox(

    "Operador",

    ["Todos"]
    + list(
        df["operador"].dropna().unique()
    )
    if not df.empty
    else ["Todos"]
)

status = st.sidebar.selectbox(

    "Status",

    ["Todos"]
    + list(
        df["status"].dropna().unique()
    )
    if not df.empty
    else ["Todos"]
)


df_filtrado = filtrar_dados(
    df,
    maquina,
    status
)


# ------------------------------------------------
# MÉTRICAS
# ------------------------------------------------

metricas = calcular_metricas(df_filtrado)

c1, c2, c3 = st.columns(3)

c1.metric(
    "Total OPs",
    metricas["total_ops"]
)

c2.metric(
    "Operadores ativos",
    metricas["maquinas_ocupadas"]
)

c3.metric(
    "Próxima máquina",
    metricas["proxima_maquina"]
)


st.divider()


# ------------------------------------------------
# TABELA
# ------------------------------------------------

st.subheader("Programação")

df_ativos = df_filtrado[
    df_filtrado["status"]
    != "Finalizado"
]

if not df_ativos.empty:

    tabela = df_ativos.copy()

    if is_operador:

        tabela = tabela[
            [
                "produto",
                "quantidade",
                "operador",
                "status"
            ]
        ]

    else:

        tabela = tabela[
            [
                "produto",
                "quantidade",
                "operador",
                "inicio",
                "fim",
                "prazo_limite",
                "status"
            ]
        ]

    st.dataframe(
        tabela,
        use_container_width=True,
        hide_index=True
    )

else:

    st.info(
        "Nenhuma programação ativa"
    )


# ------------------------------------------------
# GANTT
# ------------------------------------------------

st.divider()

if not df_ativos.empty:

    df_grafico = df_ativos.copy()

    cores = {

        "Programado": "#f1c40f",
        "Em produção": "#2ecc71",
        "Finalizado": "#95a5a6"
    }

    fig = grafico_gantt(
        df_grafico,
        cores
    )

    st.plotly_chart(
        fig,
        use_container_width=True
    )


# ------------------------------------------------
# HISTÓRICO
# ------------------------------------------------

st.divider()

st.subheader(
    "Histórico"
)

df_finalizados = df_filtrado[
    df_filtrado["status"]
    == "Finalizado"
]

if not df_finalizados.empty:

    hist = df_finalizados.copy()

    hist["inicio"] = hist["inicio"].dt.date
    hist["fim"] = hist["fim"].dt.date
    hist["prazo_limite"] = hist["prazo_limite"].dt.date
    hist["data_finalizado"] = hist["data_finalizado"].dt.date

    st.dataframe(

        hist[
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

    st.info(
        "Nenhuma finalizada"
    )