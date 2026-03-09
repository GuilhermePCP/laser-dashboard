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

    # -----------------------------
    # UPLOAD DO DESENHO
    # -----------------------------

    desenho = st.file_uploader(
        "Desenho da peça (PNG ou JPG)",
        type=["png","jpg","jpeg"]
    )

    salvar = st.form_submit_button("Salvar")

    if salvar:

        nome_arquivo = None

        if desenho is not None:

            os.makedirs("desenhos", exist_ok=True)

            nome_arquivo = f"{produto}_{datetime.now().timestamp()}.png"

            caminho = os.path.join("desenhos", nome_arquivo)

            with open(caminho, "wb") as f:
                f.write(desenho.getbuffer())

        nova = dict(
            produto=produto,
            quantidade=quantidade,
            operador=operador,
            inicio=str(inicio),
            fim=str(fim),
            prazo_limite=str(prazo),
            status=status,
            desenho=nome_arquivo,
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

            # guardar coluna desenho
            desenhos = df_operador["desenho"]

            # remover da tabela
            df_operador = df_operador.drop(columns=["desenho"], errors="ignore")

            # -------------------------
            # ORDEM DAS COLUNAS
            # -------------------------

            df_operador = df_operador[
                [
                    "id",
                    "produto",
                    "quantidade",
                    "operador",
                    "status",
                    "inicio",
                    "fim",
                    "prazo_limite",
                ]
            ]

            # formatar datas
            df_operador["inicio"] = df_operador["inicio"].dt.strftime("%d/%m/%Y")
            df_operador["fim"] = df_operador["fim"].dt.strftime("%d/%m/%Y")
            df_operador["prazo_limite"] = df_operador["prazo_limite"].dt.strftime("%d/%m/%Y")

            # -------------------------
            # FUNÇÃO DE COR DO STATUS
            # -------------------------

            # -------------------------
            # BOLINHA DE STATUS
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

                with st.expander("📅 Ajustar cronograma"):

                    nova_inicio = st.date_input(
                        "Data início",
                        pd.to_datetime(linha["inicio"]),
                        key=f"inicio_{linha['id']}"
                    )

                    novo_fim = st.date_input(
                        "Data fim",
                        pd.to_datetime(linha["fim"]),
                        key=f"fim_{linha['id']}"
                    )

                    novo_prazo = st.date_input(
                        "Prazo limite",
                        pd.to_datetime(linha["prazo_limite"]),
                        key=f"prazo_{linha['id']}"
                    )

                    if st.button("💾 Salvar novas datas", key=f"editar_datas_{linha['id']}"):

                        query = """
                        UPDATE programacao
                        SET inicio = :inicio,
                            fim = :fim,
                            prazo_limite = :prazo
                        WHERE id = :id
                        """

                        with engine.connect() as conn:
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

                    st.markdown(
                        """
                        <div style="
                            background-color:#1e1e1e;
                            padding:20px;
                            border-radius:12px;
                            border:1px solid #333;
                        ">
                        """,
                        unsafe_allow_html=True
                    )

                    st.markdown("### ⚙ Controle da OP")

                    st.write(f"**Produto:** {linha['produto']}")
                    st.write(f"**Quantidade:** {linha['quantidade']}")
                    st.write(f"**Operador:** {linha['operador']}")
                    st.write(f"**Status:** {linha['status']}")

                    st.write("")

                    status = linha["status"]

                    if status == "Programado":

                        if st.button("▶ Iniciar", use_container_width=True, key=f"iniciar_{linha['id']}"):
                            atualizar_status()

                    elif status == "Em produção":

                        col1, col2 = st.columns(2)

                        with col1:
                            if st.button("⏸ Pausar", use_container_width=True, key=f"pausar_{linha['id']}"):
                                pausar()

                        with col2:
                            if st.button("✔ Finalizar", use_container_width=True, key=f"finalizar_{linha['id']}"):
                                finalizar()

                    elif status == "Parado":

                        if st.button("▶ Retomar", use_container_width=True, key=f"retomar_{linha['id']}"):
                            retomar()

                    with st.expander("📅 Ajustar cronograma"):

                        nova_inicio = st.date_input(
                            "Início",
                            pd.to_datetime(linha["inicio"]),
                            key=f"inicio_{linha['id']}"
                        )

                        novo_fim = st.date_input(
                            "Fim",
                            pd.to_datetime(linha["fim"]),
                            key=f"fim_{linha['id']}"
                        )

                        novo_prazo = st.date_input(
                            "Prazo limite",
                            pd.to_datetime(linha["prazo_limite"]),
                            key=f"prazo_{linha['id']}"
                        )

                        if st.button("💾 Salvar datas", use_container_width=True):

                            query = """
                            UPDATE programacao
                            SET inicio = :inicio,
                                fim = :fim,
                                prazo_limite = :prazo
                            WHERE id = :id
                            """

                            with engine.connect() as conn:
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

                        st.markdown("</div>", unsafe_allow_html=True)

                    # -------------------------
                    # BOTÕES DINÂMICOS
                    # -------------------------

                    status = linha["status"]

                    # -------------------------
                    # PROGRAMADO → INICIAR
                    # -------------------------

                    if status == "Programado":

                        if st.button("▶ Iniciar produção", key=f"iniciar_{linha['id']}"):

                            query = """
                            UPDATE programacao
                            SET status = :status
                            WHERE id = :id
                            """

                            with engine.connect() as conn:
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


                    # -------------------------
                    # EM PRODUÇÃO → PAUSAR / FINALIZAR
                    # -------------------------

                    elif status == "Em produção":

                        col1, col2 = st.columns(2)

                        with col1:

                            if st.button("⏸ Pausar produção", key=f"pausar_{linha['id']}"):

                                query = """
                                UPDATE programacao
                                SET status = :status
                                WHERE id = :id
                                """

                                with engine.connect() as conn:
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

                        with col2:

                            if st.button("✅ Finalizar produção", key=f"finalizar_{linha['id']}"):

                                query = """
                                UPDATE programacao
                                SET status = :status,
                                    data_finalizado = :data
                                WHERE id = :id
                                """

                                with engine.connect() as conn:
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


                    # -------------------------
                    # PARADO → RETOMAR
                    # -------------------------

                    elif status == "Parado":

                        if st.button("▶ Retomar produção", key=f"retomar_{linha['id']}"):

                            query = """
                            UPDATE programacao
                            SET status = :status
                            WHERE id = :id
                            """

                            with engine.connect() as conn:
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