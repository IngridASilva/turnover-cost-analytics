# Modelo semântico

## Tabelas importadas

| Tabela | Origem | Grão | Storage |
|---|---|---|---|
| `dim_calendario` | base | dia | Import |
| `dim_colaborador` | base | pessoa | Import |
| `dim_area` | base | área | Import |
| `dim_cargo` | base | família × grade | Import |
| `dim_faixa_salarial` | base | cargo × ano | Import |
| `fato_headcount_mensal` | base | matrícula × mês | Import |
| `fato_folha_mensal` | base | matrícula × mês | Import |
| `fato_movimentacao` | base | evento | Import |
| `fato_desligamento_custo` | base | desligamento | Import |
| `fato_scoring` | `reports/` | matrícula × mês | Import |
| `dim_faixa_risco` | tabela DAX | faixa | Calculada |
| `p_eficacia` | what-if | parâmetro | Calculada |

`dim_colaborador` entra **sem a coluna `nome`** no modelo publicado para
gestores. Ver a seção de RLS.

## Relacionamentos

Todas 1:N, filtro em direção única (dimensão → fato). Nenhuma bidirecional:
ativar filtro cruzado aqui cria caminhos ambíguos entre `fato_scoring` e
`fato_folha_mensal` via `dim_colaborador` e quebra as medidas de custo.

```
dim_calendario[id_mes]      1 → N  fato_headcount_mensal[id_mes]
dim_calendario[id_mes]      1 → N  fato_folha_mensal[id_mes]
dim_calendario[id_mes]      1 → N  fato_scoring[id_mes]
dim_calendario[id_data]     1 → N  fato_movimentacao[data_evento]
dim_calendario[id_data]     1 → N  fato_desligamento_custo[data_evento]
dim_colaborador[matricula]  1 → N  todos os fatos
dim_area[id_area]           1 → N  fato_headcount_mensal, fato_scoring
dim_cargo[id_cargo]         1 → N  fato_headcount_mensal, fato_scoring
dim_faixa_risco[faixa]      1 → N  fato_scoring[faixa_risco]
```

`dim_calendario` marcada como tabela de datas em `data`. Sem isso,
`DATEADD` e `SAMEPERIODLASTYEAR` falham silenciosamente ou devolvem resultado
errado em meses parciais.

### A relação que exige atenção

`dim_faixa_salarial` tem chave composta (`id_cargo` + `ano`). O Power BI não
aceita relação composta, então crie uma coluna em ambos os lados:

```dax
// em dim_faixa_salarial
chave_faixa = dim_faixa_salarial[id_cargo] & "|" & FORMAT(dim_faixa_salarial[ano], "0000")

// em fato_headcount_mensal
chave_faixa = fato_headcount_mensal[id_cargo] & "|" & LEFT(FORMAT(fato_headcount_mensal[id_mes], "000000"), 4)
```

Alternativa sem coluna calculada, usando `TREATAS` dentro da medida, está em
`medidas_dax.md` na seção de equidade. Prefira a coluna: `TREATAS` em medida
de alta cardinalidade custa caro no VertiPaq.

## Tabelas auxiliares

```dax
dim_faixa_risco =
DATATABLE(
    "faixa",      STRING,
    "ordem",      INTEGER,
    "cor",        STRING,
    "acao_padrao", STRING,
    {
        { "Baixo",    1, "#6B7280", "Monitorar" },
        { "Moderado", 2, "#D97706", "Conversa no ciclo regular" },
        { "Elevado",  3, "#DC2626", "Conversa em 30 dias" },
        { "Crítico",  4, "#7F1D1D", "Conversa em 15 dias + plano" }
    }
)
```

Parâmetro what-if para a eficácia da conversa de carreira, que é a premissa
mais frágil do projeto:

```dax
p_eficacia = GENERATESERIES(0.05, 0.40, 0.05)
```

Marque `Valor do p_eficacia` como medida do parâmetro. Ela alimenta as
medidas de ROI e faz o usuário ver, na própria tela, quanto o resultado
depende de uma premissa não medida. É a diferença entre apresentar um número
e apresentar um intervalo defensável.

## Performance

**Colunas removidas na importação:** `hash_documento`, `nome` (no modelo de
gestores), `label` (é o desfecho observado, usado só na validação — não deve
circular em relatório operacional).

**Tipos:** force `id_mes` para inteiro e `matricula` para inteiro. Texto em
chave de relacionamento de alta cardinalidade é o erro mais caro num modelo
de RH, porque `fato_headcount_mensal` tem ~94 mil linhas e a compressão de
inteiro é uma ordem de grandeza melhor.

**Agregações:** com 94 mil linhas não são necessárias. Se a base real trouxer
histórico de 10 anos e 20 mil pessoas (~2,4 milhões de linhas), crie uma
tabela agregada por `id_mes` × `id_area` e configure agregação automática
para as medidas de headcount e folha.

## Segurança em nível de linha

Duas funções.

**`Gestor`** — vê apenas a própria estrutura:

```dax
// em dim_area
[id_area] IN
    SELECTCOLUMNS(
        FILTER(
            dim_mapeamento_acesso,
            dim_mapeamento_acesso[email] = USERPRINCIPALNAME()
        ),
        "id_area", dim_mapeamento_acesso[id_area]
    )
```

**`RH_Corporativo`** — sem filtro, mas publicada em workspace separado.

A tabela `dim_mapeamento_acesso` (email, id_area) não vem da base sintética;
é a ponte com o Entra ID e precisa ser mantida pelo próprio RH.

### Supressão por n mínimo

RLS não resolve exposição individual. Um gestor com três subordinados que vê
salário médio do time sabe o salário de cada um. Toda medida que cruze
remuneração com recorte sensível passa pela supressão em `medidas_dax.md`.

## Atualização

| Item | Configuração |
|---|---|
| Origem | Parquet em ADLS Gen2 ou SharePoint |
| Frequência | Mensal, dia 3, após o fechamento da folha |
| Gateway | Necessário só se a origem for on-premises |
| Pipeline | Dev → Teste → Produção com regras de parâmetro de origem |

O `fato_scoring` é regenerado pelo GitHub Actions no dia 2. A atualização do
dataset no dia 3 garante que o Power BI leia o arquivo novo. Se inverter a
ordem, o relatório mostra o score do mês anterior sem nenhum aviso — falha
silenciosa, a pior categoria.

Configure alerta de falha de atualização para o e-mail do time, não para uma
pessoa.
