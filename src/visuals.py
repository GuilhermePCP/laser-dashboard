import plotly.express as px
import plotly.graph_objects as go
import pandas as pd

def grafico_gantt(df):

    if df.empty:
        return go.Figure()

    df = df.copy()
    df["Inicio"] = pd.to_datetime(df["Inicio"])
    df["Fim"] = pd.to_datetime(df["Fim"])

    # Ordenar máquinas
    df = df.sort_values(by=["Operador", "Inicio"])

    # TEXTO BONITO DENTRO DA BARRA
    df["Texto"] = (
        df["Produto"].astype(str) +
        "<br>" +
        df["Inicio"].dt.strftime("%d/%m") +
        " → " +
        df["Fim"].dt.strftime("%d/%m")
    )

    fig = px.timeline(
        df,
        x_start="Inicio",
        x_end="Fim",
        y="Operador",
        color="Status",
        text="Texto",  # ← TEM VÍRGULA AQUI
        hover_data={
            "Inicio": "|%d/%m/%Y",
            "Fim": "|%d/%m/%Y"
        },
        color_discrete_map={
            "Programado": "#4C78A8",
            "Em produção": "#F58518",
            "Finalizado": "#54A24B"
        }
    )

    # 🔥 TEXTO GRANDE + CONTORNO BRANCO
    fig.update_traces(
        textposition="inside",
        insidetextanchor="middle",
        textfont=dict(
            size=16,
            color="white",
            family="Arial Black"
        ),
        marker_line_color="white",
        marker_line_width=2,
        cliponaxis=False
    )

    # Layout premium industrial
    fig.update_layout(
        template="plotly_dark",
        plot_bgcolor="#0E1117",
        paper_bgcolor="#0E1117",
        font=dict(color="white", size=14),
        xaxis_title="Período",
        yaxis_title="Operador",
        title={
            "text": "Programação das Máquinas Laser",
            "x": 0.02,
            "xanchor": "left",
            "font": dict(size=22)
        },
        legend_title="Status",
        hoverlabel=dict(
            bgcolor="black",
            font_size=14,
            font_family="Arial"
        ),
        uniformtext_minsize=12,
        uniformtext_mode="show",   # força mostrar texto
        bargap=0.25,
        height=650,
        margin=dict(l=40, r=40, t=70, b=40)
    )

    # Grid suave
    fig.update_xaxes(
        showgrid=True,
        gridcolor="rgba(255,255,255,0.05)"
    )

    # Inverter eixo Y (estilo cronograma industrial)
    fig.update_yaxes(autorange="reversed")

    # 🔴 Linha vertical mostrando HOJE
    hoje = pd.Timestamp.today().normalize()

    fig.add_vline(
        x=hoje,
        line_width=2,
        line_dash="dash",
        line_color="red"
    )

    fig.add_annotation(
        x=hoje,
        y=1,
        yref="paper",
        text="HOJE",
        showarrow=False,
        font=dict(color="red", size=12),
        bgcolor="rgba(0,0,0,0.6)"
    )

    fig.update_xaxes(
        tickformat="%d/%m/%Y"
    )

    return fig