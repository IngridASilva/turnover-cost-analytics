"""
Camada econômica: transforma probabilidade em decisão de gasto.

Por que o custo do falso positivo não é um número único
-------------------------------------------------------
Tratar "agir sobre um falso positivo" como despesa fixa embute três premissas
erradas:

1. **Ação de retenção não é binária.** Ninguém dá aumento para todo mundo que
   o modelo sinaliza. O que existe é uma escada: todo sinalizado recebe uma
   conversa estruturada de carreira (custo é tempo de gestor e de RH), e
   apenas parte escala para ação material.

2. **A ação não funciona sempre.** Assumir eficácia de 100% infla o ROI do
   projeto por um fator de duas a três vezes. É a premissa que mais move o
   resultado e a que quase nenhum projeto declara.

3. **O custo evitado varia por pessoa.** Perder um especialista de área
   crítica custa seis salários de reposição; um assistente de produção custa
   dois e meio. O mesmo gasto se paga num caso e não no outro.

Modelo adotado: duas decisões independentes
-------------------------------------------
Cada camada tem custo, eficácia e limiar próprios.

    Camada 1 - conversa estruturada de carreira
        custo:    tempo de gestor + RH, algumas centenas de reais
        eficácia: baixa isoladamente (~15%)
        limiar:   c1 / (e1 x custo_perder)

    Camada 2 - ação material (correção de posicionamento salarial)
        custo:    gap até a mediana da faixa, anualizado e carregado
        eficácia: incremental sobre a camada 1 (45% total, +30 pontos)
        limiar:   c2 / ((e2 - e1) x custo_perder)

Separar as duas expõe um resultado que o modelo de custo único esconde: a
conversa barata se paga numa faixa ampla do quadro, enquanto ajuste salarial
como ferramenta de retenção raramente sobrevive à conta de valor esperado.
Ver `docs/achados.md`.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class PremissasEconomicas:
    """Todas as premissas em um lugar, para o stakeholder contestar uma a uma."""

    # --- Camada 1: conversa estruturada -----------------------------------
    horas_gestor: float = 3.0             # preparação, conversa, follow-up
    horas_rh: float = 2.0
    custo_hora_gestor: float = 145.0      # salário gerencial carregado / 220h
    custo_hora_rh: float = 95.0
    eficacia_conversa: float = 0.15

    # --- Camada 2: correção de posicionamento -----------------------------
    # O custo não é um percentual fixo: é o gap até a mediana da faixa.
    # Quem já está no ponto médio não recebe ajuste, e tratar todo mundo com
    # os mesmos 8% superestima o custo em metade do quadro.
    piso_ajuste: float = 0.03             # abaixo disso não é ação de retenção
    teto_ajuste: float = 0.15             # limite de correção em uma rodada
    meses_ate_reavaliacao: int = 12
    fator_encargos: float = 1.94
    eficacia_total: float = 0.45          # camada 1 + camada 2

    # --- Custo de reposição (múltiplo do salário mensal) ------------------
    multiplo_reposicao: dict = field(
        default_factory=lambda: {"Alta": 6.0, "Média": 4.0, "Baixa": 2.5}
    )

    @property
    def custo_conversa(self) -> float:
        return (self.horas_gestor * self.custo_hora_gestor
                + self.horas_rh * self.custo_hora_rh)

    @property
    def eficacia_incremental(self) -> float:
        return max(self.eficacia_total - self.eficacia_conversa, 1e-6)


# --------------------------------------------------------------------------
# Custos
# --------------------------------------------------------------------------
def custo_material(salario: pd.Series, compa_ratio: pd.Series,
                   p: PremissasEconomicas) -> pd.Series:
    """Custo anual carregado de corrigir o posicionamento até a mediana."""
    gap = (1.0 - compa_ratio).clip(lower=0, upper=p.teto_ajuste)
    # Corrigir um gap de 0,5% não é ação de retenção, é ruído de folha. Sem
    # este piso a camada 2 sinaliza quem está em cima da mediana, porque o
    # custo tende a zero e qualquer probabilidade "compensa".
    gap = gap.where(gap >= p.piso_ajuste, 0.0)
    return salario * gap * p.meses_ate_reavaliacao * p.fator_encargos


def custo_reposicao(salario: pd.Series, meses_de_casa: pd.Series,
                    criticidade: pd.Series, p: PremissasEconomicas) -> pd.Series:
    """Custo de perder a pessoa: verbas rescisórias + reposição.

    Pedido de demissão não gera multa de FGTS nem aviso prévio indenizado,
    então o peso está na reposição: recrutamento, seleção, onboarding e curva
    de produtividade até o substituto render.
    """
    ferias_e_13o = salario * ((4 / 3) * (meses_de_casa.mod(12) / 12) + 0.5)
    verbas = ferias_e_13o * p.fator_encargos
    reposicao = salario * criticidade.map(p.multiplo_reposicao).astype(float)
    return verbas + reposicao


# --------------------------------------------------------------------------
# Decisão
# --------------------------------------------------------------------------
def preparar(df: pd.DataFrame, prob: np.ndarray,
             p: PremissasEconomicas) -> pd.DataFrame:
    """Anexa custos, limiares e decisões a um conjunto já escorado."""
    out = df.copy()
    out["probabilidade"] = prob
    out["custo_perder"] = custo_reposicao(
        out["salario"], out["meses_de_casa"], out["criticidade"], p
    )
    out["risco_financeiro"] = out["probabilidade"] * out["custo_perder"]

    # Camada 1
    out["custo_conversa"] = p.custo_conversa
    out["limiar_conversa"] = (
        p.custo_conversa / (p.eficacia_conversa * out["custo_perder"])
    ).clip(0, 1)
    out["ve_conversa"] = (
        out["probabilidade"] * p.eficacia_conversa * out["custo_perder"]
        - p.custo_conversa
    )
    out["acionar_conversa"] = out["ve_conversa"] > 0

    # Camada 2 (decisão incremental, só faz sentido sobre quem já conversou)
    out["custo_material"] = custo_material(out["salario"], out["compa_ratio"], p)
    with np.errstate(divide="ignore", invalid="ignore"):
        out["limiar_material"] = np.where(
            out["custo_material"] > 0,
            (out["custo_material"]
             / (p.eficacia_incremental * out["custo_perder"])).clip(0, 1),
            np.nan,
        )
    out["ve_material"] = (
        out["probabilidade"] * p.eficacia_incremental * out["custo_perder"]
        - out["custo_material"]
    )
    # Exigir custo positivo: quem está em cima da mediana não tem ação
    # material a receber, e sem esta condição entraria na lista com custo zero.
    out["acionar_material"] = (
        out["acionar_conversa"] & (out["custo_material"] > 0) & (out["ve_material"] > 0)
    )

    out["faixa_risco"] = pd.cut(
        out["probabilidade"], [-0.01, 0.05, 0.12, 0.25, 1.01],
        labels=["Baixo", "Moderado", "Elevado", "Crítico"],
    )
    return out


def simular_campanha(escorado: pd.DataFrame, p: PremissasEconomicas,
                     mascara: pd.Series | None = None,
                     nome: str = "limiar individual",
                     eficacia: float | None = None,
                     custo: pd.Series | None = None) -> dict:
    """Resultado financeiro de uma política, medido contra o desfecho real."""
    m = escorado["acionar_conversa"] if mascara is None else mascara
    ef = p.eficacia_conversa if eficacia is None else eficacia
    c = escorado["custo_conversa"] if custo is None else custo

    alvo = escorado[m]
    investimento = float(c[m].sum())
    custo_evitado = float(alvo.loc[alvo["label"] == 1, "custo_perder"].sum() * ef)
    nao_endereçado = float(
        escorado.loc[~m & (escorado["label"] == 1), "custo_perder"].sum()
    )
    return {
        "politica": nome,
        "acionados": int(m.sum()),
        "pct_da_base": round(float(m.mean()), 4),
        "positivos_no_alvo": int(alvo["label"].sum()),
        "recall": round(float(alvo["label"].sum() / max(escorado["label"].sum(), 1)), 4),
        "precisao": round(float(alvo["label"].mean()), 4) if len(alvo) else 0.0,
        "investimento": round(investimento, 2),
        "retencoes_esperadas": round(float(alvo["label"].sum() * ef), 1),
        "custo_evitado": round(custo_evitado, 2),
        "resultado_liquido": round(custo_evitado - investimento, 2),
        "roi": round((custo_evitado - investimento) / investimento, 3)
        if investimento else np.nan,
        "perda_nao_enderecada": round(nao_endereçado, 2),
    }


def sensibilidade(escorado: pd.DataFrame, p: PremissasEconomicas,
                  grade: tuple[float, ...] = (0.05, 0.10, 0.15, 0.20, 0.30)
                  ) -> pd.DataFrame:
    """Como o resultado reage à premissa mais frágil: a eficácia da conversa.

    Leve esta tabela para a reunião. Se o projeto só tem retorno com eficácia
    de 30%, ele não tem retorno — tem esperança.
    """
    linhas = []
    limpar = [
        "probabilidade", "custo_perder", "risco_financeiro", "custo_conversa",
        "limiar_conversa", "ve_conversa", "acionar_conversa", "custo_material",
        "limiar_material", "ve_material", "acionar_material", "faixa_risco",
    ]
    base = escorado.drop(columns=[c for c in limpar if c in escorado.columns])
    prob = escorado["probabilidade"].to_numpy()
    for ef in grade:
        p_ = replace(p, eficacia_conversa=ef)
        r = simular_campanha(preparar(base, prob, p_), p_, nome=f"eficácia {ef:.0%}")
        linhas.append({
            "eficacia_conversa": ef, "acionados": r["acionados"],
            "pct_da_base": r["pct_da_base"], "investimento": r["investimento"],
            "custo_evitado": r["custo_evitado"],
            "resultado_liquido": r["resultado_liquido"], "roi": r["roi"],
        })
    return pd.DataFrame(linhas)
