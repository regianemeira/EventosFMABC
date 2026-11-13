# Atualização — verificação de disponibilidade de espaços

Esta atualização faz o formulário público consultar a agenda quando o solicitante informa data, horário e local e, além disso, repetir a verificação no servidor imediatamente antes de gravar o evento.

## Arquivos alterados

- `app.py`
- `templates/request_form.html`
- `static/app.css`

A atualização não contém banco de dados e não modifica `.env`.

## Como aplicar no Windows

1. Pare o servidor com `Ctrl+C`.
2. Faça cópia de segurança de `instance/fmabc_eventos.db` e `.env`.
3. Extraia o ZIP de atualização diretamente na pasta do projeto (a pasta que contém `app.py`) e aceite substituir os três arquivos listados acima.
4. Inicie novamente:

```bat
set PORT=5055
python app.py
```

5. Abra `http://127.0.0.1:5055/solicitar` e pressione `Ctrl+F5`.

## Comportamento

- Ao selecionar data, horário e local, o formulário consulta o servidor e mostra um aviso de disponibilidade.
- Se houver choque de data/local/horário, o botão de envio é desabilitado enquanto a combinação conflituosa estiver selecionada.
- O envio também é bloqueado no servidor, mesmo se a checagem dinâmica do navegador não acontecer. A verificação e a inserção são protegidas por um lock de escrita SQLite para reduzir a possibilidade de duas solicitações simultâneas ocuparem a mesma combinação.
- Eventos com status `cancelado` não bloqueiam novas solicitações.
- Locais externos à FMABC não são verificados contra a agenda interna.
- Nomes de salas são normalizados para comparar diferenças de maiúsculas/minúsculas, acentos, tipos de travessão e sufixos de capacidade (por exemplo, `- 280 lugares`).
- Horários podem ser informados como `08h30` ou `08:30`. Para comparar intervalos, pode-se informar `08h30 às 10h00` ou `08:30-10:00` no campo de horário.
- Se uma reserva existente tiver horário não padronizado, a solicitação é bloqueada conservadoramente para confirmar disponibilidade com o Setor de Eventos.
- Se somente o horário inicial estiver disponível para ambos os eventos, a verificação bloqueia início idêntico. Não é possível inferir uma sobreposição com início diferente sem conhecer a duração; para esses casos, informe também o término no campo de horário.

## Testes realizados neste ambiente

- Sintaxe de `app.py` compilada com `py_compile`.
- Template Jinja analisado.
- JavaScript do formulário validado com `node --check`.
- Testes isolados da lógica de conflito: mesmo local/data/início, horários formatados de forma diferente, intervalos sobrepostos, intervalos adjacentes, local externo, evento cancelado, horário preexistente não padronizado e eventos de vários dias.

O servidor Flask completo não pôde ser iniciado neste ambiente de criação; a validação final deve ser feita no computador local depois da atualização.
