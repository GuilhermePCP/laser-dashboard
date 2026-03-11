import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import streamlit as st
import pandas as pd
import base64
from datetime import datetime
from PIL import Image

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
import fitz
import io
import plotly.express as px


UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# -------------------------------------------------
# CONFIGURAÇÃO DA PÁGINA
# -------------------------------------------------

st.set_page_config(
    page_title="Programação Laser",
    layout="wide"
)

# -------------------------------------------------
# SISTEMA DE LOGIN
# -------------------------------------------------

def verificar_login(usuario, senha):

    try:

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

    except:
        return None


# estado da sessão
if "logado" not in st.session_state:
    st.session_state.logado = False

if "nivel" not in st.session_state:
    st.session_state.nivel = None

is_admin = st.session_state.nivel == "admin"
is_pcp = st.session_state.nivel == "pcp"
is_operador = st.session_state.nivel == "operador"

# tela de login
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
# KPIs
# -------------------------------------------------

st.subheader("📊 Visão geral da produção")

metricas = calcular_metricas(df)

# -------------------------
# STATUS DA PRODUÇÃO
# -------------------------

programadas = len(df[df["status"] == "Programado"])
em_producao = len(df[df["status"] == "Em produção"])
finalizadas = len(df[df["status"] == "Finalizado"])

atrasadas = len(
    df[
        (df["status"] != "Finalizado") &
        (pd.to_datetime(df["prazo_limite"]) < pd.Timestamp.today())
    ]
)



c1, c2, c3, c4 = st.columns(4)

c1.metric("🟡 Programadas", programadas)
c2.metric("🟢 Em produção", em_producao)
c3.metric("⚪ Finalizadas", finalizadas)
c4.metric("📦 Total OPs", metricas["total_ops"])

# -------------------------------------------------
# ALERTA DE ATRASOS
# -------------------------------------------------

df_atrasadas = df[
    (df["status"] != "Finalizado") &
    (pd.to_datetime(df["prazo_limite"]) < pd.Timestamp.today())
]

atrasadas = len(df_atrasadas)

if atrasadas > 0:

    with st.expander(f"🔴 {atrasadas} OP(s) atrasada(s) — clique para ver"):

        df_alerta = df_atrasadas.copy()

        df_alerta["prazo_limite"] = pd.to_datetime(
            df_alerta["prazo_limite"], errors="coerce"
        ).dt.strftime("%d/%m/%Y")

        df_alerta = df_alerta.rename(columns={
            "produto": "Produto",
            "operador": "Operador",
            "quantidade": "Quantidade",
            "prazo_limite": "Prazo limite"
        })

        st.dataframe(
            df_alerta[
                [
                    "Produto",
                    "Quantidade",
                    "Operador",
                    "Prazo limite"
                ]
            ],
            use_container_width=True,
            hide_index=True
        )

else:

    st.caption("🟢 Nenhuma OP atrasada")

# -------------------------
# VISÃO OPERACIONAL
# -------------------------

c5, c6 = st.columns(2)

c5.metric("⚙ Operadores ativos", metricas["maquinas_ocupadas"])
c6.metric("➡ Próxima máquina", metricas["proxima_maquina"])


st.divider()

# -------------------------------------------------
# USUÁRIO LOGADO
# -------------------------------------------------

st.sidebar.image("assets/logo2.png", use_container_width=True)

st.sidebar.markdown("---")

st.sidebar.markdown("### 👤 Usuário logado")

st.sidebar.write(f"**Nome:** {st.session_state.usuario}")

st.sidebar.write(f"**Função:** {st.session_state.nivel.upper()}")

st.sidebar.markdown("---")

# -------------------------------------------------
# BOTÃO LOGOUT
# -------------------------------------------------

if st.sidebar.button("🚪 Sair"):
    st.session_state.logado = False
    st.rerun()

# -------------------------------------------------
# SIDEBAR NOVA PROGRAMAÇÃO
# -------------------------------------------------

if st.session_state.nivel in ["admin", "pcp"]:

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

        inicio = st.date_input(
            "Início",
            format="DD/MM/YYYY"
        )

        fim = st.date_input(
            "Fim",
            format="DD/MM/YYYY"
        )

        prazo = st.date_input(
            "Prazo limite",
            format="DD/MM/YYYY"
        )

        status = st.selectbox(
            "Status",
            ["Programado","Em produção","Finalizado"]
        )

        desenho = st.file_uploader(
            "Desenho da peça (PNG, JPG ou PDF)",
            type=["png","jpg","jpeg","pdf"]
        )

        # ✅ BOTÃO TEM QUE FICAR DENTRO DO FORM
        salvar = st.form_submit_button("Salvar")


    # ------------------------------------------
    # AQUI FICA FORA DO FORM
    # ------------------------------------------

    if salvar:

        nome_arquivo = None
        caminho_desenho = None

        if desenho is not None:

            timestamp = int(datetime.now().timestamp())

            # -------------------------------------------------
            # SE FOR PDF → CONVERTER PARA IMAGEM
            # -------------------------------------------------

            if desenho.type == "application/pdf":

                pdf = fitz.open(stream=desenho.read(), filetype="pdf")

                pagina = pdf.load_page(0)  # primeira página

                pix = pagina.get_pixmap()

                nome_arquivo = f"{produto}_{timestamp}.png"
                caminho_desenho = os.path.join(UPLOAD_DIR, nome_arquivo)

                pix.save(caminho_desenho)

            # -------------------------------------------------
            # SE FOR IMAGEM NORMAL
            # -------------------------------------------------

            else:

                extensao = desenho.name.split(".")[-1]

                nome_arquivo = f"{produto}_{timestamp}.{extensao}"
                caminho_desenho = os.path.join(UPLOAD_DIR, nome_arquivo)

                with open(caminho_desenho, "wb") as f:
                    f.write(desenho.read())

            df_nova = pd.DataFrame({
                "operador": [operador],
                "produto": [produto],
                "quantidade": [quantidade],
                "inicio": [inicio],
                "fim": [fim],
                "prazo_limite": [prazo],
                "status": [status],
                "caminho_desenho": [caminho_desenho],
                "nome_arquivo": [nome_arquivo]
            })

            salvar_programacao(df_nova)

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

else:

    # operador ainda consegue usar filtros simples
    maquina = "Todas"
    status = "Todos"

df_filtrado = filtrar_dados(df, maquina, status)

df_ativos = df_filtrado[df_filtrado["status"] != "Finalizado"]
df_finalizados = df_filtrado[df_filtrado["status"] == "Finalizado"]

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

            # -------------------------
            # CONTROLE DE COLUNAS POR NÍVEL
            # -------------------------

            colunas_base = [
                "id",
                "produto",
                "quantidade",
                "operador",
                "status",
                "caminho_desenho"
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

            df_exibicao = df_operador.drop(columns=["caminho_desenho"], errors="ignore")

            df_exibicao = df_exibicao.rename(columns={
                "id": "ID",
                "produto": "Produto",
                "quantidade": "Quantidade",
                "operador": "Operador",
                "status": "Status",
                "inicio": "Início",
                "fim": "Fim",
                "prazo_limite": "Prazo"
            })

            # -------------------------
            # ORDENAR PELO MAIS RECENTE
            # -------------------------

            df_exibicao = df_exibicao.sort_values("Início", ascending=True)

            tabela = st.dataframe(
                df_exibicao,
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

                col1, col2 = st.columns([2,1])

                # -------------------------
                # TITULOS
                # -------------------------

                # -------------------------
                # CONTEÚDO
                # -------------------------

                col1, col2 = st.columns([2,1])


                # -------------------------
                # IMAGEM
                # -------------------------

                with col1:

                    linha = df_operador.iloc[index]
                    caminho = linha["caminho_desenho"]

                    if caminho and os.path.exists(caminho):

                        st.image(caminho, use_container_width=True)

                    else:

                        st.info("Sem desenho para essa OP")


                # -------------------------
                # CONTROLE DA PRODUÇÃO
                # -------------------------

                with col2:

                    status = linha["status"]

                    with st.container(border=True):

                        st.subheader("⚙ Controle da OP")

                        st.write(f"**Produto:** {linha['produto']}")
                        st.write(f"**Quantidade:** {linha['quantidade']}")
                        st.write(f"**Operador:** {linha['operador']}")

                        cores = {
                            "Programado": "🟡 Programado",
                            "Em produção": "🟢 Em produção",
                            "Parado": "🟠 Parado",
                            "Finalizado": "⚪ Finalizado"
                        }

                        st.write(f"**Status:** {cores.get(status, status)}")

                        st.divider()

                        # -------------------------
                        # BOTÕES DE PRODUÇÃO
                        # -------------------------

                        if status == "🟡 Programado":

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

                                st.success("Produção iniciada")
                                st.rerun()

                        elif status == "🟢 Em produção":

                            col_pause, col_finish = st.columns(2)

                            with col_pause:

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

                                    st.warning("Produção pausada")
                                    st.rerun()

                            with col_finish:

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

                                    st.success("Produção finalizada")
                                    st.rerun()

                        elif status == "🟠 Parado":

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

                                st.success("Produção retomada")
                                st.rerun()
                        
                        # -------------------------
                        # EXCLUIR OP
                        # -------------------------

                        if st.button(
                            "🗑 Excluir OP",
                            use_container_width=True,
                            key=f"excluir_{linha['id']}"
                        ):

                            st.session_state[f"confirmar_delete_{linha['id']}"] = True


                        if st.session_state.get(f"confirmar_delete_{linha['id']}", False):

                            st.warning("⚠️ Tem certeza que deseja excluir esta OP? Esta ação não pode ser desfeita.")

                            col_confirmar, col_cancelar = st.columns(2)

                            with col1:
                                if st.button(
                                    "✅ Sim, excluir",
                                    use_container_width=True,
                                    key=f"confirmar_{linha['id']}"
                                ):

                                    query = "DELETE FROM programacao WHERE id = :id"

                                    with engine.begin() as conn:
                                        conn.execute(
                                            text(query),
                                            {"id": int(linha["id"])}
                                        )

                                    st.success("OP excluída com sucesso")

                                    st.session_state[f"confirmar_delete_{linha['id']}"] = False
                                    st.rerun()

                            with col2:
                                if st.button(
                                    "❌ Cancelar",
                                    use_container_width=True,
                                    key=f"cancelar_{linha['id']}"
                                ):

                                    st.session_state[f"confirmar_delete_{linha['id']}"] = False
                                    st.rerun()

                        # -------------------------
                        # EDITAR OP
                        # -------------------------

                        if st.session_state.nivel in ["admin", "pcp"]:

                            with st.expander("✏️ Editar OP"):

                                novo_produto = st.text_input(
                                    "Produto",
                                    value=linha["produto"],
                                    key=f"produto_{operador}_{linha['id']}"
                                )

                                nova_quantidade = st.number_input(
                                    "Quantidade",
                                    min_value=1,
                                    step=1,
                                    value=int(linha["quantidade"]),
                                    key=f"quantidade_{operador}_{linha['id']}"
                                )

                                nova_inicio = st.date_input(
                                    "Início",
                                    pd.to_datetime(linha["inicio"]),
                                    format="DD/MM/YYYY",
                                    key=f"inicio_{operador}_{linha['id']}"
                                )

                                novo_fim = st.date_input(
                                    "Fim",
                                    pd.to_datetime(linha["fim"]),
                                    format="DD/MM/YYYY",
                                    key=f"fim_{operador}_{linha['id']}"
                                )

                                novo_prazo = st.date_input(
                                    "Prazo limite",
                                    pd.to_datetime(linha["prazo_limite"]),
                                    format="DD/MM/YYYY",
                                    key=f"prazo_{operador}_{linha['id']}"
                                )

                                if st.button(
                                    "💾 Salvar alterações",
                                    use_container_width=True,
                                    key=f"salvar_op_{operador}_{linha['id']}"
                                ):

                                    query = """
                                    UPDATE programacao
                                    SET produto = :produto,
                                        quantidade = :quantidade,
                                        inicio = :inicio,
                                        fim = :fim,
                                        prazo_limite = :prazo
                                    WHERE id = :id
                                    """

                                    with engine.begin() as conn:
                                        conn.execute(
                                            text(query),
                                            {
                                                "produto": novo_produto,
                                                "quantidade": nova_quantidade,
                                                "inicio": nova_inicio,
                                                "fim": novo_fim,
                                                "prazo": novo_prazo,
                                                "id": int(linha["id"])
                                            }
                                        )

                                    st.success("OP atualizada com sucesso")
                                    st.rerun()
                        

# -------------------------------------------------
# FILTRAR APENAS PRODUÇÃO ATIVA
# -------------------------------------------------

df_producao = df_filtrado[df_filtrado["status"] != "Finalizado"]


# -------------------------------------------------
# KANBAN DE PRODUÇÃO (VISUAL MELHORADO)
# -------------------------------------------------

st.divider()

st.subheader("📋 Kanban de produção")

operadores = df_producao["operador"].unique()

cols = st.columns(len(operadores))

status_cores = {
    "Programado": "🟡",
    "Em produção": "🟢",
    "Parado": "🟠"
}

for i, operador in enumerate(operadores):

    with cols[i]:

        df_op = df_producao[df_producao["operador"] == operador]

        ordem_status = {
            "Em produção": 0,
            "Parado": 1,
            "Programado": 2
        }

        df_op["ordem_status"] = df_op["status"].map(ordem_status)

        df_op = df_op.sort_values(["ordem_status", "inicio"])

        # Caixa principal do operador
        with st.container(border=True):

            st.markdown(f"### ⚙ {operador}")
            st.caption(f"{len(df_op)} OP(s) programadas")
            st.caption(f"📦 {int(df_op['quantidade'].sum())} peças totais")

            st.divider()

            for _, row in df_op.iterrows():

                inicio = pd.to_datetime(row["inicio"]).strftime("%d/%m")
                fim = pd.to_datetime(row["fim"]).strftime("%d/%m")

                with st.container(border=True):

                    st.write(f"**{row['produto']}**")

                    st.write(f"📦 Quantidade: {int(row['quantidade'])}")

                    st.caption(f"{inicio} → {fim}")

                    status_icon = status_cores.get(row["status"], "")

                    if row["status"] == "Em produção":
                        st.success(f"{status_icon} {row['status']}")
                    elif row["status"] == "Parado":
                        st.warning(f"{status_icon} {row['status']}")
                    else:
                        st.write(f"{status_icon} {row['status']}")


# -------------------------------------------------
# MINI GANTT (VISÃO GERAL)
# -------------------------------------------------

st.divider()

st.subheader("📊 Linha do tempo da produção")

df_gantt = df_producao.copy()

df_gantt["inicio"] = pd.to_datetime(df_gantt["inicio"])
df_gantt["fim"] = pd.to_datetime(df_gantt["fim"])

cores_status = {
    "Programado": "#f1c40f",
    "Em produção": "#2ecc71",
    "Parado": "#e67e22"
}

fig = px.timeline(
    df_gantt,
    x_start="inicio",
    x_end="fim",
    y="operador",
    color="status",
    color_discrete_map=cores_status,
    text=df_gantt["produto"] + " • " + df_gantt["quantidade"].astype(int).astype(str)
)

fig.update_traces(
    textposition="inside",
    insidetextanchor="middle",
    textfont=dict(
        color="black",
        size=12,
        family="Arial Black"
    ),
    width=0.35,
    marker=dict(
        line=dict(
            color="white",
            width=2
        )
    )
)

fig.update_layout(
    height=380,
    showlegend=True,
    margin=dict(l=20, r=20, t=20, b=20),
    xaxis_title="Data",
    yaxis_title="Operador",
    plot_bgcolor="#0e1117",
    paper_bgcolor="#0e1117"
)

st.plotly_chart(fig, use_container_width=True)

# -------------------------------------------------
# HISTÓRICO
# -------------------------------------------------

st.divider()
st.subheader("📚 Programações finalizadas")

if not df_finalizados.empty:

    df_hist = df_finalizados.copy()

    # -------------------------
    # FORMATAÇÃO DE DATAS
    # -------------------------

    df_hist["inicio"] = pd.to_datetime(df_hist["inicio"], errors="coerce").dt.strftime("%d/%m/%Y")
    df_hist["fim"] = pd.to_datetime(df_hist["fim"], errors="coerce").dt.strftime("%d/%m/%Y")
    df_hist["prazo_limite"] = pd.to_datetime(df_hist["prazo_limite"], errors="coerce").dt.strftime("%d/%m/%Y")
    df_hist["data_finalizado"] = pd.to_datetime(df_hist["data_finalizado"], errors="coerce").dt.strftime("%d/%m/%Y")

    # -------------------------
    # RENOMEAR COLUNAS
    # -------------------------

    df_hist = df_hist.rename(columns={
        "produto": "Produto",
        "quantidade": "Quantidade",
        "operador": "Operador",
        "inicio": "Início",
        "fim": "Fim",
        "prazo_limite": "Prazo limite",
        "data_finalizado": "Finalizado em"
    })

    # -------------------------
    # ORDENAR PELO MAIS RECENTE
    # -------------------------

    df_hist = df_hist.sort_values("Finalizado em", ascending=False)

    # -------------------------
    # MOSTRAR TABELA
    # -------------------------

    st.dataframe(
        df_hist[
            [
                "Produto",
                "Quantidade",
                "Operador",
                "Início",
                "Fim",
                "Prazo limite",
                "Finalizado em"
            ]
        ],
        use_container_width=True,
        hide_index=True
    )

else:

    st.info("Nenhuma programação finalizada ainda")