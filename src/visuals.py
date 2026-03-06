import plotly.express as px
import plotly.graph_objects as go
import pandas as pd


def grafico_gantt(df, cores_status=None):

    if df.empty:
        return go.Figure()

    df = df.copy()

    # garantir formato das datas
    df["inicio"] = pd.to_datetime(df["inicio"], errors="coerce")
    df["fim"] = pd.to_datetime(df["fim"], errors="coerce")

    # remover linhas inválidas
    df = df.dropna(subset=["inicio", "fim"])

    # ordenar
    df = df.sort_values(by=["operador", "inicio"])

    # texto dentro da barra
    df["texto"] = (
        df["produto"].astype(str)
        + "<br>"
        + df["inicio"].dt.strftime("%d/%m")
        + " → "
        + df["fim"].dt.strftime("%d/%m")
    )

    # cores padrão caso não sejam enviadas
    if cores_status is None:
        cores_status = {
            "Programado": "#f1c40f",
            "Em produção": "#2ecc71",
            "Finalizado": "#95a5a6"
        }

    fig = px.timeline(
        df,
        x_start="inicio",
        x_end="fim",
        y="operador",
        color="status",
        text="texto",
        hover_data={
            "inicio": "|%d/%m/%Y",
            "fim": "|%d/%m/%Y"
        },
        color_discrete_map=cores_status
    )

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
        uniformtext_mode="show",
        bargap=0.25,
        height=650,
        margin=dict(l=40, r=40, t=70, b=40)
    )

    fig.update_xaxes(
        showgrid=True,
        gridcolor="rgba(255,255,255,0.05)",
        tickformat="%d/%m/%Y"
    )

    fig.update_yaxes(autorange="reversed")

    # linha vertical de HOJE
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

    return fig