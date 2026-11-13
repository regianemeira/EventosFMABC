# Atualização — Checklist consolidado | FMABC Eventos

## Inclui
- Nova opção Checklist consolidado no menu lateral.
- Visão das tarefas de todos os eventos, com filtros por evento, status, responsável, texto e prazo.
- Indicadores de tarefas exibidas, em aberto, atrasadas e concluídas.
- Links para abrir o evento e a tarefa correspondente.
- Layout responsivo em identidade azul/verde.

## Instalação
1. Pare o servidor local.
2. Faça backup da pasta do projeto e do banco `instance/fmabc_eventos.db`.
3. Extraia este ZIP em uma pasta temporária.
4. Copie `app.py` para a raiz do projeto, `base.html` e `checklist_consolidado.html` para `templates/`, e `app.css` para `static/`, substituindo os arquivos correspondentes.
5. Preserve o banco de dados e o arquivo `.env`.
6. Reinicie o sistema e acesse Checklist consolidado no menu lateral.

A tela usa tarefas já cadastradas e não apaga registros. Teste primeiro em cópia local. A base incluída é a versão do projeto que estava disponível nesta conversa; se houver mudanças posteriores no seu `app.py`, compare/mescle antes de substituir.
