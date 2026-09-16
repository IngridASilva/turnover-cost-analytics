"""
Treino, calibração e avaliação.

A calibração não é preciosismo estatístico neste projeto. A camada econômica
multiplica a probabilidade por reais, então um modelo que diz 0,30 quando a
frequência real é 0,12 produz um número financeiro errado com aparência de
precisão. AUC não detecta esse erro: ela só olha ordenação. Brier e a curva de
confiabilidade, sim.

Ordem: treina no `treino`, calibra no `validacao`, avalia no `teste`.
Calibrar no mesmo conjunto do treino vaza e produz calibração otimista.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.frozen import FrozenEstimator
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from xgboost import XGBClassifier

from .dataset import CATEGORICAS, NUMERICAS


@dataclass
class Resultado:
    nome: str
    auc_roc: float
    auc_pr: float
    brier: float
    lift_decil: float
    prevalencia: float

    def como_linha(self) -> dict:
        return {
            "modelo": self.nome,
            "AUC-ROC": round(self.auc_roc, 4),
            "AUC-PR": round(self.auc_pr, 4),
            "Brier": round(self.brier, 5),
            "lift decil 1": round(self.lift_decil, 2),
            "prevalência": round(self.prevalencia, 4),
        }


def baseline_logistica() -> Pipeline:
    """Referência obrigatória. Se o XGBoost não bater a logística com folga,
    a complexidade extra não se justifica na conversa com o negócio."""
    pre = ColumnTransformer([
        ("num", Pipeline([
            ("imp", SimpleImputer(strategy="median")),
            ("sc", StandardScaler()),
        ]), NUMERICAS),
        ("cat", OneHotEncoder(handle_unknown="ignore", drop="first"), CATEGORICAS),
    ])
    return Pipeline([
        ("pre", pre),
        ("clf", LogisticRegression(max_iter=2000, C=0.5)),
    ])


def modelo_xgboost(prevalencia: float) -> XGBClassifier:
    """XGBoost com suporte nativo a categóricas.

    Sobre balanceamento: NÃO usamos SMOTE nem undersampling. Com prevalência
    de ~5% o problema não é desbalanceamento, é escassez de positivos, e
    reamostragem sintética distorce a calibração — justamente o que precisamos
    preservar para converter probabilidade em reais. `scale_pos_weight` fica
    em 1 e o ajuste de decisão acontece na camada econômica, onde ele tem
    significado de negócio.
    """
    return XGBClassifier(
        n_estimators=1500,
        learning_rate=0.03,
        max_depth=3,
        min_child_weight=20,
        subsample=0.85,
        colsample_bytree=0.70,
        reg_lambda=3.0,
        enable_categorical=True,
        tree_method="hist",
        eval_metric="aucpr",
        early_stopping_rounds=80,
        random_state=42,
    )


def avaliar(nome: str, y: pd.Series, p: np.ndarray) -> Resultado:
    n_decil = max(int(0.1 * len(p)), 1)
    top = y.to_numpy()[np.argsort(-p)[:n_decil]]
    prev = float(y.mean())
    return Resultado(
        nome=nome,
        auc_roc=roc_auc_score(y, p),
        auc_pr=average_precision_score(y, p),
        brier=brier_score_loss(y, p),
        lift_decil=float(top.mean() / prev) if prev else np.nan,
        prevalencia=prev,
    )


def curva_confiabilidade(y: pd.Series, p: np.ndarray, n_faixas: int = 10) -> pd.DataFrame:
    """Probabilidade prevista contra frequência observada, por faixa.

    É esta tabela que você mostra quando alguém perguntar se dá para confiar
    no número em reais.
    """
    df = pd.DataFrame({"y": y.to_numpy(), "p": p})
    df["faixa"] = pd.qcut(df["p"], n_faixas, duplicates="drop")
    g = df.groupby("faixa", observed=True).agg(
        n=("y", "size"),
        prob_media_prevista=("p", "mean"),
        frequencia_observada=("y", "mean"),
    ).reset_index(drop=True)
    g["desvio"] = g["frequencia_observada"] - g["prob_media_prevista"]
    return g.round(4)


def treinar(
    X_tr: pd.DataFrame, y_tr: pd.Series,
    X_va: pd.DataFrame, y_va: pd.Series,
) -> dict:
    """Compara logística e XGBoost, calibra os dois e devolve tudo.

    Sobre a escolha do método de calibração: isotônica precisa de volume de
    positivos para não decorar a cauda. Com ~140 positivos no conjunto de
    validação ela produziu probabilidade máxima de 1,00 e piorou a AUC-PR.
    Platt (sigmoide) tem apenas dois parâmetros, é estável nesse regime e
    melhorou o Brier nos dois modelos. Foi a escolhida.
    """
    logistica = baseline_logistica().fit(X_tr, y_tr)
    xgb = modelo_xgboost(float(y_tr.mean()))
    xgb.fit(X_tr, y_tr, eval_set=[(X_va, y_va)], verbose=False)

    cal_log = CalibratedClassifierCV(FrozenEstimator(logistica), method="sigmoid")
    cal_log.fit(X_va, y_va)
    cal_xgb = CalibratedClassifierCV(FrozenEstimator(xgb), method="sigmoid")
    cal_xgb.fit(X_va, y_va)

    return {
        "logistica": logistica, "xgboost": xgb,
        "logistica_calibrada": cal_log, "xgboost_calibrado": cal_xgb,
    }
