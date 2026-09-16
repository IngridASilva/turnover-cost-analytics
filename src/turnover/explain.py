"""
Explicabilidade: SHAP no modelo de árvore, coeficientes na logística.

Dois usos distintos, que costumam ser confundidos:

- **Explicação global** responde "o que puxa o turnover nesta empresa". É
  insumo de política de RH e é o que vai para a diretoria.
- **Explicação local** responde "por que esta pessoa apareceu na lista". É
  insumo de conversa entre RH e gestor, e precisa citar fatores acionáveis.

O modelo em produção é a logística, cujos coeficientes já são interpretáveis.
O SHAP entra sobre o XGBoost com outra finalidade: verificar se há estrutura
não linear que a logística esteja deixando na mesa, e conferir o ranking de
drivers contra o gabarito documentado do gerador da base.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import shap

from .dataset import CATEGORICAS, NUMERICAS


def importancia_global(modelo, X: pd.DataFrame, n: int = 20) -> pd.DataFrame:
    """Ranking por SHAP médio absoluto."""
    explicador = shap.TreeExplainer(modelo)
    valores = explicador.shap_values(X)
    imp = pd.DataFrame({
        "feature": X.columns,
        "shap_medio_abs": np.abs(valores).mean(axis=0),
    })
    imp["participacao"] = imp["shap_medio_abs"] / imp["shap_medio_abs"].sum()
    return imp.sort_values("shap_medio_abs", ascending=False).head(n).reset_index(drop=True)


def coeficientes_logistica(pipeline) -> pd.DataFrame:
    """Coeficientes padronizados. Como as numéricas passam por StandardScaler,
    a magnitude é comparável entre variáveis."""
    pre = pipeline.named_steps["pre"]
    nomes = list(NUMERICAS) + list(
        pre.named_transformers_["cat"].get_feature_names_out(CATEGORICAS)
    )
    coefs = pipeline.named_steps["clf"].coef_[0]
    df = pd.DataFrame({"feature": nomes, "coeficiente": coefs})
    df["odds_ratio"] = np.exp(df["coeficiente"])
    df["abs"] = df["coeficiente"].abs()
    return df.sort_values("abs", ascending=False).drop(columns="abs").reset_index(drop=True)


def explicacao_individual(modelo, X: pd.DataFrame, linha: int,
                          top: int = 3) -> pd.DataFrame:
    """Os N fatores que mais empurraram uma pessoa para cima do limiar.

    É o que aparece no drill-through do Power BI. Regra de comunicação: só
    exibir fatores acionáveis. Dizer a um gestor que a pessoa é jovem não
    gera ação nenhuma; dizer que está há 31 meses sem promoção, sim.
    """
    explicador = shap.TreeExplainer(modelo)
    valores = explicador.shap_values(X.iloc[[linha]])[0]
    df = pd.DataFrame({
        "feature": X.columns,
        "valor": X.iloc[linha].values,
        "contribuicao": valores,
    })
    return df.reindex(df["contribuicao"].abs().sort_values(ascending=False).index) \
             .head(top).reset_index(drop=True)


HIERARQUIA_GABARITO = [
    "meses_sem_promocao", "compa_ratio", "perf_x_subremuneracao",
    "meses_de_casa", "turnover_12m_gestor", "modelo_trabalho", "idade",
    "horas_extras", "distancia_km",
]


def conferir_contra_gabarito(imp: pd.DataFrame) -> pd.DataFrame:
    """Compara o ranking observado com a hierarquia verdadeira do gerador.

    Equivalentes são tratados como o mesmo conceito: log_meses_sem_promocao e
    razao_estagnacao medem estagnação; subremuneracao e compa_ratio medem
    posicionamento.
    """
    equiv = {
        "meses_sem_promocao": {"meses_sem_promocao", "log_meses_sem_promocao",
                               "razao_estagnacao", "promocoes_por_ano"},
        "compa_ratio": {"compa_ratio", "subremuneracao", "delta_compa_ratio_12m",
                        "compa_ratio_vs_time", "var_salarial_12m"},
        "perf_x_subremuneracao": {"perf_x_subremuneracao", "alto_desempenho",
                                  "performance"},
        "meses_de_casa": {"meses_de_casa", "pico_tenure"},
        "turnover_12m_gestor": {"turnover_12m_gestor", "meses_sem_promocao_medio_time",
                                "compa_ratio_medio_time", "performance_media_time",
                                "tamanho_time", "meses_de_casa_medio_time"},
        "modelo_trabalho": {c for c in ["modelo_trabalho"]},
        "idade": {"idade"},
        "horas_extras": {"horas_extras", "horas_extras_rel_area",
                         "horas_extras_media_time"},
    }
    posicao = {f: i for i, f in enumerate(imp["feature"])}
    linhas = []
    for i, conceito in enumerate(HIERARQUIA_GABARITO):
        fs = equiv.get(conceito, {conceito})
        pos = [posicao[f] for f in fs if f in posicao]
        peso = imp.loc[imp["feature"].isin(fs), "participacao"].sum()
        linhas.append({
            "conceito": conceito,
            "posicao_esperada": i + 1,
            "melhor_posicao_observada": min(pos) + 1 if pos else None,
            "participacao_shap": round(float(peso), 4),
        })
    df = pd.DataFrame(linhas)
    df["rank_observado"] = df["participacao_shap"].rank(ascending=False).astype(int)
    return df
