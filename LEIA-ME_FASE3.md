# Fase 3 — Comunicar (26/10/2026)

Pacote **cumulativo**: inclui as correções e a Fase 2. Se ainda não instalou os pacotes anteriores, instale só este.

## O que há de novo

**1. Avisos automáticos ao solicitante**
- **Confirmação de recebimento** por e-mail logo após o envio do formulário, com o protocolo.
- Ao mudar o status, tanto na *Triagem* quanto na página do evento, aparecem dois campos novos:
  - **Mensagem ao solicitante**: um texto livre que vai no e-mail. Exemplos: o motivo de um cancelamento ou um recado na aprovação.
  - **Avisar o solicitante por e-mail**: vem marcado. Desmarque quando não quiser avisar.
- Recebem aviso as mudanças para: *Em triagem*, *Aprovado*, *Em planejamento*, *Cancelado* e *Aguardando informações*. Passar de *Aprovado* para *Em planejamento* sem mensagem não gera e-mail, para não incomodar o solicitante.
- Cada aviso fica registrado na linha do tempo do evento.

**2. Pedido de informações pelo sistema**
- Ao mudar para **Aguardando informações**, a mensagem ao solicitante é obrigatória: é ali que você escreve o que está faltando.
- O solicitante recebe um link para **responder e anexar arquivos** (até 5 arquivos, 15 MB no total). O mesmo pedido aparece na página pública **Acompanhar solicitação**, quando ele consulta o protocolo.
- Quando o solicitante responde:
  - o status volta sozinho para *Em triagem*;
  - a resposta e os arquivos entram no evento (linha do tempo e anexos);
  - o responsável interno, ou os administradores se não houver responsável, recebe um e-mail.

**3. Lembretes automáticos** (uma vez por dia, a partir das 7h, enquanto o sistema estiver ligado)
- **Equipe:** um resumo com as tarefas atrasadas ou vencendo em até 3 dias, enviado ao responsável interno do evento (ou aos administradores, se não houver responsável). Se a tarefa tiver um e-mail no campo "Responsável", essa pessoa também recebe.
- **Áreas de apoio:** providências não concluídas de eventos nos próximos 7 dias, com o link de atualização. No máximo um lembrete a cada 3 dias por providência.
- **Solicitantes:** quem não respondeu a um pedido de informações em 3 dias recebe lembrete, até 3 vezes.
- Os lembretes nunca se repetem no mesmo dia.
- Também é possível gerar os lembretes manualmente em **E-mails e lembretes → Gerar lembretes agora**.
- Opcional: para gerar lembretes mesmo quando o sistema não fica ligado de manhã, agende `python enviar_lembretes.py` no Agendador de Tarefas do Windows.

**4. Tela "E-mails e lembretes"** (menu lateral)
- Uma **caixa de saída** com todos os e-mails automáticos e a situação de cada um: aguardando, enviado, enviado manualmente, falhou ou cancelado. Clique em um e-mail para ver o texto completo.
- **Sem SMTP configurado** (situação atual), os e-mails ficam aguardando. Use **Abrir no e-mail** para enviar pelo seu Outlook e depois **Marcar como enviado**.
- **Com SMTP configurado**, os e-mails saem sozinhos em segundo plano, com até 3 tentativas, e **Tentar enviar de novo** reenvia os que falharam.

**5. Calendário (.ics)**
- Em **E-mails e lembretes** há um **link pessoal** para assinar a agenda de eventos no Outlook, no Google Agenda ou no celular. A agenda se atualiza sozinha; eventos ainda em análise aparecem como "provisórios".
- Na página de cada evento, o botão **Adicionar ao calendário** baixa o evento.

**6. Tarefas salvas sem recarregar a página**
Ao salvar uma tarefa do checklist, o resumo da tarefa e a barra de progresso se atualizam na hora, sem voltar ao topo da página.

## Como instalar

1. Pare o sistema e **faça uma cópia de segurança da pasta inteira** (incluindo `instance/`).
2. Extraia este pacote na pasta do projeto, substituindo os arquivos. **Não** substitua o banco nem o `.env`.
3. Inicie normalmente. O banco recebe só acréscimos: caixa de saída, pedidos de informação, registro de lembretes e configurações.
4. Ctrl+F5 no navegador.
5. Teste rápido: `python -m unittest tests.test_sistema -v` deve mostrar 8 testes OK. O teste nunca envia e-mails de verdade.

## Para os e-mails funcionarem por completo (com a TI)

| Configuração no `.env` | Para que serve | Sem ela |
| --- | --- | --- |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM` | Envio automático dos e-mails | Os e-mails ficam na caixa de saída para envio manual |
| `APP_BASE_URL` (ex.: `https://eventos.fmabc.br`) | Links nos e-mails: responder, acompanhar, atualizar providência, abrir evento | Os e-mails vão sem links; o solicitante responde pela consulta de protocolo |
| `LEMBRETES_AUTOMATICOS=0` | Desligar os lembretes automáticos | Lembretes ligados (padrão) |

Enquanto o sistema roda só no seu computador, ninguém de fora consegue abrir os links. O `APP_BASE_URL` só faz sentido depois que o sistema estiver publicado na rede da FMABC.

## Atenção com os seus dados

8 dos seus 12 eventos vieram da planilha e **não têm e-mail do solicitante**. Para esses eventos, os avisos não são enviados (o sistema avisa a equipe na hora). Preencha o e-mail em **Editar dados do evento** quando souber.
