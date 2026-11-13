# Correção do gráfico de orçamento — FMABC Eventos

## Problema corrigido
O JavaScript do gráfico era executado antes de a tabela de despesas existir no HTML. Assim, a leitura de `[data-budget-category]` encontrava zero linhas e o gráfico ficava em R$ 0,00 mesmo com despesas cadastradas.

## Aplicação
1. Faça backup da pasta do projeto.
2. Pare o servidor local.
3. Copie `templates/event_budget.html` deste pacote para a pasta `templates` do projeto, substituindo o arquivo existente.
4. Não substitua o banco de dados nem o arquivo `.env`.
5. Reinicie o servidor e recarregue a página com Ctrl+F5.

## Teste esperado
Para uma despesa não cancelada com categoria `Alimentação`, previsto R$ 100,00, contratado R$ 150,00 e realizado vazio, o gráfico deve mostrar total de R$ 150,00 e 100% em Alimentação. Ao salvar alterações de valor, a página recarrega e o gráfico recalcula os valores.
