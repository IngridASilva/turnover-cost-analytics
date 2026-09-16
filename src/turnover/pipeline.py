"""Pipeline ponta a ponta: dataset -> modelos -> calibração -> decisão econômica."""

from __future__ import annotations

import argparse
import warnings
from pathlib import Path

import pandas as pd

from .dataset import construir_dataset, separar_xy
from .economics import PremissasEconomicas, preparar, sensibilidade, simular_campanha
from .model import avaliar, curva_confiabilidade, treinar
from .monitor import (
    deriva_calibracao,
    deriva_features,
    montar_alertas,
    registrar,
    severidade_geral,
)

warnings.filterwarnings("ignore")
pd.set_option("display.width", 200)


def main() -> None:
    ap = argparse.ArgumentParser(description="Propensão e custo de turnover")
    ap.add_argument("--base", default="data_base")
    ap.add_argument("--saida", default="reports")
    ap.add_argument("--janela", type=int, default=6)
    args = ap.parse_args()

    saida = Path(args.saida)
    saida.mkdir(parents=True, exist_ok=True)

    df, _ = construir_dataset(args.base, janela_meses=args.janela)
    print(f"\nDataset: {len(df):,} linhas | prevalência {df['label'].mean():.4f}")
    print(df.groupby("particao").agg(
        linhas=("label", "size"), positivos=("label", "sum"),
        prevalencia=("label", lambda s: round(s.mean(), 4)),
        de=("data_referencia", "min"), ate=("data_referencia", "max"),
    ).to_string())

    X_tr, y_tr = separar_xy(df, "treino")
    X_va, y_va = separar_xy(df, "validacao")
    X_te, y_te = separar_xy(df, "teste")

    modelos = treinar(X_tr, y_tr, X_va, y_va)
    escores = {n: m.predict_proba(X_te)[:, 1] for n, m in modelos.items()}
    metricas = pd.DataFrame(
        [avaliar(n, y_te, p).como_linha() for n, p in escores.items()]
    ).sort_values("AUC-PR", ascending=False)

    print("\nComparação de modelos (conjunto de teste):")
    print(metricas.to_string(index=False))

    escolhido = "logistica_calibrada"
    p_final = escores[escolhido]
    print(f"\nModelo em produção: {escolhido}")
    print("\nCurva de confiabilidade:")
    print(curva_confiabilidade(y_te, p_final).to_string(index=False))

    # ---------------------------------------------------------------- economia
    prem = PremissasEconomicas()
    teste = df[df["particao"] == "teste"].reset_index(drop=True)
    esc = preparar(teste, p_final, prem)

    print("\nLimiar de acionamento por criticidade da área:")
    print(esc.groupby("criticidade", observed=True).agg(
        n=("matricula", "size"),
        salario_mediano=("salario", "median"),
        custo_perder_mediano=("custo_perder", "median"),
        limiar_conversa=("limiar_conversa", "median"),
        limiar_material=("limiar_material", "median"),
        prob_mediana=("probabilidade", "median"),
    ).round(3).to_string())

    politicas = [
        simular_campanha(esc, prem, nome="camada 1 - limiar individual"),
        simular_campanha(esc, prem, mascara=esc["probabilidade"] > 0.5,
                         nome="camada 1 - limiar fixo 0,50"),
        simular_campanha(esc, prem,
                         mascara=esc["probabilidade"] >= esc["probabilidade"].quantile(0.90),
                         nome="camada 1 - top 10% por probabilidade"),
        simular_campanha(esc, prem,
                         mascara=esc["risco_financeiro"] >= esc["risco_financeiro"].quantile(0.90),
                         nome="camada 1 - top 10% por R$ em risco"),
        simular_campanha(esc, prem, mascara=esc["acionar_material"],
                         nome="camada 2 - ajuste salarial",
                         eficacia=prem.eficacia_incremental,
                         custo=esc["custo_material"]),
    ]
    print("\nComparação de políticas de acionamento:")
    print(pd.DataFrame(politicas).to_string(index=False))

    sens = sensibilidade(esc, prem)
    print("\nSensibilidade à eficácia da conversa de carreira:")
    print(sens.to_string(index=False))

    # ------------------------------------------------------------ exportação
    colunas = [
        "id_mes", "data_referencia", "matricula", "id_area", "diretoria",
        "gerencia", "criticidade", "id_cargo", "grade", "familia_cargo",
        "modelo_trabalho", "salario", "compa_ratio", "meses_de_casa",
        "meses_sem_promocao", "performance", "id_gestor", "turnover_12m_gestor",
        "probabilidade", "faixa_risco", "custo_perder", "risco_financeiro",
        "custo_conversa", "limiar_conversa", "acionar_conversa", "custo_material",
        "limiar_material", "acionar_material", "label",
    ]
    # ------------------------------------------------------------ monitoramento
    treino = df[df["particao"] == "treino"]
    drift = deriva_features(treino, teste, list(X_te.columns))
    calib = deriva_calibracao(y_te, p_final)
    alertas = montar_alertas(drift, calib, int(esc["acionar_conversa"].sum()))
    registrar(alertas, saida, int(esc["id_mes"].max()))

    print(f"\nMonitoramento — severidade geral: {severidade_geral(alertas).upper()}")
    print(drift.head(6).to_string(index=False))
    for a in alertas:
        print(f"  [{a['severidade']}] {a['titulo']}: {a['detalhe']}")

    drift.to_csv(saida / "deriva_features.csv", index=False)

    esc[colunas].to_parquet(saida / "fato_scoring.parquet", index=False)
    metricas.to_csv(saida / "metricas_modelo.csv", index=False)
    pd.DataFrame(politicas).to_csv(saida / "comparacao_politicas.csv", index=False)
    sens.to_csv(saida / "sensibilidade.csv", index=False)
    print(f"\nArtefatos em {saida.resolve()}")


if __name__ == "__main__":
    main()
