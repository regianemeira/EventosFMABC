# Atualização do layout do formulário de solicitação

## O que mudou

- A primeira seção agora começa com **Nome do evento**, seguida de **Data do evento** e **Horário de início e término**.
- Na linha seguinte aparecem **Nome da pessoa responsável**, **E-mail do solicitante** e **Setor organizador**.
- O e-mail principal permanece separado do telefone/WhatsApp e e-mail de contato solicitados na pergunta 14, que continuam na seção de contato.
- Os campos estão em uma grade mais compacta para desktop, com melhor aproveitamento horizontal, espaçamento menor e controles de altura reduzida.
- Em telas médias e pequenas, o formulário reorganiza os campos para evitar texto cortado.
- IDs e names dos campos existentes foram preservados, assim como a verificação de disponibilidade e conflito de reservas.

## Como instalar no Windows

1. Pare o servidor usando `Ctrl+C` na janela do Prompt de Comando.
2. Faça uma cópia de segurança de `instance\fmabc_eventos.db` e do arquivo `.env`.
3. Extraia o ZIP de atualização diretamente na pasta do projeto que contém `app.py`, mantendo as pastas `templates` e `static` e aceitando substituir os dois arquivos incluídos.
4. Reinicie o sistema:

```bat
set PORT=5055
python app.py
```

5. Abra `http://127.0.0.1:5055/solicitar` e pressione `Ctrl+F5` para limpar o cache dos estilos.

O patch substitui apenas `templates/request_form.html` e `static/app.css`. Ele não contém nem altera o banco de dados.
