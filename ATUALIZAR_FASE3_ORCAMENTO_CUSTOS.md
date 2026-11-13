# Atualização — Fase 3: Orçamento e custos do evento

## Recursos incluídos
- Controle separado de valores previstos, contratados e realizados.
- Categorias para alimentação, estrutura, audiovisual, materiais, comunicação, transporte, hospedagem, serviços, equipe, tecnologia e taxas.
- Registro de várias cotações por item, com fornecedor, valor, data, validade e observações.
- Seleção de uma cotação como referência para contratação. Essa ação não representa aprovação financeira institucional.
- Campos para status da aprovação, responsável/aprovador, data, centro de custo, pedido/ordem de compra e referência de nota fiscal/documento.
- Resumo por categoria e comparativo histórico por ano/tipo de evento.
- Migração aditiva para banco SQLite já existente; não apaga despesas antigas.

## Onde acessar o módulo
- Abra **Solicitações e eventos**, entre no evento desejado e clique em **Orçamento e custos** ao lado do título.
- Para comparar custos entre eventos, use **Comparativo de custos** no menu lateral.

## Instalação recomendada
1. Pare o servidor local.
2. Faça backup da pasta do sistema e do arquivo `instance/fmabc_eventos.db`.
3. Extraia o PATCH em uma pasta temporária.
4. Copie os arquivos do PATCH para os mesmos caminhos do projeto, substituindo os arquivos indicados.
5. Não substitua o banco de dados nem o arquivo `.env`.
6. Inicie o sistema. A inicialização adiciona as colunas financeiras ausentes e cria a tabela de cotações.
7. Abra um evento de teste, entre em **Orçamento e custos**, cadastre uma despesa, inclua duas cotações e confira os totais.
8. Acesse **Comparativo histórico de custos** para conferir o agrupamento por ano e tipo.

## Observações importantes
- Os campos de aprovação são um registro de acompanhamento. Não disparam aprovação oficial nem substituem compras, financeiro, contratos ou alçadas da FMABC/FUABC.
- Valores em branco são tratados como zero apenas nos totais; os registros individuais continuam distinguindo ausência de valor de valor informado.
- Antes de usar em produção, valide o fluxo com o setor financeiro e confirme quais documentos/campos institucionais são obrigatórios.


## Correção de navegação
Esta versão inclui também `templates/event_detail.html` e `templates/base.html`, que não estavam no PATCH inicial. Esses arquivos exibem o acesso ao orçamento dentro do evento e o relatório comparativo no menu lateral.
