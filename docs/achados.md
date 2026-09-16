# Achados

Resultados no conjunto de teste (jan–abr/2025, 3.023 observações, prevalência
5,92%), com o modelo treinado até abr/2024 e calibrado em jul–out/2024.

## 1. XGBoost não venceu a regressão logística

| Modelo | AUC-ROC | AUC-PR | Brier | Lift decil 1 |
|---|---|---|---|---|
| Logística calibrada | **0,707** | 0,138 | **0,0542** | 2,35 |
| XGBoost calibrado | 0,687 | 0,138 | 0,0544 | 2,40 |

Com ~1.080 positivos no treino e um processo gerador em que os efeitos são
aditivos em log-odds, a árvore não tem o que explorar além do que a logística
já captura — desde que as formas funcionais corretas estejam codificadas como
features. O modelo em produção é a logística: mesma performance, coeficientes
lidos direto em razão de chances, e nenhuma dependência de SHAP para explicar
um caso individual ao gestor.

Isso não é argumento contra gradient boosting. É argumento contra escolher o
modelo antes de medir.

## 2. Calibração isotônica piorou o resultado

Isotônica precisa de volume de positivos para não decorar a cauda. Com 140
positivos na validação, produziu probabilidade máxima de 1,00 e derrubou a
AUC-PR de 0,135 para 0,118. Platt, com dois parâmetros, ficou estável e
melhorou o Brier nos dois modelos.

A curva de confiabilidade final tem desvio abaixo de 2 pontos percentuais em 8
dos 10 decis. É isso que autoriza multiplicar a probabilidade por reais.

## 3. O limiar de corte é individual, e a diferença chega a 2,5x

| Criticidade da área | Custo mediano de perder | Limiar de acionamento |
|---|---|---|
| Alta | R$ 89.298 | **4,7%** |
| Média | R$ 50.455 | 8,3% |
| Baixa | R$ 36.268 | 11,5% |

Deriva de `p × eficácia × custo_perder > custo_ação`. Uma pessoa com 6% de
probabilidade em área crítica merece ação; a mesma probabilidade em área de
baixa criticidade não. Um limiar único não representa isso.

## 4. Acionar o decil superior quase não paga

| Política | Acionados | Investimento | Custo evitado | Resultado | ROI |
|---|---|---|---|---|---|
| Limiar individual | 418 (13,8%) | R$ 261.250 | R$ 403.412 | **R$ 142.162** | 0,54 |
| Top 10% por R$ em risco | 303 (10,0%) | R$ 189.375 | R$ 310.273 | R$ 120.898 | **0,64** |
| Top 10% por probabilidade | 303 (10,0%) | R$ 189.375 | R$ 193.254 | R$ 3.879 | 0,02 |
| Limiar fixo 0,50 | 0 | — | — | — | — |

Duas leituras que interessam:

**`predict()` é inútil aqui.** Nenhuma probabilidade chega a 0,50 num evento de
6% de prevalência. Qualquer projeto que use o limiar padrão entrega lista vazia
e conclui que o modelo não funcionou.

**Ordenar por probabilidade é pior que ordenar por dinheiro.** Mesmo número de
acionados, ROI de 0,02 contra 0,64. O decil de maior probabilidade concentra
cargos de alta rotatividade e baixa criticidade, exatamente onde reter erra
barato mas também perde barato.

## 5. Ajuste salarial como ferramenta de retenção não sobrevive à conta

O limiar da camada 2 fica em 1,00 para praticamente todo o quadro: corrigir o
posicionamento até a mediana custa, anualizado e carregado, uma fração grande
demais do custo de reposição para compensar em valor esperado, mesmo com
eficácia incremental de 30 pontos.

A conclusão precisa de uma ressalva. O modelo trata o aumento como custo puro
de retenção. Se a pessoa está de fato abaixo da faixa, a correção resolve um
problema de posicionamento de mercado que existe independentemente do risco de
saída, e o valor esperado não é o quadro completo. O que o número diz é mais
estreito e ainda assim útil: **não use o score de propensão como justificativa
para aumento.** Use-o para priorizar conversas.

## 6. O SHAP contradisse o gabarito, e o gabarito estava certo

Ranking do SHAP no XGBoost:

| # | Feature | Participação |
|---|---|---|
| 1 | meses_de_casa | 27,9% |
| 2 | idade | 18,7% |
| 3 | salario | 14,0% |
| 4 | pico_tenure | 13,5% |
| 5 | modelo_trabalho | 9,8% |

O gerador da base coloca estagnação de carreira e posicionamento salarial no
topo. O SHAP colocou tempo de casa, idade e salário — três variáveis
correlacionadas com os drivers reais e nenhuma delas acionável.

Duas causas, e as duas aparecem em projeto real:

**Crédito dividido entre features correlacionadas.** Quem nunca foi promovido
tem `meses_sem_promocao` igual a `meses_de_casa`. A árvore escolhe uma e o SHAP
atribui a ela o efeito das duas. SHAP explica o *modelo*, não o mundo.

**Proxies não acionáveis vencem causas acionáveis.** `salario` é proxy de
senioridade, `idade` de estágio de vida. Ambos preveem bem e não geram ação
nenhuma de RH. Pior: um modelo que se apoia em idade para ordenar pessoas é um
problema de conformidade esperando para acontecer. Foi por isso que a lista de
fatores exibida no drill-through ficou restrita a fatores acionáveis.

Os coeficientes da logística, depois de removidas as features colineares,
recuperaram a direção correta de todos os efeitos: horas extras e trabalho
presencial aumentam o risco; tempo de casa e posicionamento relativo ao time
reduzem.

## 7. A premissa que mais move o resultado

| Eficácia da conversa | Acionados | Resultado líquido | ROI |
|---|---|---|---|
| 5% | 7 | R$ 8.402 | 1,92 |
| 10% | 130 | R$ 20.976 | 0,26 |
| **15% (adotada)** | 418 | R$ 142.162 | 0,54 |
| 20% | 772 | R$ 478.642 | 0,99 |
| 30% | 1.360 | R$ 1.278.320 | 1,50 |

O ROI varia de 0,26 a 1,50 conforme uma premissa que ninguém mede. Toda a
conversa sobre AUC importa menos que este parâmetro, e por isso ele aparece
antes do resultado principal em qualquer apresentação deste projeto.

Encaminhamento natural: rodar as conversas como teste controlado em um
subconjunto aleatório dos sinalizados, medir a eficácia real em dois trimestres
e substituir a premissa por evidência.
