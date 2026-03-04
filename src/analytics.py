import pandas as pd
from datetime import datetime


def filtrar_dados(df, operador, status):

    df_filtrado = df.copy()

    if operador != "Todas":
        df_filtrado = df_filtrado[df_filtrado["operador"] == operador]

    if status != "Todos":
        df_filtrado = df_filtrado[df_filtrado["status"] == status]

    return df_filtrado


def calcular_metricas(df):

    if df.empty:
        return {
            "total_ops": 0,
            "maquinas_ocupadas": 0,
            "proxima_maquina": "Nenhum"
        }


    total_ops = len(df)

    # Operadores em produção
    operadores_ocupados = (
        df[df["status"] == "Em produção"]["operador"]
        .nunique()
    )

    hoje = pd.Timestamp(datetime.today().date())

    proximas = df[df["inicio"] > hoje].sort_values("inicio")

    if not proximas.empty:
        proximo_operador = proximas.iloc[0]["operador"]
    else:
        proximo_operador = "Nenhum"

    return {
        "total_ops": total_ops,
        "maquinas_ocupadas": operadores_ocupados,
        "proxima_maquina": proximo_operador
    }