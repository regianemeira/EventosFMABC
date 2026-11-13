# Central de Conhecimento — Manual de Eventos FMABC

## Documento-fonte
- **Título:** Manual de Cerimonial e Eventos do Centro Universitário FMABC
- **Edição indicada no documento:** 2023
- **Extensão:** 67 páginas no PDF fornecido
- **Arquivo integral distribuído:** `static/docs/manual_cerimonial_eventos_fmabc_2023.pdf`
- **Índice textual de consulta:** `data/manual_eventos_index.json`

## Experiência implementada
- Página pública em `/manual`, com uma caixa de pergunta e consultas sugeridas.
- Resultados com trechos textuais recuperados do documento, nome de seção aproximado e página do PDF.
- Link direto para abrir o PDF na página citada.
- Leitor incorporado do PDF integral e link para abrir/baixar o arquivo original.
- Consulta local sem internet e sem chamada a um serviço externo. As perguntas não são gravadas em banco de dados.
- Quando não há correspondência suficiente, a página informa que não encontrou orientação suficiente, em vez de criar uma regra.

## Limitação funcional explícita
Esta é a primeira versão do chat: um mecanismo de recuperação textual (busca lexical com normalização de palavras e equivalências limitadas), que devolve trechos do manual. Ele **não gera uma resposta conversacional por IA nem faz inferências fora do texto**. Para uma próxima etapa, é possível adicionar síntese com um modelo de linguagem, desde que cada afirmação seja sustentada por trechos recuperados do PDF e as lacunas sejam reconhecidas explicitamente. Isso exigiria escolher e configurar um provedor de IA e aprovar o envio de trechos do manual a esse provedor.

## Reindexação quando houver nova edição
1. Coloque a nova edição do PDF em `static/docs/`.
2. Em ambiente de desenvolvimento com PyMuPDF instalado, execute:
   `python scripts/indexar_manual.py --input static/docs/manual_cerimonial_eventos_fmabc_2023.pdf --output data/manual_eventos_index.json`
3. Confirme a quantidade de páginas indexadas e rode os testes em `tests/test_manual_search.py`.
4. Teste perguntas de assuntos conhecidos, verificando se o resultado aponta para a página correta.
5. Publique o PDF e o JSON de índice juntos, no mesmo pacote de aplicação.

## Escopo documental
O índice abrange as páginas extraídas do PDF recebido, incluindo introdução, classificação, participação, nomenclatura, tipologia, planejamento/organização/execução, atribuições, programação visual, divulgação, convites, estrutura, cerimonial/protocolo, precedência e anexos. O PDF original é sempre a referência para conferir tabelas, imagens, diagramas e contexto de trechos recuperados.
