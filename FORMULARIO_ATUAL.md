# Formulário para Eventos — mapeamento do PDF recebido

Fonte: arquivo “Formulário para Eventos - Google Formulários.pdf”, recebido em 20/10/2026. O formulário web em `templates/request_form.html` foi adaptado para reproduzir as 17 perguntas encontradas no documento.

| Nº | Pergunta original | Campo armazenado |
|---:|---|---|
| 1 | E-mail (obrigatório) | `organizer_email` |
| 2 | Qual o dia do evento? (obrigatório) | `start_date` |
| 3 | Nome do Evento (obrigatório) | `title` |
| 4 | Qual o horário do evento? (obrigatório; exemplo 08h30) | `start_time` |
| 5 | Setor organizador (obrigatório) | `department` |
| 6 | Indique o nome de uma pessoa responsável (obrigatório) | `organizer_name` |
| 7 | Qual o tipo do evento? Presencial / On-line / Híbrido (múltipla seleção) | `event_modes_json` e `event_format` |
| 8 | Quais serviços de apoio serão necessários? Manutenção / Limpeza / TI / Inspetoria / Outro (opção “Nenhum” removida por solicitação da coordenadora) | `support_json` e `support_other` |
| 9 | Qual local foi reservado para o evento? (locais e capacidades do PDF, mais Externo e Outro) | `venues_json`, `venue` e `venue_other` |
| 10 | Qual o público-alvo do evento? (obrigatório) | `audience` |
| 11 | Qual o número de pessoas esperado? (obrigatório) | `expected_attendees` |
| 12 | Qual o objetivo do evento? (obrigatório) | `description` |
| 13 | Assinale os itens que julga necessários (opções do PDF adaptadas; a opção “Nenhum” foi removida por solicitação da coordenadora) | `requested_items_json` e `items_other` |
| 14 | Contato da pessoa responsável (telefone/WhatsApp e e-mail) (obrigatório) — **mantida separada, conforme solicitado** | `organizer_phone` e `contact_email` |
| 15 | Autorizado por: Reitoria / Pró-Reitorias listadas no PDF (obrigatório, seleção única) | `authorized_by` |
| 16 | Centro de custo (obrigatório) | `cost_center` |
| 17 | Informações Adicionais | `additional_info` |

## Regras adicionadas

- As perguntas 7, 8, 9 e 13 exigem pelo menos uma seleção, como no formulário original.
- Se “Outro” for selecionado nas perguntas 8, 9 ou 13, a pessoa precisa detalhar a opção.
- O protocolo único continua sendo gerado após o envio e pode ser usado para acompanhar o status junto com o e-mail da pergunta 1.
- Ao mover a solicitação para “Aprovado” ou “Em planejamento”, o sistema cria tarefas gerais e tarefas condicionais baseadas nos serviços e itens marcados, por exemplo TI/audiovisual, limpeza, transmissão simultânea, coffee break, certificados e credenciais.
- Os campos estruturais de versões anteriores foram mantidos no banco para não quebrar o projeto existente. As perguntas do formulário público, porém, correspondem às 17 perguntas do PDF.

## Pontos a validar com o Setor de Eventos

- **Definição confirmada:** manter a pergunta 14, incluindo telefone/WhatsApp e e-mail de contato próprios. A pergunta 1 (“E-mail”) também permanece; os campos não serão unificados. A pergunta 1 continua sendo usada para acompanhar a solicitação junto com o protocolo.
- Decisão confirmada: a opção “Nenhum” foi removida das perguntas 8 (serviços de apoio) e 13 (itens necessários). Como ambas as perguntas são obrigatórias, o solicitante deverá selecionar ao menos uma opção disponível em cada grupo.
- Confirmar prazos e nomes finais das tarefas do checklist antes de colocar a aplicação em produção.


## Adaptações implementadas no sistema (20/10/2026)

- As 17 perguntas do formulário fornecido foram preservadas, inclusive a pergunta 14 com telefone/WhatsApp e e-mail separados da pergunta 1.
- A opção “Nenhum” foi removida dos serviços de apoio e dos itens necessários; os grupos continuam obrigatórios.
- Foi acrescentada a pergunta **Categoria do evento**, separada do formato presencial/on-line/híbrido. É uma pergunta operacional adicional para controlar quais tarefas são incluídas automaticamente no checklist. Se “Outro” for escolhido, é solicitado o detalhamento.
- A categoria e as seleções são usadas para gerar tarefas gerais e tarefas condicionais, de acordo com os modelos configuráveis.
