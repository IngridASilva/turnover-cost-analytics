# turnover-cost-analytics

![CI](https://github.com/IngridASilva/turnover-cost-analytics/actions/workflows/ci.yml/badge.svg)

Modelo calibrado de propensão de saída voluntária cruzado com o custo
financeiro de perder cada pessoa, entregando uma lista de acionamento onde o
limiar de corte é individual.

Base sintética longitudinal: [hr-synthetic-data-br](../hr-synthetic-data-br).

```bash
pip install -e ".[dev]"
turnover-pipeline --base data_base --saida reports
```

---

## A pergunta

Um modelo de turnover que entrega probabilidade não resolve nada. A diretoria
não decide com base em 0,11; decide com base em quanto custa agir e quanto
custa não agir.

Este projeto responde três perguntas em sequência:

1. Quem tem risco de sair nos próximos 6 meses, com probabilidade confiável?
2. Quanto custa perder cada uma dessas pessoas?
3. Sobre quem vale a pena gastar, e quanto?

## Desenho

**Janela de predição:** 6 meses. Prevalência resultante de 5,4%.

**Grão:** person-month amostrado trimestralmente. O painel completo tem 94 mil
linhas, mas a mesma pessoa aparece em até 60 meses com features quase
idênticas — isso infla o n sem acrescentar informação e contamina validação
cruzada aleatória. A amostragem trimestral entrega 25.878 observações com
autocorrelação muito menor.

**Rótulo:** pedido de demissão. Dispensa pela empresa dentro da janela é
removida da amostra, não rotulada como negativo. Manter como 0 ensinaria ao
modelo que a pessoa "ia ficar", o que é falso: ela foi censurada por um evento
concorrente.

**Corte temporal:** treino até abr/2024, calibração em jul–out/2024, teste em
jan–abr/2025. Sem sobreposição de horizonte entre partições.

**Fora das features por decisão, não por esquecimento:** gênero, raça/cor,
identificadores e os arquivos de gabarito da base.

## Engenharia de features

Além das cadastrais, três blocos:

**Formas funcionais.** A inspeção de PDP sugeriu que estagnação satura e que o
risco por tempo de casa é um U invertido. Em vez de aceitar a caixa-preta,
codificamos as formas: `log_meses_sem_promocao`, `pico_tenure`,
`subremuneracao` (assimétrica) e a interação `perf_x_subremuneracao`.

**Features de equipe.** O gerador da base embute um efeito latente de liderança
que não existe em nenhuma coluna. A única forma de capturá-lo é agregar por
gestor: `turnover_12m_gestor` (estritamente retrospectivo),
`compa_ratio_medio_time`, `meses_sem_promocao_medio_time`. Sem elas o modelo
aponta pessoas; com elas, aponta problemas de gestão.

**Posição relativa.** `compa_ratio_vs_time` mede o quanto a pessoa está abaixo
dos próprios colegas, que é a comparação que ela de fato faz.

Features colineares foram removidas depois que os coeficientes da logística
começaram a trocar de sinal entre formas equivalentes. Detalhes em
`docs/achados.md`.

## Resultado

| Modelo | AUC-ROC | AUC-PR | Brier | Lift decil 1 |
|---|---|---|---|---|
| **Logística calibrada (produção)** | **0,707** | 0,138 | **0,0542** | 2,35 |
| XGBoost calibrado | 0,687 | 0,138 | 0,0544 | 2,40 |

Calibração por Platt. A isotônica foi testada e descartada: com 140 positivos
na validação ela decorou a cauda e derrubou a AUC-PR.

A calibração importa mais que a AUC neste projeto, porque a camada seguinte
multiplica probabilidade por reais. Um modelo descalibrado produz um número
financeiro errado com aparência de precisão.

## A camada econômica

O custo de agir sobre um falso positivo não é um número único. São duas
decisões independentes, cada uma com custo, eficácia e limiar próprios:

| | Camada 1 — conversa de carreira | Camada 2 — correção salarial |
|---|---|---|
| Custo | tempo de gestor e RH | gap até a mediana, anualizado e carregado |
| Eficácia | 15% isolada | 45% total (+30 pontos) |
| Limiar | `c₁ / (e₁ × custo_perder)` | `c₂ / ((e₂−e₁) × custo_perder)` |

Como `custo_perder` varia por pessoa, **o limiar é individual**:

| Criticidade | Custo mediano de perder | Limiar |
|---|---|---|
| Alta | R$ 89.298 | 4,7% |
| Média | R$ 50.455 | 8,3% |
| Baixa | R$ 36.268 | 11,5% |

Aplicado ao conjunto de teste: 418 pessoas acionadas (13,8% do quadro),
R$ 261 mil de investimento, R$ 403 mil de custo evitado, **ROI de 0,54**.

A política ingênua de acionar o decil de maior probabilidade, com o mesmo
esforço, entrega ROI de 0,02. O limiar fixo de 0,50 entrega lista vazia.

## O que não funcionou

Três resultados negativos que valem mais que os positivos, documentados em
`docs/achados.md`:

- XGBoost não superou a logística neste regime de dados.
- Ajuste salarial como ferramenta de retenção não sobrevive ao cálculo de
  valor esperado.
- O ranking do SHAP contradisse o gabarito documentado da base, e o gabarito
  estava certo. O modelo se apoiou em tempo de casa, idade e salário — três
  proxies não acionáveis, sendo que um deles é um risco de conformidade.

## Dashboard

O modelo semântico, as medidas DAX e o wireframe das telas estão especificados
em `powerbi/`. **O arquivo `.pbix` ainda não está neste repositório** — a
especificação veio primeiro de propósito, porque tela desenhada antes de ser
construída custa muito menos para corrigir.

| Arquivo | Conteúdo |
|---|---|
| `powerbi/wireframe.md` | Quatro telas, com a razão de cada decisão de layout |
| `powerbi/modelo_semantico.md` | Relacionamentos, RLS, supressão por n mínimo, atualização |
| `powerbi/medidas_dax.md` | Biblioteca de medidas documentada, uma a uma |
| `powerbi/consultas_powerquery.m` | Consultas de carga em linguagem M |

A decisão de desenho que mais importa: a lista operacional ordena por
valor esperado da ação, não por probabilidade nem por R$ em risco.
Probabilidade sozinha entrega retorno de 2%; o critério econômico entrega
54%.

O parâmetro what-if da eficácia da conversa fica **acima** dos KPIs, não ao
lado. A premissa mais frágil do projeto aparece antes do resultado que ela
produz.


## Monitoramento

Duas derivas, com consequências diferentes. A de features (PSI) diz que a
população mudou. A de calibração diz que as probabilidades deixaram de bater
com a realidade — esta é a crítica, porque a camada financeira multiplica
probabilidade por reais, e um modelo que ainda ordena bem mas superestima o
nível produz um valor em reais inflado sem que a AUC acuse nada.

Na execução atual o monitoramento acusa deriva crítica em 6 features: o quadro
envelheceu (tempo médio de time de 45 para 58 meses) e a progressão salarial
desacelerou. É o efeito do ano de contenção de 2024 no cenário simulado, e é
exatamente o que o alerta deveria pegar.

## Estrutura

```
src/turnover/
  dataset.py     rótulo, corte temporal, features individuais e de equipe
  model.py       horse race, calibração, métricas, curva de confiabilidade
  economics.py   custos, limiar individual, simulação de campanha
  explain.py     SHAP global e local, conferência contra o gabarito
  pipeline.py    execução ponta a ponta
  monitor.py     PSI, deriva de calibração, alertas
tests/           8 testes: vazamento temporal, colunas proibidas, inversão
                 de limiar, gap mínimo de ajuste
docs/
  achados.md     resultados comentados, incluindo os negativos
  faq.md         objeções de stakeholder respondidas com os números do projeto
powerbi/
  wireframe.md          quatro telas, com a razão de cada decisão
  modelo_semantico.md   relacionamentos, RLS, supressão, atualização
  medidas_dax.md        biblioteca de medidas documentada
  consultas_powerquery.m
reports/         fato_scoring.parquet, métricas, políticas, monitoramento
```

## Saída para o Power BI

`reports/fato_scoring.parquet`, grão matrícula × mês, com probabilidade, faixa
de risco, custo de perder, R$ em risco, limiar individual e as duas decisões
de acionamento. Relaciona-se com as dimensões da base original pelas mesmas
chaves.

## Ressalvas

Score de propensão é dado pessoal derivado e pode gerar efeito adverso: gestor
que vê "risco alto" pode parar de investir na pessoa, o que vira profecia
autorrealizável. Por isso a entrega é para o RH e não para o gestor de linha,
a comunicação é em faixas e não em decimais, e o drill-through exibe apenas
fatores acionáveis.

A eficácia da conversa de carreira é premissa, não medida. Ela move o ROI de
0,26 a 1,50. O encaminhamento correto é rodar as conversas como teste
controlado num subconjunto aleatório dos sinalizados e substituir a premissa
por evidência em dois trimestres.
