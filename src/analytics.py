import pandas as pd
from datetime import datetime

def calcular_metricas(df):

    if not df.empty:
        df["Inicio"] = pd.to_datetime(df["Inicio"], errors="coerce")
        df["Fim"] = pd.to_datetime(df["Fim"], errors="coerce")
        df["Prazo Limite"] = pd.to_datetime(df["Prazo Limite"], errors="coerce")

    hoje = pd.Timestamp.today()


def filtrar_dados(df, operador, status):

    df_filtrado = df.copy()

    if operador != "Todas":
        df_filtrado = df_filtrado[df_filtrado["Operador"] == operador]

    if status != "Todos":
        df_filtrado = df_filtrado[df_filtrado["Status"] == status]

    return df_filtrado


def calcular_metricas(df):

    total_ops = len(df)

    # Operadores em produção
    operadores_ocupados = (
        df[df["Status"] == "Em produção"]["Operador"]
        .nunique()
    )

    hoje = pd.Timestamp(datetime.today().date())

    proximas = df[df["Inicio"] > hoje].sort_values("Inicio")

    if not proximas.empty:
        proximo_operador = proximas.iloc[0]["Operador"]
    else:
        proximo_operador = "Nenhum"

    return {
        "total_ops": total_ops,
        "maquinas_ocupadas": operadores_ocupados,
        "proxima_maquina": proximo_operador
    }