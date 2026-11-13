# Atualização — Checklist inteligente e personalizável

## O que muda

- O checklist inicial continua sendo gerado automaticamente a partir do tipo de evento, modalidade, serviços e itens informados no formulário.
- Na tela do evento, a seção **Selecionar atividades da biblioteca** permite acrescentar manualmente outras atividades reutilizáveis sem alterar o modelo geral.
- Atividades já presentes no checklist aparecem desabilitadas para evitar duplicidade.
- A opção **Criar atividade personalizada** permite registrar tarefas exclusivas daquele evento, com categoria, prazo, responsável, detalhamento e observações.
- Os campos detalhados permanecem recolhidos até a pessoa abrir uma tarefa.
- A biblioteca geral continua administrável em **Modelos de checklist**; mudanças nessa biblioteca valem para novas gerações, enquanto a seleção manual acrescenta tarefas apenas ao evento atual.

## Instalação

1. Pare o servidor com `Ctrl+C`.
2. Faça cópia de `instance/fmabc_eventos.db` e `.env`.
3. Extraia o ZIP de atualização na pasta do projeto, mantendo os caminhos `app.py`, `templates/event_detail.html` e `static/app.css`.
4. Reinicie com `set PORT=5055` e `python app.py`.
5. Atualize o navegador com `Ctrl+F5`.

Não substitua nem apague a pasta `instance`. Não é necessária migração de banco de dados para esta atualização.

## Teste recomendado

1. Abra um evento que já tenha checklist.
2. Expanda **Selecionar atividades da biblioteca**.
3. Escolha uma atividade que ainda não esteja no checklist e clique em **Adicionar selecionadas**.
4. Confirme que a atividade aparece no checklist com o prazo sugerido relativo à data do evento.
5. Tente adicionar novamente a mesma atividade: ela deve aparecer como já adicionada e não criar duplicata.
6. Expanda **Criar atividade personalizada** e adicione uma tarefa exclusiva.
7. Confira que o checklist original e os demais eventos não foram alterados.
