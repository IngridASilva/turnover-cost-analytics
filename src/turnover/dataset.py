"""
Construção do dataset supervisionado de propensão de saída.

Decisões de desenho, todas reversíveis via config:

- Janela de predição: 6 meses. Define quanto tempo o RH tem para agir.
- Grão: person-month amostrado trimestralmente. O painel completo tem ~94 mil
  linhas, mas a mesma pessoa aparece em até 60 meses consecutivos com
  features quase idênticas. Isso infla o n sem aumentar a informação e
  contamina validação cruzada aleatória. A amostragem trimestral mantém
  volume razoável e reduz a autocorrelação.
- Rótulo: pedido de demissão (voluntário) dentro da janela. Dispensa pela
  empresa NÃO é positivo: é decisão da própria empresa, e misturar as duas
  coisas produz um modelo que prevê o próprio RH.
- Corte temporal: treino, validação e teste separados no tempo, sem
  sobreposição de janela de horizonte.
- Gênero e raça/cor ficam fora das features por decisão documentada, não por
  esquecimento. Ver docs/governanca.md.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

# Colunas que jamais entram como feature.
BLOQUEADAS = {
    "genero", "raca_cor", "nome", "hash_documento",       # sensíveis / identificadores
    "data_desligamento", "tipo_desligamento", "motivo_desligamento", "status",
    "efeito_latente_log_odds",                             # gabarito
}


@dataclass
class Janelas:
    """Cortes temporais. `fim_horizonte` é o último mês com 6 meses de futuro
    observável na base."""
    treino_fim: str
    validacao_fim: str
    teste_fim: str


def carregar(dir_base: str | Path) -> dict[str, pd.DataFrame]:
    d = Path(dir_base)
    nomes = [
        "fato_headcount_mensal", "fato_folha_mensal", "fato_movimentacao",
        "dim_colaborador", "dim_area", "dim_cargo", "fato_desligamento_custo",
    ]
    return {n: pd.read_parquet(d / f"{n}.parquet") for n in nomes}


# --------------------------------------------------------------------------
# Rótulo
# --------------------------------------------------------------------------
def aplicar_rotulo(
    snaps: pd.DataFrame, colabs: pd.DataFrame, janela_meses: int = 6
) -> pd.DataFrame:
    df = snaps.copy()
    base = colabs.set_index("matricula")
    df["_data_saida"] = df["matricula"].map(base["data_desligamento"])
    df["_tipo_saida"] = df["matricula"].map(base["tipo_desligamento"])

    horizonte = (df["_data_saida"] - df["data_referencia"]).dt.days
    limite = int(janela_meses * 30.44)

    df["label"] = (
        (horizonte > 0) & (horizonte <= limite) & (df["_tipo_saida"] == "Voluntário")
    ).astype(int)

    # Quem saiu por dispensa dentro da janela é removido, não rotulado como 0.
    # Manter como negativo ensina o modelo que "ia ficar", o que é falso: a
    # pessoa foi censurada por um evento concorrente.
    censurado = (
        (horizonte > 0) & (horizonte <= limite) & (df["_tipo_saida"] == "Involuntário")
    )
    df = df[~censurado].copy()

    return df.drop(columns=["_data_saida", "_tipo_saida"])


# --------------------------------------------------------------------------
# Features
# --------------------------------------------------------------------------
def features_de_equipe(snaps: pd.DataFrame) -> pd.DataFrame:
    """Agregações por gestor e mês.

    Esta é a parte que importa. O gerador da base embute um efeito latente de
    liderança que não está em nenhuma coluna do fato. A única forma de
    capturá-lo é olhar para o time, não para o indivíduo. Sem estas features o
    modelo aponta pessoas; com elas, aponta problemas de gestão.
    """
    g = snaps.groupby(["id_gestor", "id_mes"])
    eq = g.agg(
        tamanho_time=("matricula", "count"),
        compa_ratio_medio_time=("compa_ratio", "mean"),
        meses_sem_promocao_medio_time=("meses_sem_promocao", "mean"),
        performance_media_time=("performance", "mean"),
        horas_extras_media_time=("horas_extras", "mean"),
        meses_de_casa_medio_time=("meses_de_casa", "mean"),
    ).reset_index()
    return eq


def turnover_historico_gestor(
    snaps: pd.DataFrame, colabs: pd.DataFrame, meses: int = 12
) -> pd.DataFrame:
    """Turnover voluntário do time do gestor nos últimos 12 meses.

    Estritamente retrospectivo. Usar turnover futuro aqui seria vazamento
    direto do rótulo, e é um dos erros mais comuns em projeto de propensão.
    """
    base = colabs.set_index("matricula")
    s = snaps[["matricula", "id_gestor", "id_mes", "data_referencia"]].copy()
    s["data_saida"] = s["matricula"].map(base["data_desligamento"])
    s["tipo_saida"] = s["matricula"].map(base["tipo_desligamento"])

    saidas = s[s["tipo_saida"] == "Voluntário"].dropna(subset=["data_saida"])
    saidas = saidas[saidas["data_saida"] == saidas["data_referencia"]]
    por_gestor_mes = (
        saidas.groupby(["id_gestor", "data_referencia"]).size()
        .rename("saidas_no_mes").reset_index()
    )

    calendario = s[["id_gestor", "data_referencia", "id_mes"]].drop_duplicates()
    m = calendario.merge(por_gestor_mes, on=["id_gestor", "data_referencia"], how="left")
    m["saidas_no_mes"] = m["saidas_no_mes"].fillna(0)
    m = m.sort_values(["id_gestor", "data_referencia"])

    # Soma móvel de 12 meses, deslocada em 1 para excluir o mês corrente.
    m["saidas_12m_gestor"] = (
        m.groupby("id_gestor")["saidas_no_mes"]
        .transform(lambda s: s.shift(1).rolling(meses, min_periods=1).sum())
        .fillna(0)
    )
    return m[["id_gestor", "id_mes", "saidas_12m_gestor"]]


def features_individuais(snaps: pd.DataFrame) -> pd.DataFrame:
    """Derivadas do próprio histórico do colaborador, sempre retrospectivas."""
    df = snaps.sort_values(["matricula", "id_mes"]).copy()
    g = df.groupby("matricula")

    # Variação salarial nominal nos últimos 12 meses.
    df["salario_12m_atras"] = g["salario"].shift(12)
    df["var_salarial_12m"] = np.where(
        df["salario_12m_atras"].notna(),
        df["salario"] / df["salario_12m_atras"] - 1,
        np.nan,
    )
    # Deterioração do posicionamento: perdeu terreno contra a faixa?
    df["compa_ratio_12m_atras"] = g["compa_ratio"].shift(12)
    df["delta_compa_ratio_12m"] = df["compa_ratio"] - df["compa_ratio_12m_atras"]

    # Razão entre tempo no cargo atual e tempo de casa. Valor alto significa
    # que a pessoa passou a maior parte da carreira parada no mesmo nível.
    df["razao_estagnacao"] = df["meses_sem_promocao"] / df["meses_de_casa"].clip(lower=1)

    # Promoções por ano de casa.
    df["promocoes_por_ano"] = df["num_promocoes"] / (df["meses_de_casa"] / 12).clip(lower=0.5)

    # Sobrecarga relativa: horas extras contra a média da própria área.
    media_area = df.groupby(["id_area", "id_mes"])["horas_extras"].transform("mean")
    df["horas_extras_rel_area"] = df["horas_extras"] / media_area.clip(lower=0.5)

    # ------------------------------------------------------------------
    # Features de forma funcional.
    #
    # A inspeção de PDP e SHAP do modelo de árvore mostrou três estruturas que
    # uma regressão logística com termos lineares não consegue representar.
    # Em vez de aceitar a caixa-preta, codificamos as formas explicitamente.
    # O gabarito em docs/ground_truth do repositório da base confirma que são
    # exatamente as formas usadas na geração.
    # ------------------------------------------------------------------

    # 1. Subremuneração é assimétrica: ganhar abaixo da faixa empurra para
    #    fora, ganhar acima não segura na mesma proporção.
    df["subremuneracao"] = (1.0 - df["compa_ratio"]).clip(lower=0)

    # 2. Interação alto desempenho x subremuneração: a origem do turnover
    #    lamentado. Quem entrega e ganha mal tem opção externa.
    df["alto_desempenho"] = (df["performance"] - 3).clip(lower=0)
    df["perf_x_subremuneracao"] = df["alto_desempenho"] * df["subremuneracao"]

    # 3. Estagnação satura: de 12 para 24 meses sem promoção dói muito mais
    #    que de 60 para 72.
    df["log_meses_sem_promocao"] = np.log1p(df["meses_sem_promocao"] / 12.0)

    # 4. Risco por tempo de casa é um U invertido com pico perto do segundo
    #    ano, não uma reta.
    df["pico_tenure"] = np.exp(-(((df["meses_de_casa"] - 18.0) / 16.0) ** 2))

    return df.drop(columns=["salario_12m_atras", "compa_ratio_12m_atras"])


# --------------------------------------------------------------------------
# Montagem
# --------------------------------------------------------------------------
def construir_dataset(
    dir_base: str | Path,
    *,
    janela_meses: int = 6,
    meses_amostrados: tuple[int, ...] = (1, 4, 7, 10),
    janelas: Janelas | None = None,
) -> tuple[pd.DataFrame, Janelas]:
    t = carregar(dir_base)
    snaps, colabs, areas = t["fato_headcount_mensal"], t["dim_colaborador"], t["dim_area"]

    # Features precisam do painel completo; a amostragem vem só no final.
    snaps = features_individuais(snaps)
    snaps = snaps.merge(features_de_equipe(snaps), on=["id_gestor", "id_mes"], how="left")
    snaps = snaps.merge(
        turnover_historico_gestor(snaps, colabs), on=["id_gestor", "id_mes"], how="left"
    )
    snaps["turnover_12m_gestor"] = (
        snaps["saidas_12m_gestor"] / snaps["tamanho_time"].clip(lower=1)
    )

    # Posição relativa dentro do próprio time.
    snaps["compa_ratio_vs_time"] = snaps["compa_ratio"] - snaps["compa_ratio_medio_time"]

    snaps = snaps.merge(
        areas[["id_area", "diretoria", "gerencia", "criticidade"]], on="id_area", how="left"
    )
    snaps = aplicar_rotulo(snaps, colabs, janela_meses)

    # Corta a cauda sem futuro observável.
    ultimo = snaps["data_referencia"].max()
    fim_horizonte = ultimo - pd.DateOffset(months=janela_meses)
    snaps = snaps[snaps["data_referencia"] <= fim_horizonte]

    # Amostragem trimestral.
    snaps = snaps[snaps["data_referencia"].dt.month.isin(meses_amostrados)].copy()

    # Colaborador com menos de 3 meses de casa não tem histórico para as
    # features de variação e distorce o modelo. Fica de fora.
    snaps = snaps[snaps["meses_de_casa"] >= 3]

    if janelas is None:
        datas = sorted(snaps["data_referencia"].unique())
        janelas = Janelas(
            # Validação com dois trimestres: calibração isotônica com um só
            # trimestre fica instável (menos de 100 positivos).
            treino_fim=str(pd.Timestamp(datas[-5]).date()),
            validacao_fim=str(pd.Timestamp(datas[-3]).date()),
            teste_fim=str(pd.Timestamp(datas[-1]).date()),
        )

    snaps["particao"] = np.select(
        [
            snaps["data_referencia"] <= janelas.treino_fim,
            snaps["data_referencia"] <= janelas.validacao_fim,
        ],
        ["treino", "validacao"],
        default="teste",
    )
    return snaps.drop(columns=[c for c in BLOQUEADAS if c in snaps.columns]), janelas


# Conjunto final de features.
#
# Removidas por colinearidade: `meses_sem_promocao` e `razao_estagnacao`
# (redundantes com `log_meses_sem_promocao`, que tem a forma funcional
# correta) e `compa_ratio` (redundante com `subremuneracao`, que captura a
# assimetria). Mantê-las fazia os coeficientes da logística trocarem de sinal
# entre formas equivalentes — sintoma clássico de colinearidade, e algo que
# destrói a leitura do modelo numa apresentação.
NUMERICAS = [
    "grade", "salario", "performance", "meses_de_casa",
    "num_promocoes", "idade", "horas_extras",
    "var_salarial_12m", "delta_compa_ratio_12m",
    "promocoes_por_ano", "horas_extras_rel_area", "tamanho_time",
    "compa_ratio_medio_time", "meses_sem_promocao_medio_time",
    "performance_media_time", "horas_extras_media_time",
    "meses_de_casa_medio_time", "turnover_12m_gestor", "compa_ratio_vs_time",
    "subremuneracao", "alto_desempenho", "perf_x_subremuneracao",
    "log_meses_sem_promocao", "pico_tenure",
]
CATEGORICAS = ["modelo_trabalho", "familia_cargo", "diretoria", "criticidade"]


def separar_xy(df: pd.DataFrame, particao: str) -> tuple[pd.DataFrame, pd.Series]:
    sub = df[df["particao"] == particao]
    X = sub[NUMERICAS + CATEGORICAS].copy()
    for c in CATEGORICAS:
        X[c] = X[c].astype("category")
    return X, sub["label"]
