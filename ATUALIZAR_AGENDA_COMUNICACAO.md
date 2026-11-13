# Atualização — Agenda mensal e envio de comunicados na mesma página

Esta atualização reorganiza a tela `/comunicacao` para que a preparação mensal e o envio dos comunicados aconteçam em um único lugar.

## O que mudou

- O mês e o ano são escolhidos separadamente dos destinatários.
- É possível marcar vários departamentos para receber a programação.
- O sistema cria um rascunho individual e personalizado para cada área selecionada.
- Os rascunhos do mês são exibidos na própria tela da agenda, com e-mail, assunto e mensagem editáveis.
- A mesma área permite salvar alterações, enviar por SMTP quando configurado ou registrar que a mensagem foi enviada pelo Outlook.
- A configuração da participação de cada departamento nos eventos continua disponível na mesma página, em uma área recolhível.
- Histórico recente, administração dos departamentos e importação da planilha ficam em seções recolhíveis para reduzir a poluição visual.
- Os e-mails dos departamentos não são inventados. Se um destinatário estiver em branco, ele pode ser informado na prévia antes do envio.

## Aplicar a atualização no Windows

1. Encerre o servidor com `Ctrl+C` na janela onde `python app.py` está rodando.
2. Faça uma cópia de segurança do arquivo `instance/fmabc_eventos.db`.
3. Extraia o ZIP de patch dentro da pasta do projeto `fmabc_eventos`, preservando as pastas e permitindo substituir os arquivos existentes.
4. O patch substitui `app.py`, `templates/communication.html` e `static/app.css`, e adiciona este guia. Ele não inclui nem substitui o banco de dados, o arquivo `.env` ou o PDF do manual.
5. Reinicie o sistema:

   ```bat
   set PORT=5055
   python app.py
   ```

6. Acesse `http://127.0.0.1:5055/comunicacao` e pressione `Ctrl+F5` para recarregar os estilos.

## Como usar

1. Selecione mês e ano e a área usada para configurar as providências por evento.
2. Marque os departamentos que devem receber o comunicado. Os que ainda não têm e-mail cadastrado continuam selecionáveis, mas será necessário preencher o destinatário na prévia.
3. Clique em **Gerar prévias selecionadas**.
4. Na mesma página, expanda cada mensagem, revise destinatário, assunto e conteúdo.
5. Salve as alterações, use **Salvar e enviar pelo sistema** se o SMTP institucional estiver configurado, ou confirme o envio pelo Outlook para registrar o envio manual.

Cada área selecionada recebe um rascunho separado, com os eventos em que sua participação não está marcada como “Não incluir no comunicado”. Revise os textos antes de enviar. O envio automático só deve ser habilitado depois de configuração e teste com a TI institucional.
