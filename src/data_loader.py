import pandas as pd

def carregar_dados(caminho):

    df = pd.read_excel(caminho)

    # 🔥 Garantir colunas obrigatórias
    colunas_necessarias = [
        "Produto",
        "Operador",
        "Inicio",
        "Fim",
        "Prazo Limite",
        "Status",
        "Data Finalizado"
    ]

    for coluna in colunas_necessarias:
        if coluna not in df.columns:
            df[coluna] = None

    # 🔥 Converter datas corretamente
    df["Inicio"] = pd.to_datetime(df["Inicio"], errors="coerce")
    df["Fim"] = pd.to_datetime(df["Fim"], errors="coerce")
    df["Prazo Limite"] = pd.to_datetime(df["Prazo Limite"], errors="coerce")
    df["Data Finalizado"] = pd.to_datetime(df["Data Finalizado"], errors="coerce")

    return df