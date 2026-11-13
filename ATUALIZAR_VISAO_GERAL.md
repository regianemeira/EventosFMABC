# Atualização — Visão geral com contagem regressiva

Esta atualização muda apenas a apresentação da página inicial e seus estilos. Não altera banco de dados, usuários, senhas, eventos, checklists ou configurações de e-mail.

## O que muda

- Destaque visual do evento futuro mais próximo.
- Contagem regressiva em dias; mostra `É hoje` e `Amanhã` para as datas imediatas.
- Destaque por cor: vermelho (até 3 dias), âmbar (4 a 7 dias), verde (8 a 30 dias) e azul (mais de 30 dias).
- Lista de próximos eventos com data, horário, local, status e contador.
- Layout responsivo para telas menores.

## Como aplicar na instalação existente do Windows

1. Na janela do Prompt de Comando em que o servidor está rodando, pressione `Ctrl+C`.
2. Faça uma cópia de segurança da pasta do projeto. O banco de dados local costuma ficar em `instance/fmabc_eventos.db`; não o substitua nem apague.
3. Extraia o arquivo ZIP de atualização **na raiz da pasta** `fmabc_eventos`, mantendo a estrutura de pastas. Autorize a substituição de `templates/dashboard.html` e `static/app.css`.
4. Inicie novamente o servidor com os comandos usados na sua máquina:

   ```bat
   set PORT=5055
   python app.py
   ```

5. Abra `http://127.0.0.1:5055/` ou `http://127.0.0.1:5055/login` e faça login.
6. Se a página ainda mostrar o estilo antigo, pressione `Ctrl+F5` para recarregar os arquivos CSS do navegador.

## Observação

A contagem regressiva usa a data local do computador que está abrindo o painel. Eventos cancelados ou realizados não aparecem na lista de próximos eventos, conforme as regras atuais do sistema.
