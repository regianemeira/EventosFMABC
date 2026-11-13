# Atualização visual dos campos de horário

Esta atualização compacta os seletores de início e término no formulário público de solicitação.

## O que mudou

- Os dois horários agora aparecem agrupados em um bloco visual único, com fundo verde-claro discreto e borda suave.
- O usuário escolhe início e término em controles lado a lado no desktop.
- Os seletores ficaram mais baixos, com menos preenchimento interno e rótulos menores.
- Em telas estreitas, o bloco se adapta ao espaço disponível.
- Os nomes de campo (`start_time` e `end_time`), as 48 opções de 30 minutos e a validação de conflito foram preservados.

## Como instalar no Windows

1. Pare o servidor pela janela do Prompt de Comando usando `Ctrl+C`.
2. Faça uma cópia de segurança do arquivo `.env` e de `instance\fmabc_eventos.db`.
3. Extraia o patch diretamente na pasta do projeto que contém `app.py`, preservando as pastas `templates` e `static` e aceitando substituir os dois arquivos.
4. Inicie o sistema novamente:

```bat
set PORT=5055
python app.py
```

5. Abra `http://127.0.0.1:5055/solicitar` e pressione `Ctrl+F5`.

O patch não contém nem modifica o banco de dados.
