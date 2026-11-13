# Gestão avançada do FMABC Eventos

Este módulo adiciona recursos operacionais à aplicação existente. Ele complementa as solicitações, checklists, agenda mensal, comunicados, manual e relatórios pós-evento.

## Agenda institucional e prevenção de conflitos
- Acesse `/agenda` para navegar por mês/ano.
- A agenda apresenta os eventos em cada dia, possíveis conflitos de local/horário, tarefas com prazo vencido ou próximo e confirmações pendentes das áreas.
- Os conflitos são alertas preventivos: precisam de validação humana, principalmente quando horários finais ou duração não foram informados. O sistema não realiza reserva externa de espaço nem bloqueia uma solicitação automaticamente.

## Confirmação das áreas de apoio
- Na agenda e comunicação, defina uma área como “Ação necessária” ou “Para conhecimento” e registre as providências.
- Ao gerar o comunicado de uma área marcada com ação necessária, o sistema cria um link individual para resposta.
- A área pode indicar “Confirmado”, “Ciente”, “Precisa alinhar” ou “Não poderá atender”, com nome e observações.
- A tela da agenda lista retornos pendentes. Para links acessíveis fora do computador local, configure `APP_BASE_URL` com o endereço real publicado e acessível aos destinatários. Enquanto o sistema operar em `127.0.0.1`, outros funcionários não poderão abrir o link.
- Antes de uso real, cadastre/valide os e-mails oficiais dos departamentos e teste SMTP com a TI.

## Tarefas críticas e alertas
- O painel e a agenda destacam tarefas em aberto com prazo vencido ou nos próximos três dias.
- Tarefas concluídas ou marcadas “Não se aplica” não geram alertas.
- O indicador é preventivo e não substitui revisão do checklist pelo Setor de Eventos.

## Roteiro do dia
- No detalhe do evento, selecione “Roteiro do dia”.
- Cadastre atividades com horário de início/término, local, responsável e observações. O roteiro pode ser impresso para orientar a equipe.

## Orçamento e custos
- No detalhe do evento, abra “Orçamento e custos”.
- Registre itens, categoria, fornecedor, valor previsto, custo realizado, situação e observações.
- Os totais por evento são agregados no relatório anual. Valores em branco significam não registrados; não devem ser interpretados como custo zero confirmado.

## Ocorrências e lições aprendidas
- No detalhe do evento, abra “Ocorrências”.
- Registre problema, data/hora, categoria, impacto, solução, ação preventiva, responsável e situação.
- Os relatórios anuais exibem a quantidade de ocorrências e quantas continuam abertas/em tratamento. Use os campos de ação preventiva para registrar aprendizados para eventos futuros.

## Relatórios anuais
- `/relatorios` permite filtrar por ano, status, categoria e setor.
- A tabela e o CSV incluem público previsto/real, encerramento, avaliações, totais previstos/realizados e ocorrências.
- Apenas os números efetivamente cadastrados são consolidados; campos não preenchidos continuam como informação ausente.

## Segurança e implantação
- Faça backup de `instance/fmabc_eventos.db` e `.env` antes de atualizar.
- A aplicação local usa SQLite; antes de compartilhá-la com toda a FMABC, confirme política de hospedagem, backup, controle de acesso, privacidade e retenção de dados com a TI.
- `APP_BASE_URL` precisa ser o endereço HTTPS institucional/de produção para links públicos enviados por e-mail; não use endereço `localhost`/`127.0.0.1`.
