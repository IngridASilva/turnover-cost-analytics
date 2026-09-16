# Medidas DAX

Todas as medidas do modelo, com a razão de cada escolha. O `.pbix` é uma
caixa-preta no GitHub — este arquivo é o que torna o trabalho revisável.

Convenção: prefixo de grupo no nome da tabela de medidas (`_Medidas`),
variáveis em `PascalCase`, nenhuma medida escrevendo `FILTER(ALL(...))` onde
`KEEPFILTERS` resolve.

---

## 1. Quadro de pessoal

`fato_headcount_mensal` é uma foto mensal, então headcount é **semiaditivo**:
soma ao longo de área, não ao longo do tempo. Somar 12 meses devolve 12 vezes
o quadro, que é o erro mais comum em modelo de RH.

```dax
Headcount =
VAR UltimoMes = MAX ( fato_headcount_mensal[id_mes] )
RETURN
    CALCULATE (
        DISTINCTCOUNT ( fato_headcount_mensal[matricula] ),
        KEEPFILTERS ( fato_headcount_mensal[id_mes] = UltimoMes )
    )
```

```dax
Headcount Médio =
AVERAGEX (
    VALUES ( dim_calendario[id_mes] ),
    CALCULATE ( DISTINCTCOUNT ( fato_headcount_mensal[matricula] ) )
)
```

`Headcount Médio` é o denominador correto de turnover. Usar o headcount final
subestima a taxa em empresa que cresce e superestima em empresa que encolhe —
e nenhuma das duas distorções é pequena no ano de contenção.

```dax
Admissões =
CALCULATE (
    DISTINCTCOUNT ( dim_colaborador[matricula] ),
    USERELATIONSHIP ( dim_colaborador[data_admissao], dim_calendario[data] )
)
```

Exige relação inativa entre `dim_colaborador[data_admissao]` e
`dim_calendario[data]`. A relação ativa é por matrícula; criar uma segunda
relação ativa por data geraria ambiguidade.

---

## 2. Turnover

```dax
Desligamentos =
CALCULATE (
    COUNTROWS ( fato_movimentacao ),
    KEEPFILTERS ( fato_movimentacao[tipo_evento] = "Desligamento" )
)
```

```dax
Desligamentos Voluntários =
CALCULATE (
    [Desligamentos],
    KEEPFILTERS ( dim_colaborador[tipo_desligamento] = "Voluntário" )
)
```

```dax
Turnover Voluntário 12M =
VAR Periodo =
    DATESINPERIOD ( dim_calendario[data], MAX ( dim_calendario[data] ), -12, MONTH )
VAR Saidas    = CALCULATE ( [Desligamentos Voluntários], Periodo )
VAR QuadroMed = CALCULATE ( [Headcount Médio], Periodo )
RETURN
    DIVIDE ( Saidas, QuadroMed )
```

Janela móvel de 12 meses, não acumulado do ano. Turnover no acumulado do ano
é ruído puro em janeiro e só fica legível em novembro, o que o torna inútil
para gestão.

```dax
Turnover Voluntário 12M AA =
CALCULATE ( [Turnover Voluntário 12M], SAMEPERIODLASTYEAR ( dim_calendario[data] ) )
```

```dax
Custo Realizado de Turnover =
SUM ( fato_desligamento_custo[custo_total_desligamento] )
```

---

## 3. Folha e decomposição da variação

```dax
Custo Folha = SUM ( fato_folha_mensal[custo_total] )

Salário Base = SUM ( fato_folha_mensal[salario] )

Fator Custo sobre Salário = DIVIDE ( [Custo Folha], [Salário Base] )
```

O fator acima costuma ser a primeira surpresa numa reunião de orçamento.
Encargos, provisões e benefícios levam o custo real a cerca de 1,9 vez o
salário — e o número é maior nos salários baixos, porque vale-refeição e plano
de saúde são valores fixos e portanto regressivos.

### Ponte com FP&A: de onde veio o aumento da folha

A pergunta que o controller sempre faz é quanto do crescimento veio de
reajuste e quanto veio de gente nova. `fato_movimentacao` responde:

```dax
Impacto Dissídio =
CALCULATE (
    SUMX (
        fato_movimentacao,
        fato_movimentacao[salario_novo] - fato_movimentacao[salario_anterior]
    ),
    KEEPFILTERS ( fato_movimentacao[tipo_evento] = "Dissídio" )
)
```

```dax
Impacto Mérito =
CALCULATE (
    SUMX (
        fato_movimentacao,
        fato_movimentacao[salario_novo] - fato_movimentacao[salario_anterior]
    ),
    KEEPFILTERS ( fato_movimentacao[tipo_evento] = "Mérito" )
)

Impacto Promoção =
CALCULATE (
    SUMX (
        fato_movimentacao,
        fato_movimentacao[salario_novo] - fato_movimentacao[salario_anterior]
    ),
    KEEPFILTERS ( fato_movimentacao[tipo_evento] = "Promoção" )
)
```

```dax
Variação Salário Base =
VAR Atual   = [Salário Base]
VAR Anterior = CALCULATE ( [Salário Base], DATEADD ( dim_calendario[data], -1, MONTH ) )
RETURN
    Atual - Anterior

// Resíduo: o que não veio de reajuste individual veio de movimentação de quadro.
Impacto Headcount =
[Variação Salário Base] - [Impacto Dissídio] - [Impacto Mérito] - [Impacto Promoção]
```

As quatro medidas alimentam um gráfico de cascata que fecha exatamente com a
variação total. É a visualização que transforma o painel de RH em ferramenta
de Finanças.

---

## 4. Risco financeiro

`fato_scoring` também é foto mensal. Mesma regra semiaditiva.

```dax
_ScoringMesAtual =
VAR UltimoMes = MAX ( fato_scoring[id_mes] )
RETURN
    CALCULATETABLE ( fato_scoring, KEEPFILTERS ( fato_scoring[id_mes] = UltimoMes ) )
```

Como o DAX não tem tabela de medida reutilizável, repita o padrão de
`UltimoMes` nas medidas abaixo ou materialize uma coluna booleana
`eh_mes_atual` no Power Query. A segunda opção é mais rápida e mais legível.

```dax
R$ em Risco =
VAR UltimoMes = MAX ( fato_scoring[id_mes] )
RETURN
    CALCULATE (
        SUMX ( fato_scoring, fato_scoring[probabilidade] * fato_scoring[custo_perder] ),
        KEEPFILTERS ( fato_scoring[id_mes] = UltimoMes )
    )
```

Leitura: perda esperada em reais nos próximos seis meses se nada for feito.
Não é previsão de caixa — é a soma de probabilidades ponderadas por custo, e
essa distinção precisa estar no tooltip do cartão.

```dax
Probabilidade Média Ponderada =
DIVIDE ( [R$ em Risco], [Custo de Perder Total] )

Custo de Perder Total =
VAR UltimoMes = MAX ( fato_scoring[id_mes] )
RETURN
    CALCULATE (
        SUM ( fato_scoring[custo_perder] ),
        KEEPFILTERS ( fato_scoring[id_mes] = UltimoMes )
    )
```

```dax
Concentração do Risco =
VAR UltimoMes = MAX ( fato_scoring[id_mes] )
VAR Tabela =
    CALCULATETABLE (
        ADDCOLUMNS (
            fato_scoring,
            "@risco", fato_scoring[probabilidade] * fato_scoring[custo_perder]
        ),
        KEEPFILTERS ( fato_scoring[id_mes] = UltimoMes )
    )
VAR N        = COUNTROWS ( Tabela )
VAR Decil    = ROUNDUP ( N * 0.1, 0 )
VAR TopDecil = TOPN ( Decil, Tabela, [@risco], DESC )
RETURN
    DIVIDE ( SUMX ( TopDecil, [@risco] ), SUMX ( Tabela, [@risco] ) )
```

Quanto do risco total está concentrado em 10% das pessoas. Se der 45%, a
campanha é viável; se der 12%, o risco é difuso e nenhuma ação individual
resolve — o problema é sistêmico e a resposta é política, não lista.

---

## 5. Decisão e retorno, com what-if

O parâmetro `p_eficacia` deixa a premissa mais frágil do projeto visível na
própria tela. Quem discorda do número move o controle e vê o resultado mudar,
em vez de discutir a conclusão no escuro.

```dax
Eficácia Selecionada = SELECTEDVALUE ( p_eficacia[p_eficacia], 0.15 )
```

```dax
Acionáveis =
VAR Eficacia  = [Eficácia Selecionada]
VAR UltimoMes = MAX ( fato_scoring[id_mes] )
RETURN
    CALCULATE (
        COUNTROWS (
            FILTER (
                fato_scoring,
                fato_scoring[probabilidade] * Eficacia * fato_scoring[custo_perder]
                    > fato_scoring[custo_conversa]
            )
        ),
        KEEPFILTERS ( fato_scoring[id_mes] = UltimoMes )
    )
```

Esta é a medida central do projeto. O limiar não é uma constante: cada linha
compara contra o próprio custo de perder. Uma pessoa com 6% de probabilidade
em área crítica entra na lista; a mesma probabilidade em área de baixa
criticidade fica de fora.

```dax
Investimento Campanha =
VAR Eficacia  = [Eficácia Selecionada]
VAR UltimoMes = MAX ( fato_scoring[id_mes] )
RETURN
    CALCULATE (
        SUMX (
            FILTER (
                fato_scoring,
                fato_scoring[probabilidade] * Eficacia * fato_scoring[custo_perder]
                    > fato_scoring[custo_conversa]
            ),
            fato_scoring[custo_conversa]
        ),
        KEEPFILTERS ( fato_scoring[id_mes] = UltimoMes )
    )
```

```dax
Custo Evitado Esperado =
VAR Eficacia  = [Eficácia Selecionada]
VAR UltimoMes = MAX ( fato_scoring[id_mes] )
RETURN
    CALCULATE (
        SUMX (
            FILTER (
                fato_scoring,
                fato_scoring[probabilidade] * Eficacia * fato_scoring[custo_perder]
                    > fato_scoring[custo_conversa]
            ),
            fato_scoring[probabilidade] * Eficacia * fato_scoring[custo_perder]
        ),
        KEEPFILTERS ( fato_scoring[id_mes] = UltimoMes )
    )
```

```dax
ROI da Campanha =
DIVIDE (
    [Custo Evitado Esperado] - [Investimento Campanha],
    [Investimento Campanha]
)
```

```dax
Rótulo ROI =
VAR R = [ROI da Campanha]
RETURN
    SWITCH (
        TRUE (),
        ISBLANK ( R ),  "Sem pessoas acima do limiar",
        R < 0,          "Campanha não se paga nesta premissa",
        R < 0.30,       "Retorno marginal — reavaliar escopo",
        FORMAT ( R, "0%" ) & " de retorno esperado"
    )
```

Cartão com texto em vez de número solto. Um ROI de −0,12 num cartão grande e
vermelho comunica melhor que qualquer gráfico, e evita que alguém leve o
número para uma apresentação sem o contexto.

---

## 6. Privacidade nas visualizações

RLS não impede exposição individual. Um gestor com três subordinados que vê o
salário médio do time deduz o salário de cada um.

```dax
_N Mínimo = 5

Salário Mediano (protegido) =
VAR N = DISTINCTCOUNT ( fato_headcount_mensal[matricula] )
RETURN
    IF ( N < [_N Mínimo], BLANK (), MEDIANX ( fato_headcount_mensal, fato_headcount_mensal[salario] ) )
```

```dax
Compa-Ratio Médio (protegido) =
VAR N = DISTINCTCOUNT ( fato_headcount_mensal[matricula] )
RETURN
    IF ( N < [_N Mínimo], BLANK (), AVERAGE ( fato_headcount_mensal[compa_ratio] ) )
```

```dax
Aviso de Supressão =
VAR N = DISTINCTCOUNT ( fato_headcount_mensal[matricula] )
RETURN
    IF ( N < [_N Mínimo], "Grupo com menos de 5 pessoas — valor suprimido" )
```

Aplique a supressão a **toda** medida de remuneração usada em recorte por
gênero, raça/cor, área pequena ou gestor. Se uma única medida escapar, o
controle inteiro perde sentido.

---

## 7. Fatores acionáveis para o drill-through

O SHAP explica o modelo; o gestor precisa de causa acionável. Estas medidas
traduzem a linha do colaborador em linguagem de conversa. Dizer a um gestor
que a pessoa tem 34 anos não produz ação; dizer que está há 31 meses sem
promoção, sim.

```dax
Fator Estagnação =
VAR Meses = SELECTEDVALUE ( fato_scoring[meses_sem_promocao] )
RETURN
    IF ( Meses >= 24, "Sem promoção há " & FORMAT ( Meses, "0" ) & " meses" )
```

```dax
Fator Posicionamento =
VAR Compa = SELECTEDVALUE ( fato_scoring[compa_ratio] )
RETURN
    IF (
        Compa < 0.92,
        "Salário " & FORMAT ( 1 - Compa, "0%" ) & " abaixo da mediana da faixa"
    )
```

```dax
Fator Liderança =
VAR TO = SELECTEDVALUE ( fato_scoring[turnover_12m_gestor] )
RETURN
    IF ( TO >= 0.25, "Time do gestor com " & FORMAT ( TO, "0%" ) & " de saída em 12 meses" )
```

```dax
Fatores Acionáveis =
VAR Lista =
    FILTER (
        { [Fator Estagnação], [Fator Posicionamento], [Fator Liderança] },
        NOT ISBLANK ( [Value] )
    )
RETURN
    IF (
        ISEMPTY ( Lista ),
        "Nenhum fator acionável isolado — risco difuso",
        CONCATENATEX ( Lista, [Value], UNICHAR ( 10 ) )
    )
```

Note o que **não** aparece: idade, gênero, raça/cor e tempo de casa. Os três
primeiros por razão ética e de conformidade, o quarto porque não é acionável.
Exibir idade num painel que ordena pessoas para intervenção é criar prova
documental de critério etário.

---

## 8. Formatação condicional

```dax
Cor da Faixa de Risco =
SWITCH (
    SELECTEDVALUE ( fato_scoring[faixa_risco] ),
    "Crítico",  "#7F1D1D",
    "Elevado",  "#DC2626",
    "Moderado", "#D97706",
    "#6B7280"
)
```

```dax
Cor do Compa-Ratio =
VAR Compa = [Compa-Ratio Médio (protegido)]
RETURN
    SWITCH (
        TRUE (),
        ISBLANK ( Compa ), "#E5E7EB",
        Compa < 0.90,      "#DC2626",
        Compa > 1.12,      "#D97706",
        "#059669"
    )
```

Compa-ratio alto também é sinalizado, em âmbar. Pagar muito acima da faixa não
é virtude: é perda de margem e criação de uma pessoa impossível de promover
sem quebrar a estrutura.
