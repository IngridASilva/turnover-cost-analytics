// ---------------------------------------------------------------------------
// Consultas do Power Query (linguagem M).
//
// Cole cada bloco no Editor Avançado de uma consulta nova. O parâmetro
// pCaminhoBase permite trocar entre desenvolvimento local e produção sem
// reescrever consulta — é o que faz o pipeline de implantação funcionar.
// ---------------------------------------------------------------------------

// === PARÂMETRO ============================================================
// Tipo: Texto. Em produção, aponte para o ADLS Gen2 ou SharePoint.
pCaminhoBase = "C:\projetos\turnover-cost-analytics" meta [
    IsParameterQuery = true,
    Type = "Text",
    IsParameterQueryRequired = true
];


// === FUNÇÃO REUTILIZÁVEL ==================================================
// Evita repetir a lógica de leitura em 11 consultas.
fnLerParquet = (pasta as text, arquivo as text) as table =>
    let
        Caminho  = pCaminhoBase & "\" & pasta & "\" & arquivo & ".parquet",
        Binario  = File.Contents(Caminho),
        Tabela   = Parquet.Document(Binario)
    in
        Tabela;


// === DIMENSÕES ============================================================

dim_calendario =
    let
        Fonte = fnLerParquet("data_base", "dim_calendario"),
        Tipos = Table.TransformColumnTypes(Fonte, {
            {"data", type date},
            {"id_data", Int64.Type},
            {"id_mes", Int64.Type},
            {"ano", Int64.Type},
            {"mes", Int64.Type},
            {"eh_dia_util", type logical}
        }),
        // Ordenação correta do eixo: "Jan/25" precisa ordenar por id_mes,
        // não alfabeticamente. Sem esta coluna o gráfico sai com Abr antes
        // de Jan, que é o erro mais irritante de painel em português.
        Ordem = Table.AddColumn(Tipos, "ordem_ano_mes", each [id_mes], Int64.Type)
    in
        Ordem;


dim_colaborador =
    let
        Fonte = fnLerParquet("data_base", "dim_colaborador"),
        // Colunas sensíveis e identificadores saem na origem, não na camada
        // de visualização. Esconder coluna no relatório não protege nada:
        // o usuário exporta os dados subjacentes.
        Removidas = Table.RemoveColumns(Fonte, {"hash_documento"}),
        Tipos = Table.TransformColumnTypes(Removidas, {
            {"matricula", Int64.Type},
            {"data_admissao", type date},
            {"data_desligamento", type date},
            {"data_nascimento", type date}
        })
    in
        Tipos;


dim_area =
    let
        Fonte = fnLerParquet("data_base", "dim_area"),
        Tipos = Table.TransformColumnTypes(Fonte, {
            {"id_area", Int64.Type},
            {"mes_data_base", Int64.Type}
        })
    in
        Tipos;


dim_cargo =
    let
        Fonte = fnLerParquet("data_base", "dim_cargo"),
        Tipos = Table.TransformColumnTypes(Fonte, {{"grade", Int64.Type}})
    in
        Tipos;


dim_faixa_salarial =
    let
        Fonte = fnLerParquet("data_base", "dim_faixa_salarial"),
        Tipos = Table.TransformColumnTypes(Fonte, {{"ano", Int64.Type}}),
        // Chave composta resolvida aqui. O Power BI não aceita relação
        // com duas colunas, e TREATAS em medida de alta cardinalidade
        // custa caro no VertiPaq.
        Chave = Table.AddColumn(
            Tipos, "chave_faixa",
            each [id_cargo] & "|" & Text.From([ano]), type text
        )
    in
        Chave;


// === FATOS ================================================================

fato_headcount_mensal =
    let
        Fonte = fnLerParquet("data_base", "fato_headcount_mensal"),
        Tipos = Table.TransformColumnTypes(Fonte, {
            {"id_mes", Int64.Type},
            {"matricula", Int64.Type},
            {"id_area", Int64.Type},
            {"id_gestor", Int64.Type},
            {"grade", Int64.Type},
            {"performance", Int64.Type},
            {"data_referencia", type date}
        }),
        Chave = Table.AddColumn(
            Tipos, "chave_faixa",
            each [id_cargo] & "|" & Text.Start(Text.From([id_mes]), 4), type text
        )
    in
        Chave;


fato_folha_mensal =
    let
        Fonte = fnLerParquet("data_base", "fato_folha_mensal"),
        Tipos = Table.TransformColumnTypes(Fonte, {
            {"id_mes", Int64.Type},
            {"matricula", Int64.Type},
            {"id_area", Int64.Type},
            {"data_referencia", type date}
        })
    in
        Tipos;


fato_movimentacao =
    let
        Fonte = fnLerParquet("data_base", "fato_movimentacao"),
        Tipos = Table.TransformColumnTypes(Fonte, {
            {"matricula", Int64.Type},
            {"id_area", Int64.Type},
            {"data_evento", type date}
        })
    in
        Tipos;


fato_desligamento_custo =
    let
        Fonte = fnLerParquet("data_base", "fato_desligamento_custo"),
        Tipos = Table.TransformColumnTypes(Fonte, {
            {"matricula", Int64.Type},
            {"id_area", Int64.Type},
            {"data_evento", type date}
        })
    in
        Tipos;


fato_scoring =
    let
        Fonte = fnLerParquet("reports", "fato_scoring"),
        // `label` é o desfecho observado, usado só na validação do modelo.
        // Não pode circular em relatório operacional: um gestor que vê o
        // desfecho real deixa de agir sobre quem já sabe que vai sair.
        Removidas = Table.RemoveColumns(Fonte, {"label"}),
        Tipos = Table.TransformColumnTypes(Removidas, {
            {"id_mes", Int64.Type},
            {"matricula", Int64.Type},
            {"id_area", Int64.Type},
            {"id_gestor", Int64.Type},
            {"grade", Int64.Type},
            {"data_referencia", type date},
            {"acionar_conversa", type logical},
            {"acionar_material", type logical}
        }),
        // Materializa o mês mais recente como coluna booleana. Resolver isso
        // aqui, e não em cada medida DAX, elimina o padrão repetido de
        // MAX(id_mes) em oito medidas diferentes.
        UltimoMes = List.Max(Tipos[id_mes]),
        Atual = Table.AddColumn(
            Tipos, "eh_mes_atual", each [id_mes] = UltimoMes, type logical
        )
    in
        Atual;


// === MONITORAMENTO ========================================================

monitoramento =
    let
        Caminho = pCaminhoBase & "\reports\historico_monitoramento.csv",
        Fonte = Csv.Document(
            File.Contents(Caminho),
            [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]
        ),
        Cabecalho = Table.PromoteHeaders(Fonte, [PromoteAllScalars = true]),
        Tipos = Table.TransformColumnTypes(Cabecalho, {
            {"id_mes", Int64.Type},
            {"metrica", type number}
        })
    in
        Tipos;


metricas_modelo =
    let
        Caminho = pCaminhoBase & "\reports\metricas_modelo.csv",
        Fonte = Csv.Document(
            File.Contents(Caminho),
            [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]
        ),
        Cabecalho = Table.PromoteHeaders(Fonte, [PromoteAllScalars = true])
    in
        Cabecalho;
