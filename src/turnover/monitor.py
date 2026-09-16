"""
Monitoramento do modelo em produção.

Dois tipos de deriva, com consequências diferentes:

**Deriva de features (PSI).** A população mudou. O modelo continua coerente
internamente, mas foi treinado em outra empresa. Sinal de atenção.

**Deriva de calibração.** As probabilidades deixaram de bater com a frequência
observada. Este é o crítico neste projeto, porque a camada financeira
multiplica probabilidade por reais. Um modelo que ainda ordena bem (AUC
estável) mas superestima o nível produz um valor em reais inflado com
aparência de precisão, e ninguém percebe olhando a AUC.

A saída é um dicionário pronto para virar payload de alerta (Teams, Slack,
Power Automate) e uma linha no histórico de monitoramento.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

# Limiares convencionais de PSI. Não são lei, mas são o vocabulário que a
# maioria dos times usa, e alinhar vocabulário evita discussão improdutiva.
PSI_ATENCAO = 0.10
PSI_CRITICO = 0.25

# Desvio absoluto máximo tolerado entre probabilidade média prevista e
# frequência observada, no agregado.
DESVIO_CALIBRACAO_ATENCAO = 0.010
DESVIO_CALIBRACAO_CRITICO = 0.020


@dataclass
class Alerta:
    severidade: str          # ok | atencao | critico
    titulo: str
    detalhe: str
    metrica: float

    def como_dict(self) -> dict:
        return {
            "severidade": self.severidade,
            "titulo": self.titulo,
            "detalhe": self.detalhe,
            "metrica": round(float(self.metrica), 5),
        }


def psi(referencia: pd.Series, atual: pd.Series, n_faixas: int = 10) -> float:
    """Population Stability Index entre duas distribuições.

    Faixas definidas na referência, não no conjunto atual. Recalcular as
    faixas a cada execução esconde exatamente a mudança que se quer detectar.
    """
    ref = referencia.dropna()
    atu = atual.dropna()
    if ref.nunique() < 3 or len(atu) == 0:
        return 0.0

    cortes = np.unique(np.quantile(ref, np.linspace(0, 1, n_faixas + 1)))
    if len(cortes) < 3:
        return 0.0
    cortes[0], cortes[-1] = -np.inf, np.inf

    p_ref = np.histogram(ref, bins=cortes)[0] / len(ref)
    p_atu = np.histogram(atu, bins=cortes)[0] / len(atu)

    # Piso para evitar divisão por zero em faixa vazia.
    p_ref = np.clip(p_ref, 1e-4, None)
    p_atu = np.clip(p_atu, 1e-4, None)
    return float(np.sum((p_atu - p_ref) * np.log(p_atu / p_ref)))


def deriva_features(
    referencia: pd.DataFrame, atual: pd.DataFrame, colunas: list[str]
) -> pd.DataFrame:
    linhas = []
    for c in colunas:
        if c not in referencia.columns or c not in atual.columns:
            continue
        if not pd.api.types.is_numeric_dtype(referencia[c]):
            continue
        valor = psi(referencia[c], atual[c])
        linhas.append({
            "feature": c,
            "psi": round(valor, 4),
            "status": (
                "critico" if valor >= PSI_CRITICO
                else "atencao" if valor >= PSI_ATENCAO
                else "ok"
            ),
            "media_referencia": round(float(referencia[c].mean()), 3),
            "media_atual": round(float(atual[c].mean()), 3),
        })
    return pd.DataFrame(linhas).sort_values("psi", ascending=False)


def deriva_calibracao(y: pd.Series, prob: np.ndarray) -> Alerta:
    """Compara probabilidade média prevista com a frequência realmente
    observada. Só é calculável quando a janela de 6 meses já fechou."""
    previsto = float(np.mean(prob))
    observado = float(y.mean())
    desvio = observado - previsto

    if abs(desvio) >= DESVIO_CALIBRACAO_CRITICO:
        sev = "critico"
    elif abs(desvio) >= DESVIO_CALIBRACAO_ATENCAO:
        sev = "atencao"
    else:
        sev = "ok"

    direcao = "subestimando" if desvio > 0 else "superestimando"
    return Alerta(
        severidade=sev,
        titulo="Calibração do modelo",
        detalhe=(
            f"Previsto {previsto:.3%}, observado {observado:.3%}. "
            f"O modelo está {direcao} o risco em "
            f"{abs(desvio):.3%} no agregado. "
            "Isso propaga direto para o valor em reais exibido no painel."
        ),
        metrica=desvio,
    )


def montar_alertas(
    drift: pd.DataFrame, calibracao: Alerta, n_acionaveis: int,
    n_acionaveis_anterior: int | None = None,
) -> list[dict]:
    alertas = [calibracao.como_dict()]

    criticas = drift[drift["status"] == "critico"]
    if len(criticas):
        alertas.append(Alerta(
            severidade="critico",
            titulo="Deriva de população",
            detalhe=(
                f"{len(criticas)} feature(s) com PSI acima de {PSI_CRITICO}: "
                + ", ".join(criticas["feature"].head(5))
                + ". A população mudou o suficiente para justificar retreino."
            ),
            metrica=float(criticas["psi"].max()),
        ).como_dict())

    # Salto abrupto no tamanho da lista costuma ser falha de dado, não do
    # mercado de trabalho. Vale checar antes de mobilizar gestores.
    if n_acionaveis_anterior:
        variacao = n_acionaveis / max(n_acionaveis_anterior, 1) - 1
        if abs(variacao) > 0.40:
            alertas.append(Alerta(
                severidade="atencao",
                titulo="Volume da lista de acionamento",
                detalhe=(
                    f"Lista passou de {n_acionaveis_anterior} para "
                    f"{n_acionaveis} pessoas ({variacao:+.0%}). "
                    "Verifique integridade da carga antes de acionar gestores."
                ),
                metrica=variacao,
            ).como_dict())

    return alertas


def registrar(alertas: list[dict], destino: str | Path,
              id_mes: int) -> pd.DataFrame:
    """Acrescenta a execução ao histórico de monitoramento.

    O histórico vira uma página do Power BI. Painel de modelo sem página de
    saúde do modelo é painel que ninguém sabe quando parou de funcionar.
    """
    caminho = Path(destino) / "historico_monitoramento.csv"
    novo = pd.DataFrame(alertas)
    novo.insert(0, "id_mes", id_mes)

    if caminho.exists():
        historico = pd.concat([pd.read_csv(caminho), novo], ignore_index=True)
    else:
        historico = novo

    caminho.parent.mkdir(parents=True, exist_ok=True)
    historico.to_csv(caminho, index=False, encoding="utf-8-sig")
    return historico


def severidade_geral(alertas: list[dict]) -> str:
    if any(a["severidade"] == "critico" for a in alertas):
        return "critico"
    if any(a["severidade"] == "atencao" for a in alertas):
        return "atencao"
    return "ok"
