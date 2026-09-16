# FAQ

Perguntas reais de stakeholder, respondidas com os números deste projeto. Cada
resposta cita o resultado que a sustenta, não uma generalidade sobre machine
learning.

---

### "Quanto o modelo acerta?"

Depende do que você chama de acerto. A AUC-ROC é 0,707, o que significa que se
eu sortear uma pessoa que pediu demissão e uma que ficou, o modelo dá nota
maior para a primeira em 71% dos casos.

Só que essa métrica não é a que interessa. A que interessa é o lift: no decil
de maior risco, a taxa de saída é 2,35 vezes a média. E a que decide o
orçamento é o retorno: a lista recomendada custa R$ 261 mil e evita R$ 403 mil
em custo de reposição.

Se a pergunta é "o modelo aponta quem vai sair", a resposta honesta é não.
Nenhum modelo de turnover faz isso. O que ele faz é ordenar o quadro por risco
bem o suficiente para que a ação chegue antes.

### "Por que a minha área aparece com risco alto? O clima está bom."

Clima e risco de saída medem coisas diferentes. Uma pessoa pode gostar do time
e do gestor e ainda assim sair por estagnação de carreira ou por proposta
externa acima da faixa.

Os fatores que o modelo usa são objetivos: tempo sem promoção, posicionamento
salarial contra a faixa do cargo, sobrecarga de horas extras e histórico de
saída do time. Nenhum deles é opinião. Abra o drill-through de qualquer pessoa
da sua lista e você vê exatamente quais fatores pesaram.

Se os três fatores aparecerem em branco, o próprio painel diz "risco difuso" —
e nesse caso o número não sustenta ação individual.

### "Isso vai virar lista de demissão?"

Não, e o desenho do projeto impede. A saída do modelo é entregue ao RH, não ao
gestor de linha, e a comunicação é em faixa de risco, nunca em probabilidade
decimal.

O risco real aqui não é demissão: é o gestor ver "risco alto" e parar de
investir na pessoa, o que transforma a previsão em profecia autorrealizável. É
por isso que a lista de fatores exibida contém apenas causas acionáveis, e é
por isso que o painel sugere a ação junto com o nome.

### "Se eu der aumento, o risco cai?"

Cai, mas a conta não fecha. Testamos exatamente isso.

Corrigir o posicionamento salarial até a mediana da faixa custa, anualizado e
com encargos, uma fração grande demais do custo de reposição. Mesmo assumindo
que o ajuste aumente a chance de retenção em 30 pontos percentuais, o limiar
de probabilidade que justificaria o gasto fica acima de 100% para
praticamente todo o quadro.

Isso não quer dizer que ninguém deva receber ajuste. Quer dizer que **o score
de propensão não é justificativa para aumento**. Se a pessoa está abaixo da
faixa, corrija por ser um problema de posicionamento de mercado, que existe
independentemente de ela estar pensando em sair.

### "Por que vocês não usaram uma IA mais moderna?"

Usamos XGBoost e ele perdeu. AUC-ROC de 0,687 contra 0,707 da regressão
logística, empate técnico na AUC-PR.

Com cerca de mil casos de saída no treino e efeitos que se somam de forma
previsível, não há estrutura complexa para o modelo de árvore explorar. O que
entregou ganho foi engenharia de features: codificar que estagnação satura,
que risco por tempo de casa é uma curva em U e que alto desempenho mal pago é
uma combinação pior que a soma das partes.

O modelo em produção é a logística, e isso tem uma vantagem prática: cada
fator vira uma razão de chances que você lê direto, sem precisar de uma
segunda ferramenta para explicar a primeira.

### "O modelo discrimina por gênero ou raça?"

Gênero e raça/cor não entram como features. Estão bloqueados no código, com
teste automatizado que falha o build se alguém tentar incluí-los.

Isso não basta, porque variáveis correlacionadas podem reintroduzir o viés. Os
dois controles adicionais são: medir a taxa de erro do modelo separadamente
por grupo, verificando se ele erra mais para um deles; e excluir idade da
lista de fatores exibidos, ainda que ela ajude na previsão — um painel que
ordena pessoas para intervenção e exibe idade cria prova documental de
critério etário.

### "Por que a lista tem 418 pessoas e não as 50 de maior risco?"

Porque cortar nas 50 de maior probabilidade destrói o retorno. Testamos:
acionar o decil superior por probabilidade dá retorno de 2%, praticamente
empatando com não fazer nada. A lista recomendada dá 54%.

A razão é que as pessoas de maior probabilidade se concentram em cargos de
alta rotatividade e baixa criticidade, onde perder é barato. O critério certo
não é quem tem mais risco, é sobre quem o gasto se paga — e isso depende tanto
da probabilidade quanto de quanto custa repor aquela pessoa.

O limiar é individual: 4,7% em área crítica, 11,5% em área de baixa
criticidade.

### "Agi na lista e a pessoa saiu mesmo assim. O modelo errou?"

Não necessariamente. A premissa do projeto é que a conversa de carreira
reverte 15% dos casos que de fato sairiam. Ou seja, em 85% das vezes a pessoa
sai apesar da conversa, e isso já está dentro da conta.

O retorno vem do volume, não do caso individual. É a mesma lógica de seguro: a
apólice não impede o sinistro, ela muda o resultado agregado.

### "De onde veio esse número de 15%?"

De lugar nenhum. É premissa, não medição, e está declarada como tal.

O painel tem um controle deslizante para você mudá-la e ver o efeito. Com 10%,
o retorno da campanha cai para 26%. Com 20%, sobe para 99%. A conclusão sobre
o projeto valer a pena depende inteiramente de um número que ninguém mediu.

O encaminhamento correto é medir: rodar as conversas em um subconjunto
aleatório dos sinalizados, deixar o restante como grupo de comparação e apurar
a diferença de saída em dois trimestres. Depois disso a premissa vira
evidência e essa pergunta ganha resposta de verdade.

### "Com que frequência isso atualiza, e o que acontece se a base mudar?"

Scoring mensal, no dia 2, depois do fechamento da folha. O relatório atualiza
no dia 3.

Há monitoramento automático de duas coisas: deriva das features, que detecta
quando a população mudou o suficiente para o modelo ficar desatualizado, e
deriva da calibração, que detecta quando as probabilidades deixam de bater com
a frequência observada. O segundo é o mais crítico, porque a camada financeira
multiplica probabilidade por reais — um modelo descalibrado produz um número
em reais errado com aparência de precisão.

Quando qualquer um dos dois dispara, o pipeline marca o mês e o relatório
exibe o aviso. Retreino sem aviso, silencioso, é como esses projetos morrem.

### "Quanto custa manter isso?"

O pipeline roda em minutos e o custo de execução é irrelevante. O custo real é
o tempo de gestor e de RH nas conversas: cerca de cinco horas por pessoa
acionada, entre preparação, conversa e acompanhamento.

Na lista recomendada isso dá aproximadamente 2.090 horas por ciclo, o que é a
verdadeira decisão de investimento. O número de R$ 261 mil no painel é
exatamente essa conta, não uma despesa de software.
