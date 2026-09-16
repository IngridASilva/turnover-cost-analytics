# Wireframe

Quatro telas, três públicos. A regra que organiza tudo: **cada tela responde a
uma pergunta e ordena por uma métrica só.** Painel que tenta servir diretoria e
business partner na mesma tela não serve nenhum dos dois.

| Tela | Público | Pergunta | Ordenação |
|---|---|---|---|
| 1. Risco financeiro | Diretoria, CFO | Quanto dinheiro está em risco? | R$ em risco |
| 2. Lista de acionamento | RH, business partner | Sobre quem agir neste ciclo? | Valor esperado da ação |
| 3. Ficha individual | BP + gestor | Por que esta pessoa e o que falar? | — |
| 4. Saúde do modelo | Analista, auditoria | Dá para confiar nos números? | — |

---

## Tela 1 — Risco financeiro

```
┌──────────────────────────────────────────────────────────────────────────┐
│  Risco de turnover  ·  Posição de abr/2025        [Diretoria ▾] [Mês ▾]  │
├──────────────────────────────────────────────────────────────────────────┤
│ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────────┐  │
│ │ R$ EM RISCO  │ │ TURNOVER 12M │ │ CONCENTRAÇÃO │ │ CUSTO REALIZADO  │  │
│ │              │ │              │ │              │ │ 12M              │  │
│ │  R$ 4,2 mi   │ │    12,4%     │ │  38% em 10%  │ │   R$ 8,6 mi      │  │
│ │  ▲ vs mês    │ │  ▼ 1,1 p.p.  │ │  das pessoas │ │                  │  │
│ └──────────────┘ └──────────────┘ └──────────────┘ └──────────────────┘  │
├──────────────────────────────────────────────────────────────────────────┤
│  R$ em risco por diretoria             │  Evolução — risco vs realizado  │
│                                        │                                 │
│  Comercial      ████████████ 1,4 mi    │   ╭─╮      previsto ─────       │
│  Operações      █████████ 1,1 mi       │  ╱   ╲╱╲   realizado ·····      │
│  Tecnologia     ███████ 0,9 mi         │ ╱        ╲                      │
│  Financeira     ████ 0,5 mi            │                                 │
│  Pessoas & Adm  ██ 0,3 mi              │  jan  fev  mar  abr             │
├──────────────────────────────────────────────────────────────────────────┤
│  Mapa de calor: risco médio × criticidade da área                        │
│                    Baixa      Média      Alta                            │
│  Grade 1-2          ░░░        ▒▒▒        ███                            │
│  Grade 3-4          ░░░        ▒▒▒        ▓▓▓                            │
│  Grade 5+           ░░░        ░░░        ▒▒▒                            │
└──────────────────────────────────────────────────────────────────────────┘
```

**Cartão principal.** R$ em risco, não percentual. A diretoria já viu mil
gráficos de turnover em percentual e nenhum deles mudou uma decisão de
orçamento.

**Tooltip obrigatório no cartão:** "Soma de probabilidade × custo de reposição
para os próximos 6 meses. Não é previsão de caixa." Sem isso alguém leva o
número para uma apresentação como se fosse provisão contábil.

**Concentração.** Quanto do risco total está em 10% das pessoas. Se der 38%,
campanha individual faz sentido. Se der 12%, o risco é difuso e a resposta é
política de RH, não lista de nomes.

**Linha previsto vs realizado.** A única prova pública de que o modelo funciona.
Mostre-a mesmo quando estiver ruim — esconder é como o projeto perde
credibilidade de uma vez só, em vez de ganhar aos poucos.

---

## Tela 2 — Lista de acionamento

```
┌──────────────────────────────────────────────────────────────────────────┐
│  Lista de acionamento — abr/2025                                         │
│                                                                          │
│  Eficácia esperada da conversa:  ├──●──────────┤  15%                    │
│                                 5%           40%                         │
├──────────────────────────────────────────────────────────────────────────┤
│ ┌───────────────┐ ┌───────────────┐ ┌───────────────┐ ┌────────────────┐ │
│ │ ACIONÁVEIS    │ │ INVESTIMENTO  │ │ CUSTO EVITADO │ │ RETORNO        │ │
│ │     418       │ │  R$ 261 mil   │ │  R$ 403 mil   │ │ 54% esperado   │ │
│ │ 13,8% do      │ │ ~2.090 horas  │ │               │ │                │ │
│ │ quadro        │ │ de gestor+RH  │ │               │ │                │ │
│ └───────────────┘ └───────────────┘ └───────────────┘ └────────────────┘ │
├──────────────────────────────────────────────────────────────────────────┤
│  Matrícula │ Área        │ Cargo      │ Faixa    │ VE da ação │ R$ risco  │
│  ──────────┼─────────────┼────────────┼──────────┼────────────┼────────── │
│  104382    │ Eng. Softw. │ Analista Sr│ Crítico  │ R$ 3.140   │ R$ 21.500 │
│  102947    │ Controlad.  │ Especial.  │ Elevado  │ R$ 2.880   │ R$ 19.900 │
│  105511    │ Dados & BI  │ Analista Pl│ Elevado  │ R$ 2.410   │ R$ 17.200 │
│  ...                                                                      │
│                                                     [ Exportar CSV ]      │
└──────────────────────────────────────────────────────────────────────────┘
```

**O controle deslizante fica no topo, antes dos números.** Deliberado. A
premissa mais frágil do projeto aparece antes do resultado que ela produz.
Quem discordar move o controle e vê o retorno sair de 26% para 99%, em vez de
discutir a conclusão no escuro.

**Ordenação por valor esperado da ação, não por probabilidade.** Testamos as
duas: ordenar por probabilidade dá retorno de 2%, o critério econômico dá 54%.
A coluna de R$ em risco fica visível para contexto, mas não ordena.

**Investimento em horas, não só em reais.** R$ 261 mil soa abstrato; 2.090
horas de gestor e RH é a decisão real, e é o número que vai gerar objeção
legítima na reunião. Melhor que ele apareça no painel do que na discussão.

**Sem nome e sem foto.** A tabela usa matrícula. Nome só aparece na ficha
individual, atrás de RLS.

---

## Tela 3 — Ficha individual (drill-through)

```
┌──────────────────────────────────────────────────────────────────────────┐
│  ← Voltar          Matrícula 104382 · Analista Sênior · Eng. de Software │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   Faixa de risco: CRÍTICO          Custo estimado de reposição: R$ 78.400│
│                                                                          │
│   Fatores acionáveis                                                     │
│   ─────────────────────────────────────────────────────                  │
│   • Sem promoção há 34 meses                                             │
│   • Salário 11% abaixo da mediana da faixa                               │
│   • Time do gestor com 28% de saída em 12 meses                          │
│                                                                          │
│   Ação sugerida: conversa de carreira em 15 dias + plano de              │
│   desenvolvimento com marco em 90 dias                                    │
│                                                                          │
├──────────────────────────────────────────────────────────────────────────┤
│  Trajetória                                                              │
│  Compa-ratio  ──────╲___                    Promoções: 2 em 6 anos       │
│  Horas extras ____╱‾‾‾‾                     Última: fev/2022             │
│               2023      2024      2025                                   │
└──────────────────────────────────────────────────────────────────────────┘
```

**Só fatores acionáveis.** Idade, gênero, raça/cor e tempo de casa ficam fora.
Os três primeiros por conformidade, o quarto porque não gera ação. Um painel
que ordena pessoas para intervenção e exibe idade cria prova documental de
critério etário.

**Quando nenhum fator dispara**, o campo mostra "risco difuso — sem fator
isolado". É honesto e evita que o BP invente uma explicação.

**A probabilidade numérica não aparece.** Faixa de risco, sim. Dizer a um
gestor que alguém tem 19% de chance de sair convida a interpretar como
previsão; dizer "crítico" comunica prioridade sem falsa precisão.

---

## Tela 4 — Saúde do modelo

```
┌──────────────────────────────────────────────────────────────────────────┐
│  Saúde do modelo                          Última execução: 02/05/2025    │
├──────────────────────────────────────────────────────────────────────────┤
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌─────────────────────────────┐  │
│  │ AUC-ROC  │ │  BRIER   │ │ LIFT D1  │ │  STATUS                     │  │
│  │  0,707   │ │  0,0542  │ │   2,35   │ │  ATENÇÃO                    │  │
│  └──────────┘ └──────────┘ └──────────┘ └─────────────────────────────┘  │
├──────────────────────────────────────────────────────────────────────────┤
│  Calibração: previsto vs observado    │  Deriva de população (PSI)       │
│                                       │                                  │
│   obs ┤        ╱                      │  var_salarial_12m      4,41 ███  │
│       ┤      ╱·                       │  estagnação do time    2,89 ███  │
│       ┤    ╱·                         │  Δ compa-ratio         2,10 ███  │
│       ┤  ╱·                           │  tempo médio do time   0,78 ██   │
│       └──────────── prev              │  ─── limite crítico 0,25         │
├──────────────────────────────────────────────────────────────────────────┤
│  Histórico de alertas                                                    │
│  mai/25  ATENÇÃO   Calibração: subestimando risco em 1,6 p.p.            │
│  mai/25  CRÍTICO   Deriva: 6 features acima do limite — avaliar retreino │
└──────────────────────────────────────────────────────────────────────────┘
```

Esta tela existe porque painel de modelo sem página de saúde do modelo é
painel que ninguém sabe quando parou de funcionar. Alimentada por
`reports/metricas_modelo.csv`, `deriva_features.csv` e
`historico_monitoramento.csv`.

O alerta de deriva na execução atual é real e vale entender: o quadro
envelheceu (tempo médio de time subiu de 45 para 58 meses) e a progressão
salarial desacelerou, porque o cenário simulado tem um ano de contenção em
2024. O monitoramento pegou exatamente o que deveria pegar.

---

## Notas de construção

**Cores.** Uma paleta sequencial para risco (cinza → âmbar → vermelho) e uma
neutra para o resto. Nada de arco-íris. Vermelho aparece só onde significa
risco alto, nunca como cor decorativa.

**Tipografia.** Um tamanho para KPI, um para título de visual, um para corpo.
Três tamanhos resolvem qualquer painel.

**O que não entra.** Medidor de velocímetro, gráfico de pizza com mais de três
fatias, mapa do Brasil com bolhas. Nenhum deles responde às perguntas das
quatro telas.

**Antes de abrir o Power BI**, monte estas quatro telas no PowerPoint ou no
Figma e mostre para uma pessoa de RH que não participou do projeto. Se ela não
souber dizer o que fazer depois de olhar a Tela 2, o problema é de desenho e
sai muito mais barato corrigir agora.
