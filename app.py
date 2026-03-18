import sys
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(BASE_DIR, "src"))

import streamlit as st
import pandas as pd
import base64
import json
from datetime import datetime
from PIL import Image

# 🔥 IMPORTS CORRETOS (COM src.)
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
import re
import unicodedata
from streamlit_cookies_manager import EncryptedCookieManager
from streamlit_autorefresh import st_autorefresh
def normalizar_texto(texto):
    if texto is None:
        return ""

    texto = str(texto)

    texto = unicodedata.normalize("NFKD", texto)
    texto = texto.encode("ASCII", "ignore").decode("utf-8")

    return texto.lower()

def nome_operador_bonito(usuario):

    operadores = carregar_operadores()

    for nome in operadores["nome"]:

        if normalizar_texto(nome) == normalizar_texto(usuario):
            return nome

    return usuario

@st.cache_data
def carregar_ops():
    return carregar_operadores()

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# -------------------------------------------------
# CONFIGURAÇÃO DA PÁGINA
# -------------------------------------------------

st.set_page_config(
    page_title="Programação Laser",
    layout="wide"
)

cookies = EncryptedCookieManager(
    prefix="laser_app",
    password="senha_super_secreta"
)

if not cookies.ready():
    st.stop()

# -------------------------------------------------
# SISTEMA DE LOGIN
# -------------------------------------------------

def verificar_login(usuario, senha):

    try:

        query = """
        SELECT usuario, senha, nivel
        FROM usuarios
        """

        with engine.begin() as conn:

            result = conn.execute(text(query)).fetchall()

        usuario_digitado = normalizar_texto(usuario)

        for row in result:

            if (
                normalizar_texto(row.usuario) == usuario_digitado
                and row.senha == senha
            ):
                return row

        return None

    except:
        return None


# estado da sessão
# estado da sessão
if "logado" not in st.session_state:

    if cookies.get("usuario"):

        st.session_state.logado = True
        st.session_state.usuario = nome_operador_bonito(cookies.get("usuario"))
        st.session_state.nivel = cookies.get("nivel")

    else:

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
            st.session_state.usuario = nome_operador_bonito(login.usuario)
            st.session_state.nivel = login.nivel

            cookies["usuario"] = login.usuario
            cookies["nivel"] = login.nivel
            cookies.save()

            st.rerun()

        else:

            st.error("Usuário ou senha inválidos")

    st.stop()

st_autorefresh(interval=60000, key="auto_refresh")

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
            df[col] = pd.to_datetime(df[col], errors="coerce", dayfirst=True)

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
if st.session_state.nivel in ["admin", "pcp"]:
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

    hoje = pd.Timestamp.today().normalize()

    df_atrasadas = df[
        (df["status"] != "Finalizado") &
        (
            pd.to_datetime(df["prazo_limite"], errors="coerce")
            .dt.normalize() < hoje
        )
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

st.sidebar.write("") #Espaço invisivel de proposito

# -------------------------------------------------
# BOTÃO LOGOUT
# -------------------------------------------------

if st.sidebar.button("🚪 Sair"):

    cookies["usuario"] = ""
    cookies["nivel"] = ""
    cookies.save()

    st.session_state.logado = False
    st.rerun()

st.sidebar.markdown("---")

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

        operador = nome_operador_bonito(operador)

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

        desenhos = st.file_uploader(
            "Desenhos da peça (pode enviar vários)",
            type=["png","jpg","jpeg","pdf"],
            accept_multiple_files=True
        )

        # ✅ BOTÃO TEM QUE FICAR DENTRO DO FORM
        salvar = st.form_submit_button("Salvar")


    # ------------------------------------------
    # AQUI FICA FORA DO FORM
    # ------------------------------------------

    if salvar:

        imagens_lista = []

        if desenhos:

            for arquivo in desenhos:

                try:
                    file_bytes = arquivo.read()

                    if not file_bytes:
                        continue

                    # 🔴 PDF
                    if arquivo.type == "application/pdf":

                        try:
                            pdf = fitz.open(stream=file_bytes, filetype="pdf")

                            for pagina in pdf:
                                pix = pagina.get_pixmap()
                                imagens_lista.append(pix.tobytes("png"))

                        except Exception as e:
                            st.warning(f"Erro no PDF: {e}")

                    # 🟢 IMAGEM
                    else:
                        imagens_lista.append(file_bytes)

                except Exception as e:
                    st.warning(f"Erro ao processar arquivo: {e}")

        df_nova = pd.DataFrame({
            "operador": [nome_operador_bonito(operador)],
            "produto": [produto],
            "quantidade": [quantidade],
            "inicio": [inicio],
            "fim": [fim],
            "prazo_limite": [prazo],
            "status": [status],
            "desenho": [
                json.dumps([
                    base64.b64encode(img).decode()
                    for img in imagens_lista
                ]) if imagens_lista else None
            ]
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

        if novo.strip():

            adicionar_operador(novo.strip())

            st.success("Operador adicionado!")
            st.rerun()

        else:
            st.warning("Digite um nome válido.")

    operadores = carregar_operadores()

    if not operadores.empty:

        remover = st.sidebar.selectbox(
            "Remover operador",
            operadores["nome"]
        )

        if st.sidebar.button("Remover operador"):
            remover_operador(remover)
            st.rerun()

    # -------------------------------------------------
    # GERENCIAR USUÁRIOS
    # -------------------------------------------------

    if st.session_state.nivel == "admin":

        st.sidebar.divider()
        st.sidebar.subheader("👤 Usuários")

        novo_usuario = st.sidebar.text_input("Usuário")

        nova_senha = st.sidebar.text_input("Senha", type="password")

        nivel_usuario = st.sidebar.selectbox(
            "Nível",
            ["admin", "pcp", "operador"]
        )

        if st.sidebar.button("Criar usuário"):

            if novo_usuario and nova_senha:

                query = """
                INSERT INTO usuarios (usuario, senha, nivel)
                VALUES (:usuario, :senha, :nivel)
                """

                with engine.begin() as conn:
                    conn.execute(
                        text(query),
                        {
                            "usuario": novo_usuario,
                            "senha": nova_senha,
                            "nivel": nivel_usuario
                        }
                    )

                st.sidebar.success("Usuário criado")

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

# -------------------------------------------------
# OPERADOR VÊ APENAS SUAS OPs
# -------------------------------------------------

if st.session_state.nivel == "operador":

    df_filtrado = df_filtrado[
        df_filtrado["operador"].apply(normalizar_texto)
        == normalizar_texto(st.session_state.usuario)
    ]

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

    if st.session_state.nivel == "operador":
        operadores = [st.session_state.usuario]
    else:
        operadores = df_tabela["operador"].unique()

    abas = st.tabs(list(operadores))

    for i, operador in enumerate(operadores):

        with abas[i]:

            df_operador = df_tabela[df_tabela["operador"] == operador].copy()

            hoje = pd.Timestamp.today().normalize()

            df_operador["atrasado"] = (
                (pd.to_datetime(df_operador["prazo_limite"], errors="coerce").dt.normalize() < hoje) &
                (df_operador["status"] != "Finalizado")
            )

            # 🔥 NÃO SOBRESCREVE STATUS REAL
            df_operador["status_original"] = df_operador["status"]

            df_operador["status_visual_base"] = df_operador.apply(
                lambda row: "Atrasado"
                if row["atrasado"] and row["status_original"] != "Finalizado"
                else row["status_original"],
                axis=1
            )

            prioridade_status = {
                "Atrasado": 0,
                "Em produção": 1,
                "Programado": 2,
                "Parado": 3,
                "Finalizado": 4
            }

            df_operador["prioridade"] = df_operador["status_visual_base"].map(prioridade_status)

            # -------------------------
            # GARANTIR SEQUÊNCIA
            # -------------------------

            if "sequencia" not in df_operador.columns:
                df_operador["sequencia"] = df_operador["id"]

            df_operador["sequencia"] = df_operador["sequencia"].fillna(df_operador["id"])

            # -------------------------
            # ORDENAR
            # -------------------------

            df_operador = df_operador.sort_values(
                ["sequencia", "prioridade", "inicio"]
            ).reset_index(drop=True)

            # -------------------------
            # CONTROLE DE COLUNAS
            # -------------------------

            colunas_base = [
                "id",
                "sequencia",
                "produto",
                "quantidade",
                "operador",
                "status",
                "desenho",
                "status_visual_base",  # 🔥 ADICIONA ISSO
                "quantidade_produzida"
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

            # 🔥 GARANTE DEPOIS DO CORTE
            if "status_original" not in df_operador.columns:
                df_operador["status_original"] = df_operador["status"]

            if "quantidade_produzida" not in df_operador.columns:
                df_operador["quantidade_produzida"] = 0

            # -------------------------
            # FORMATAR DATAS
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

            df_operador["status_visual"] = df_operador["status_visual_base"].apply(icone_status)

            # -------------------------
            # TABELA
            # -------------------------

            df_operador["Quantidade"] = df_operador.apply(
                lambda row: f"{int(row['quantidade_produzida'])} / {int(row['quantidade'])}"
                if row["status_original"] == "Parado" and row["quantidade_produzida"] > 0
                else f"{int(row['quantidade'])}",
                axis=1
            )

            df_exibicao = df_operador.drop(columns=["desenho", "status"], errors="ignore")

            df_exibicao = df_exibicao.rename(columns={
                "sequencia": "Sequência",
                "produto": "Produto",
                "operador": "Operador",
                "status_visual": "Status",
                "inicio": "Início",
                "fim": "Fim",
                "prazo_limite": "Prazo"
            })

            ordem_colunas = [
                "Sequência",
                "Produto",
                "Quantidade",
                "Operador",
                "Status",
                "Início",
                "Fim",
                "Prazo"
            ]

            df_exibicao = df_exibicao[[col for col in ordem_colunas if col in df_exibicao.columns]]

            tabela = st.dataframe(
                df_exibicao,
                use_container_width=True,
                selection_mode="single-row",
                on_select="rerun",
                hide_index=True
            )

            # -------------------------
            # SELEÇÃO
            # -------------------------

            if tabela["selection"]["rows"]:

                index = tabela["selection"]["rows"][0]
                linha = df_operador.iloc[index]

                col1, col2 = st.columns([2,1])

                # IMAGEM
                with col1:

                    imagens = linha.get("desenho")

                    if imagens and imagens != "null":

                        try:
                            try:
                                lista = json.loads(imagens)

                                if not isinstance(lista, list):
                                    lista = []

                            except:
                                # 🔥 formato antigo (imagem única em bytes)
                                lista = [base64.b64encode(imagens).decode()]

                            if not isinstance(lista, list):
                                lista = []

                            if len(lista) == 1:
                                # mostra direto
                                image_bytes = base64.b64decode(lista[0])
                                image = Image.open(io.BytesIO(image_bytes))
                                st.image(image, use_container_width=True)

                            else:
                                # 🔥 múltiplas imagens → botões
                                for i, img in enumerate(lista):

                                    with st.expander(f"📄 Desenho {i+1}"):

                                        try:
                                            image_bytes = base64.b64decode(img)
                                            image = Image.open(io.BytesIO(image_bytes))
                                            st.image(image, use_container_width=True)

                                        except Exception as e:
                                            st.warning(f"Erro imagem {i+1}: {e}")

                        except Exception as e:
                            st.warning(f"Erro ao carregar desenhos: {e}")

                    else:
                        st.info("Sem desenho para essa OP")

                # CONTROLE
                with col2:

                    status_op = linha["status"]

                    with st.container(border=True):

                        st.subheader("⚙ Controle da OP")

                        st.write(f"**Produto:** {linha['produto']}")
                        st.write(f"**Quantidade:** {int(linha['quantidade'])}")
                        st.write(f"**Operador:** {linha['operador']}")
                        st.write(f"**Sequência:** {int(linha['sequencia'])}")

                        st.divider()

                        if status_op == "Atrasado":
                            status_op = "Em produção"

                        if status_op == "Programado":

                            if st.button("▶ Iniciar produção", use_container_width=True,
                                         key=f"iniciar_{operador}_{linha['id']}"):

                                with engine.begin() as conn:
                                    conn.execute(text("""
                                        UPDATE programacao
                                        SET status = 'Em produção'
                                        WHERE id = :id
                                    """), {"id": int(linha["id"])})

                                st.rerun()

                        elif status_op == "Em produção":

                            col_pause, col_finish = st.columns(2)

                            with col_pause:

                                if st.button("⏸ Pausar", use_container_width=True,
                                            key=f"pausar_{linha['id']}"):

                                    st.session_state[f"pausando_{linha['id']}"] = True

                                if st.session_state.get(f"pausando_{linha['id']}", False):

                                    qtd_produzida = st.number_input(
                                        "Quantidade já produzida",
                                        min_value=0,
                                        max_value=int(linha["quantidade"]),
                                        step=1,
                                        value=int(linha.get("quantidade_produzida", 0)),
                                        key=f"input_qtd_{linha['id']}"
                                    )

                                    col_confirm, col_cancel = st.columns(2)

                                    with col_confirm:
                                        if st.button("💾 Confirmar pausa",
                                                    use_container_width=True,
                                                    key=f"confirmar_pausa_{linha['id']}"):

                                            with engine.begin() as conn:
                                                conn.execute(text("""
                                                    UPDATE programacao
                                                    SET status = 'Parado',
                                                        quantidade_produzida = :qtd
                                                    WHERE id = :id
                                                """), {
                                                    "id": int(linha["id"]),
                                                    "qtd": int(qtd_produzida)
                                                })

                                            st.session_state[f"pausando_{linha['id']}"] = False
                                            st.success("Quantidade salva corretamente")
                                            st.rerun()

                                    with col_cancel:
                                        if st.button("❌ Cancelar",
                                                    use_container_width=True,
                                                    key=f"cancelar_pausa_{linha['id']}"):

                                            st.session_state[f"pausando_{linha['id']}"] = False
                                            st.rerun()

                            with col_finish:
                                if st.button("✔ Finalizar", use_container_width=True,
                                             key=f"finalizar_{linha['id']}"):

                                    with engine.begin() as conn:
                                        conn.execute(text("""
                                            UPDATE programacao
                                            SET status = 'Finalizado',
                                                data_finalizado = :data
                                            WHERE id = :id
                                        """), {
                                            "id": int(linha["id"]),
                                            "data": datetime.now()
                                        })

                                    st.rerun()

                        elif status_op == "Parado":

                            if st.button("▶ Retomar produção", use_container_width=True,
                                         key=f"retomar_{linha['id']}"):

                                with engine.begin() as conn:
                                    conn.execute(text("""
                                        UPDATE programacao
                                        SET status = 'Em produção'
                                        WHERE id = :id
                                    """), {"id": int(linha["id"])})

                                st.rerun()
                        
                        # -------------------------
                        # EXCLUIR OP
                        # -------------------------
                        if st.session_state.nivel in ["admin", "pcp"]:
                            
                            if st.button(
                                "🗑 Excluir OP",
                                use_container_width=True,
                                key=f"excluir_{linha['id']}"
                            ):

                                st.session_state[f"confirmar_delete_{linha['id']}"] = True


                            if st.session_state.get(f"confirmar_delete_{linha['id']}", False):

                                st.warning("⚠️ Tem certeza que deseja excluir esta OP? Esta ação não pode ser desfeita.")

                                col_confirmar, col_cancelar = st.columns(2)

                                with col_confirmar:
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

                                with col_cancelar:
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

                                # 🔥 NOVO CAMPO SEQUÊNCIA
                                nova_sequencia = st.number_input(
                                    "Sequência",
                                    min_value=1,
                                    step=1,
                                    value=int(linha.get("sequencia", linha["id"])),
                                    key=f"seq_{operador}_{linha['id']}"
                                )

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
                                    pd.to_datetime(linha["inicio"], dayfirst=True),
                                    format="DD/MM/YYYY",
                                    key=f"inicio_{operador}_{linha['id']}"
                                )

                                novo_fim = st.date_input(
                                    "Fim",
                                    pd.to_datetime(linha["fim"], dayfirst=True),
                                    format="DD/MM/YYYY",
                                    key=f"fim_{operador}_{linha['id']}"
                                )

                                novo_prazo = st.date_input(
                                    "Prazo limite",
                                    pd.to_datetime(linha["prazo_limite"], dayfirst=True),
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
                                        prazo_limite = :prazo,
                                        sequencia = :sequencia
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
                                                "sequencia": nova_sequencia,  # 🔥 AQUI
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

if st.session_state.nivel == "operador":
    operadores = [st.session_state.usuario]
else:
    operadores = df_producao["operador"].unique()

if len(operadores) > 0:
    cols = st.columns(len(operadores))
else:
    st.info("Nenhuma OP em produção")

status_cores = {
    "Programado": "🟡",
    "Em produção": "🟢",
    "Parado": "🟠"
}

for i, operador in enumerate(operadores):

    with cols[i]:

        df_op = df_producao[df_producao["operador"] == operador].copy()

        hoje = pd.Timestamp.today().normalize()

        # detectar atrasos
        df_op["atrasado"] = (
            (pd.to_datetime(df_op["prazo_limite"], errors="coerce").dt.normalize() < hoje) &
            (df_op["status"] != "Finalizado")
        )

        # prioridade de exibição
        def prioridade(row):

            if row["atrasado"]:
                return 0
            if row["status"] == "Em produção":
                return 1
            if row["status"] == "Parado":
                return 2
            return 3

        df_op["prioridade"] = df_op.apply(prioridade, axis=1)

        # ordenar
        df_op = df_op.sort_values(["prioridade", "inicio"])

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

                    if st.session_state.nivel in ["admin", "pcp"]:
                        st.caption(f"{inicio} → {fim}")

                    # STATUS VISUAL
                    if row["atrasado"]:
                        st.error("🔴 ATRASADO")

                    elif row["status"] == "Em produção":
                        st.success("🟢 Em produção")

                    elif row["status"] == "Parado":
                        st.warning("🟠 Parado")

                    else:
                        st.write("🟡 Programado")


# -------------------------------------------------
# MINI GANTT (VISUAL MELHORADO)
# -------------------------------------------------

st.divider()

if st.session_state.nivel in ["admin", "pcp"]:
    st.subheader("📊 Linha do tempo da produção")

    if df_producao.empty:
        st.info("Nenhuma programação ativa para exibir no gráfico.")

    else:
        df_gantt = df_producao.copy()

        df_gantt["inicio"] = pd.to_datetime(df_gantt["inicio"])
        df_gantt["fim"] = pd.to_datetime(df_gantt["fim"])
        df_gantt["quantidade"] = df_gantt["quantidade"].astype(int)

        # -------------------------------------------------
        # CORREÇÃO PARA OP DE 1 DIA NÃO VIRAR TRACINHO
        # -------------------------------------------------

        df_gantt["fim_plot"] = df_gantt["fim"]

        df_gantt.loc[
            df_gantt["inicio"] == df_gantt["fim"],
            "fim_plot"
        ] = df_gantt["fim"] + pd.Timedelta(days=1)

        # -------------------------------------------------
        # DETECTAR ATRASO
        # -------------------------------------------------

        hoje = pd.Timestamp.today().normalize()

        df_gantt["atrasado"] = (
            (df_gantt["fim"].dt.normalize() < hoje) &
            (df_gantt["status"] != "Finalizado")
        )

        # status visual
        df_gantt["status_visual"] = df_gantt["status"]
        df_gantt.loc[df_gantt["atrasado"], "status_visual"] = "Atrasado"

        cores_status = {
            "Programado": "#f1c40f",
            "Em produção": "#2ecc71",
            "Parado": "#e67e22",
            "Atrasado": "#e74c3c"
        }

        fig = px.timeline(
            df_gantt,
            x_start="inicio",
            x_end="fim_plot",   # 👈 usamos a nova coluna
            y="operador",
            color="status_visual",
            color_discrete_map=cores_status,
            text=df_gantt["produto"] + " • " + df_gantt["quantidade"].astype(str)
        )

        fig.update_traces(
            textposition="inside",
            insidetextanchor="middle",
            textfont=dict(
                color="black",
                size=13,
                family="Arial Black"
            ),
            width=0.4,
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
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)"
        )

        fig.update_xaxes(
            tickfont=dict(size=12)
        )

        fig.update_xaxes(
            showgrid=True,
            gridcolor="rgba(200,200,200,0.2)",
            dtick="D1",
            tickformat="%d/%m",
            ticklabelmode="period"
        )

        fig.update_yaxes(showgrid=False)

        # -------------------------------------------------
        # LINHA DE HOJE
        # -------------------------------------------------

        hoje = pd.Timestamp.today().normalize()

        fig.add_vline(
            x=hoje,
            line_width=3,
            line_dash="dash",
            line_color="red"
        )

        fig.add_annotation(
            x=hoje,
            y=1.02,
            yref="paper",
            text="HOJE",
            showarrow=False,
            font=dict(size=12, color="red")
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

    df_hist["data_finalizado"] = pd.to_datetime(df_hist["data_finalizado"], errors="coerce")

    df_hist = df_hist.sort_values("data_finalizado", ascending=False)

    df_hist["inicio"] = pd.to_datetime(df_hist["inicio"], errors="coerce").dt.strftime("%d/%m/%Y")
    df_hist["fim"] = pd.to_datetime(df_hist["fim"], errors="coerce").dt.strftime("%d/%m/%Y")
    df_hist["prazo_limite"] = pd.to_datetime(df_hist["prazo_limite"], errors="coerce").dt.strftime("%d/%m/%Y")
    df_hist["data_finalizado"] = df_hist["data_finalizado"].dt.strftime("%d/%m/%Y")

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