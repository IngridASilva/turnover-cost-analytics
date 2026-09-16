"""Testes que protegem contra os erros que invalidam o projeto inteiro."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from turnover.dataset import BLOQUEADAS, NUMERICAS, construir_dataset, separar_xy
from turnover.economics import PremissasEconomicas, preparar


@pytest.fixture(scope="module")
def dados():
    df, janelas = construir_dataset("data_base")
    return df, janelas


def test_particoes_nao_se_sobrepoem_no_tempo(dados):
    df, _ = dados
    limites = df.groupby("particao")["data_referencia"].agg(["min", "max"])
    assert limites.loc["treino", "max"] < limites.loc["validacao", "min"]
    assert limites.loc["validacao", "max"] < limites.loc["teste", "min"]


def test_sem_colunas_proibidas(dados):
    """Identificadores, dados sensíveis e gabarito não podem virar feature."""
    df, _ = dados
    assert not (BLOQUEADAS & set(df.columns))
    assert not ({"genero", "raca_cor"} & set(NUMERICAS))


def test_horizonte_completo_observavel(dados):
    """Nenhuma linha pode ter janela de 6 meses que ultrapasse o fim da base."""
    df, _ = dados
    assert df["data_referencia"].max() <= pd.Timestamp("2025-06-30")


def test_prevalencia_estavel_entre_particoes(dados):
    df, _ = dados
    prev = df.groupby("particao")["label"].mean()
    assert prev.max() - prev.min() < 0.03, f"deriva de prevalência: {prev.to_dict()}"


def test_rotulo_so_conta_saida_voluntaria(dados):
    df, _ = dados
    assert df["label"].isin([0, 1]).all()
    assert 0.02 < df["label"].mean() < 0.12


def test_limiar_cai_com_criticidade():
    """Quanto mais caro perder a pessoa, menor a probabilidade que já
    justifica agir. Se este teste quebrar, a camada econômica está invertida."""
    base = pd.DataFrame({
        "salario": [9000.0] * 3,
        "meses_de_casa": [30.0] * 3,
        "compa_ratio": [0.92] * 3,
        "criticidade": ["Alta", "Média", "Baixa"],
        "label": [0, 0, 0],
    })
    esc = preparar(base, np.array([0.08, 0.08, 0.08]), PremissasEconomicas())
    limiares = esc["limiar_conversa"].tolist()
    assert limiares[0] < limiares[1] < limiares[2]


def test_acao_material_exige_gap_real():
    """Quem está acima da mediana não pode entrar na lista de ajuste."""
    base = pd.DataFrame({
        "salario": [9000.0, 9000.0],
        "meses_de_casa": [30.0, 30.0],
        "compa_ratio": [1.05, 0.80],
        "criticidade": ["Alta", "Alta"],
        "label": [0, 0],
    })
    esc = preparar(base, np.array([0.30, 0.30]), PremissasEconomicas())
    assert not esc.loc[0, "acionar_material"]
    assert esc.loc[0, "custo_material"] == 0


def test_separar_xy_devolve_mesmas_colunas(dados):
    df, _ = dados
    X1, _ = separar_xy(df, "treino")
    X2, _ = separar_xy(df, "teste")
    assert list(X1.columns) == list(X2.columns)
