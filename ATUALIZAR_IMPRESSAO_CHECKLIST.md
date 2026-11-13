# Atualização: botão de impressão do checklist

A atualização acrescenta um botão **Imprimir checklist** à área de checklist de cada evento e uma versão específica de impressão, sem os menus e controles de edição.

## Conteúdo da folha
- Nome do evento e protocolo.
- Data, horário, formato, local e setor organizador.
- Progresso geral do checklist.
- Itens com caixa para marcar no papel, categoria/etapa, status, prazo e responsável.

## Como aplicar no Windows
1. Na janela do Prompt de Comando em que o sistema está aberto, pressione `Ctrl+C`.
2. Faça cópia de segurança de `instance\fmabc_eventos.db` e do `.env`.
3. Extraia este ZIP diretamente dentro da pasta do projeto, onde está o `app.py`, mantendo as pastas `templates` e `static` e aceitando substituir os arquivos solicitados.
4. Inicie novamente:

   ```bat
   set PORT=5055
   python app.py
   ```

5. Entre no sistema, abra um evento com checklist e clique em **Imprimir checklist**.
6. Na janela de impressão, selecione papel **A4**, orientação **Paisagem** e opção **Frente e verso**, caso disponível. Confira a prévia antes de imprimir.

O pacote de atualização contém `app.py`, `templates\event_detail.html`, o novo `templates\checklist_print.html`, `static\app.css` e esta documentação. Ele não inclui, substitui ou apaga o banco de dados ou o `.env`.

## Observação
O layout foi testado em PDF A4 paisagem com checklists de 16, 25 e 60 tarefas. Até 24 tarefas são organizadas para caber em uma face; acima disso, a lista é distribuída em duas páginas, para impressão duplex em uma folha. Para listas extensas, a tipografia é reduzida para preservar o limite de duas páginas. Confira sempre a prévia de impressão da sua impressora.
