# Atualização — horários de início e término no formulário

Esta atualização substitui o campo único de horário por dois seletores: **Horário de início** e **Horário de término**. As opções aparecem em intervalos de 30 minutos ao longo do dia, com rótulos como `10h`, `10h30`, `11h` e `11h30`. O término é obrigatório e deve ser posterior ao início.

## O que foi atualizado

- `app.py`
- `templates/request_form.html`
- `templates/event_detail.html`
- `templates/dashboard.html`
- `templates/agenda.html`
- `templates/checklist_print.html`
- `templates/event_run_sheet.html`
- `templates/communication.html`
- `templates/department_response.html`
- `README.md`

## Como instalar no Windows

1. Interrompa o servidor na janela preta com `Ctrl+C`.
2. Faça cópia de segurança de `instance\fmabc_eventos.db` e `.env`.
3. Extraia o ZIP de atualização diretamente na pasta do projeto (a pasta que contém `app.py`), mantendo a estrutura `templates\...` e aceitando substituir os arquivos listados.
4. Reinicie o sistema:

```bat
set PORT=5055
python app.py
```

5. Abra `http://127.0.0.1:5055/solicitar` e pressione `Ctrl+F5`.

## Validação de disponibilidade

- O formulário verifica o conflito ao selecionar data, início, término e local.
- O servidor valida novamente os horários antes de gravar a solicitação.
- Um intervalo como 10h–11h30 conflita com 11h–12h no mesmo espaço; um intervalo adjacente como 11h30–12h não é considerado sobreposição.
- Se o início ou término não for posterior ao início, o formulário impede o envio.
- Eventos cancelados não bloqueiam a reserva.
- Eventos antigos que não têm horário de término e podem se sobrepor são sinalizados de forma conservadora; isso evita aceitar uma reserva sem que a duração da reserva anterior seja conhecida.
- Locais externos não são comparados com a agenda interna de espaços FMABC.

## Testes realizados

- `app.py` passou por compilação sintática.
- Todos os 24 templates Jinja foram compilados.
- O formulário foi renderizado com os dois campos e as opções de 30 minutos.
- JavaScript inline passou por `node --check`.
- Testes isolados confirmaram sobreposição, intervalos adjacentes, duração ausente em registros antigos, evento cancelado e 48 opções de horário.

O servidor Flask completo não foi executado neste ambiente de criação; valide o fluxo no navegador depois de instalar o patch.
