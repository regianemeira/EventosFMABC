# Atualização — Gestão de tarefas por departamento

Esta atualização amplia o acompanhamento das providências por área dentro do FMABC Eventos.

## Funcionalidades incluídas

- Confirmação explícita do recebimento da solicitação no link individual do evento e departamento.
- Campo para definir o responsável pela execução na área.
- Prazo da providência configurável pelo Setor de Eventos.
- Status da providência: Não iniciada, Em andamento, Aguardando terceiro, Bloqueada e Concluída.
- Resposta de atendimento separada do status da tarefa: recebido/em análise, confirmado, precisa alinhar, não poderá atender ou ciente.
- Justificativa obrigatória quando houver bloqueio, espera de terceiro, pedido de alinhamento ou impossibilidade de atendimento.
- Histórico de alterações com data/hora, autor, origem, campos alterados e valores anteriores/novos.
- Resumo da tarefa e acesso ao acompanhamento na página Agenda e comunicação.
- Alertas de agenda passam a incluir providências bloqueadas/aguardando terceiro e seus prazos.

## Atualização de banco

Ao iniciar, o sistema cria `department_task_history` e adiciona colunas à tabela `event_department_updates` quando ainda não existem. A migração é aditiva e não apaga eventos, usuários ou checklists. Providências antigas do tipo “Ação necessária” sem link recebem um token individual para permitir resposta da área.

## Instalação no Windows

1. Pare a aplicação com `Ctrl+C`.
2. Faça cópia de segurança de `instance/fmabc_eventos.db` e `.env`.
3. Extraia o patch na pasta onde está `app.py`, preservando as subpastas `templates` e `static` e permitindo substituir os arquivos do patch.
4. Reinicie:

```bat
set PORT=5055
python app.py
```

5. Atualize o navegador com `Ctrl+F5`.

O patch não contém o banco de dados nem o `.env`.

## Uso

1. Em **Agenda e comunicação**, selecione a área e o período.
2. Abra **Configurar participação e prazo** no evento.
3. Marque **Ação necessária**, descreva a providência, defina responsável e prazo, e salve.
4. Gere o comunicado para a área. O rascunho inclui o link individual de acompanhamento se `APP_BASE_URL` estiver configurado.
5. A pessoa da área abre o link, confirma o recebimento, informa quem responde, seleciona a resposta da área e o status da providência. Pendências precisam de justificativa.
6. O Setor de Eventos acompanha o status e o histórico na agenda mensal; pendências relevantes também aparecem em **Agenda institucional**.

## E-mail e acesso externo

Para que uma área abra o link em outro computador, é necessário publicar a aplicação em endereço acessível à rede da FMABC ou à internet conforme a política institucional, e configurar `APP_BASE_URL` com esse endereço. O endereço local `127.0.0.1` funciona apenas na própria máquina. O envio automático de e-mails também depende de configuração SMTP aprovada pela TI.

## Observações de segurança

O link de acompanhamento é um token individual para um par evento/área. Não compartilhe links publicamente. O histórico administrativo não é exibido no formulário público, para não expor observações internas.

## Validação efetuada

- Compilação de sintaxe do Python.
- Execução do esquema SQLite em banco novo.
- Simulação de migração a partir do esquema anterior, confirmando que as novas colunas/tabelas são adicionadas.
- Análise sintática de todos os templates Jinja.

O servidor Flask completo deve ser testado na instalação local após o patch, pois Flask não estava instalado no ambiente usado para preparar esta atualização.
