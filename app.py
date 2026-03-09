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
# TABELA DE FABRICAÇÃO
# -------------------------------------------------

st.subheader("Sequência de fabricação")

df_tabela = df_ativos.copy()

if not df_tabela.empty:

    df_tabela["inicio"] = pd.to_datetime(df_tabela["inicio"], errors="coerce")
    df_tabela["fim"] = pd.to_datetime(df_tabela["fim"], errors="coerce")
    df_tabela["prazo_limite"] = pd.to_datetime(df_tabela["prazo_limite"], errors="coerce")

    operadores = df_tabela["operador"].unique()

    abas = st.tabs(list(operadores))

    for i, operador in enumerate(operadores):

        with abas[i]:

            df_operador = df_tabela[df_tabela["operador"] == operador].copy()
            df_operador = df_operador.reset_index(drop=True)

            desenhos = df_operador["desenho"]
            df_operador = df_operador.drop(columns=["desenho"], errors="ignore")

            # -------------------------
            # CONTROLE DE COLUNAS POR NÍVEL
            # -------------------------

            colunas_base = [
                "id",
                "produto",
                "quantidade",
                "operador",
                "status",
            ]

            colunas_data = [
                "inicio",
                "fim",
                "prazo_limite",
            ]

            if "nivel" not in st.session_state:
                st.session_state.nivel = None

            if st.session_state.nivel in ["admin", "pcp"]:
                df_operador = df_operador[colunas_base + colunas_data]
            else:
                df_operador = df_operador[colunas_base]

            # -------------------------

            if "inicio" in df_operador.columns:
                df_operador["inicio"] = pd.to_datetime(
                    df_operador["inicio"], errors="coerce"
                ).dt.strftime("%d/%m/%Y")

            if "fim" in df_operador.columns:
                df_operador["fim"] = pd.to_datetime(
                    df_operador["fim"], errors="coerce"
                ).dt.strftime("%d/%m/%Y")

            if "prazo_limite" in df_operador.columns:
                df_operador["prazo_limite"] = pd.to_datetime(
                    df_operador["prazo_limite"], errors="coerce"
    ).dt.strftime("%d/%m/%Y")

            # -------------------------
            # STATUS COM ÍCONE
            # -------------------------

            def icone_status(status):

                if status == "Programado":
                    return "🟡 Programado"

                elif status == "Em produção":
                    return "🟢 Em produção"

                elif status == "Finalizado":
                    return "🔵 Finalizado"

                elif status == "Atrasado":
                    return "🔴 Atrasado"

                elif status == "Parado":
                    return "🟠 Parado"

                return status

            df_operador["status"] = df_operador["status"].apply(icone_status)

            # -------------------------
            # TABELA
            # -------------------------

            tabela = st.dataframe(
                df_operador,
                use_container_width=True,
                selection_mode="single-row",
                on_select="rerun",
                hide_index=True
            )

            # -------------------------
            # SELEÇÃO DA OP
            # -------------------------

            if tabela["selection"]["rows"]:

                index = tabela["selection"]["rows"][0]

                linha = df_tabela[df_tabela["operador"] == operador].iloc[index]
                nome_img = desenhos.iloc[index]

                col1, col2 = st.columns([2,1])

                # -------------------------
                # IMAGEM
                # -------------------------

                with col1:

                    if nome_img:

                        caminho_img = os.path.join("desenhos", nome_img)

                        if os.path.exists(caminho_img):

                            st.markdown(f"### 🖼️ Desenho da peça — {linha['produto']}")

                            st.image(
                                caminho_img,
                                use_container_width=True
                            )

                        else:
                            st.warning("Imagem não encontrada")

                    else:
                        st.info("Essa OP não possui desenho")

                # -------------------------
                # CONTROLE DA PRODUÇÃO
                # -------------------------

                with col2:

                    st.markdown("### ⚙ Controle da OP")

                    st.write(f"**Produto:** {linha['produto']}")
                    st.write(f"**Quantidade:** {linha['quantidade']}")
                    st.write(f"**Operador:** {linha['operador']}")
                    st.write(f"**Status:** {linha['status']}")

                    status = linha["status"]

                    # -------------------------
                    # BOTÕES DE PRODUÇÃO
                    # -------------------------

                    if status == "Programado":

                        if st.button(
                            "▶ Iniciar produção",
                            use_container_width=True,
                            key=f"iniciar_{operador}_{linha['id']}"
                        ):

                            query = """
                            UPDATE programacao
                            SET status = :status
                            WHERE id = :id
                            """

                            with engine.begin() as conn:
                                conn.execute(
                                    text(query),
                                    {
                                        "status": "Em produção",
                                        "id": int(linha["id"])
                                    }
                                )
                                conn.commit()

                            st.success("Produção iniciada")
                            st.rerun()

                    elif status == "Em produção":

                        b1, b2 = st.columns(2)

                        with b1:

                            if st.button(
                                "⏸ Pausar",
                                use_container_width=True,
                                key=f"pausar_{operador}_{linha['id']}"
                            ):

                                query = """
                                UPDATE programacao
                                SET status = :status
                                WHERE id = :id
                                """

                                with engine.begin() as conn:
                                    conn.execute(
                                        text(query),
                                        {
                                            "status": "Parado",
                                            "id": int(linha["id"])
                                        }
                                    )
                                    conn.commit()

                                st.warning("Produção pausada")
                                st.rerun()

                        with b2:

                            if st.button(
                                "✔ Finalizar",
                                use_container_width=True,
                                key=f"finalizar_{operador}_{linha['id']}"
                            ):

                                query = """
                                UPDATE programacao
                                SET status = :status,
                                    data_finalizado = :data
                                WHERE id = :id
                                """

                                with engine.begin() as conn:
                                    conn.execute(
                                        text(query),
                                        {
                                            "status": "Finalizado",
                                            "data": datetime.now(),
                                            "id": int(linha["id"])
                                        }
                                    )
                                    conn.commit()

                                st.success("Produção finalizada")
                                st.rerun()

                    elif status == "Parado":

                        if st.button(
                            "▶ Retomar produção",
                            use_container_width=True,
                            key=f"retomar_{operador}_{linha['id']}"
                        ):

                            query = """
                            UPDATE programacao
                            SET status = :status
                            WHERE id = :id
                            """

                            with engine.begin() as conn:
                                conn.execute(
                                    text(query),
                                    {
                                        "status": "Em produção",
                                        "id": int(linha["id"])
                                    }
                                )
                                conn.commit()

                            st.success("Produção retomada")
                            st.rerun()

                    # -------------------------
                    # AJUSTE DE CRONOGRAMA
                    # -------------------------

                    if st.session_state.nivel in ["admin", "pcp"]:

                        with st.expander("📅 Ajustar cronograma"):

                            nova_inicio = st.date_input(
                                "Início",
                                pd.to_datetime(linha["inicio"]),
                                key=f"inicio_{operador}_{linha['id']}"
                            )

                            novo_fim = st.date_input(
                                "Fim",
                                pd.to_datetime(linha["fim"]),
                                key=f"fim_{operador}_{linha['id']}"
                            )

                            novo_prazo = st.date_input(
                                "Prazo limite",
                                pd.to_datetime(linha["prazo_limite"]),
                                key=f"prazo_{operador}_{linha['id']}"
                            )

                            if st.button(
                                "💾 Salvar datas",
                                use_container_width=True,
                                key=f"salvar_datas_{operador}_{linha['id']}"
                            ):

                                query = """
                                UPDATE programacao
                                SET inicio = :inicio,
                                    fim = :fim,
                                    prazo_limite = :prazo
                                WHERE id = :id
                                """

                                with engine.begin() as conn:
                                    conn.execute(
                                        text(query),
                                        {
                                            "inicio": nova_inicio,
                                            "fim": novo_fim,
                                            "prazo": novo_prazo,
                                            "id": int(linha["id"])
                                        }
                                    )
                                    conn.commit()

                                st.success("Cronograma atualizado")
                                st.rerun()

else:

    st.info("Nenhuma programação ativa")

# -------------------------------------------------
# GANTT
# -------------------------------------------------

st.divider()

df_grafico = df_ativos.copy()

df_grafico["inicio"] = pd.to_datetime(df_grafico["inicio"])
df_grafico["fim"] = pd.to_datetime(df_grafico["fim"])

# -------------------------
# CORES DOS STATUS
# -------------------------

cores_status = {
    "Programado": "#f1c40f",
    "Em produção": "#2ecc71",
    "Parado": "#e67e22",
    "Finalizado": "#95a5a6"
}
fig = grafico_gantt(
    df_grafico.sort_values("inicio"),
    cores_status
)

st.plotly_chart(fig, use_container_width=True)

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