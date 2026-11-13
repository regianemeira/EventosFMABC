# Atualizar o FMABC Eventos — Gestão avançada

1. Pare o servidor na janela de comando com `Ctrl+C`.
2. Faça cópias de segurança de `instance\fmabc_eventos.db` e `.env`. Não remova nem substitua a pasta `instance`.
3. Extraia o patch na pasta que contém `app.py`, mantendo as subpastas `templates` e `static`; permita substituir apenas os arquivos listados no ZIP.
4. Reinicie no Windows: `set PORT=5055` e depois `python app.py`.
5. No navegador, use `Ctrl+F5`.

## Novas áreas
- Agenda institucional: `/agenda`
- Roteiro operacional: botão “Roteiro do dia” no evento
- Orçamento e custos: botão “Orçamento e custos” no evento
- Ocorrências e lições aprendidas: botão “Ocorrências” no evento
- Relatórios anuais: `/relatorios`
- Confirmação de uma área de apoio: link individual gerado no comunicado marcado como “Ação necessária”.

Na primeira inicialização após atualizar, a aplicação cria as tabelas novas e acrescenta as colunas de confirmação ausentes, sem excluir registros de eventos/tarefas existentes. Ainda assim, mantenha a cópia de segurança até terminar os testes.

## Sequência de teste sugerida
1. Abra um evento de teste com local e horários. Veja se a agenda detecta possíveis sobreposições com outros eventos.
2. Abra “Roteiro do dia” e adicione duas atividades.
3. Abra “Orçamento e custos” e registre valor previsto e realizado de um item de teste.
4. Abra “Ocorrências” e registre um imprevisto fictício, depois marque-o resolvido.
5. Na agenda mensal, defina um departamento como “Ação necessária”, gere um rascunho do comunicado e confira se a confirmação fica pendente até a área responder.
6. Abra `/relatorios`, selecione o ano do evento e confira os totais antes de exportar.

**Limitações:** a confirmação externa por link exige que o sistema esteja acessível a partir do computador da área; para e-mail automático, SMTP e `APP_BASE_URL` precisam ser configurados com a TI. A detecção de conflitos é um alerta para revisão, não uma reserva oficial nem um bloqueio automático.
