# Agenda institucional e comunicados por área — FMABC Eventos

## O que o módulo faz

- Mantém uma agenda mensal dentro do FMABC Eventos.
- Permite registrar, por evento e por área, se há **Ação necessária**, se é **Para conhecimento** ou se o evento deve ser **Não incluído no comunicado** daquela área.
- Separa providências que vão para o e-mail de observações internas do Setor de Eventos.
- Gera um comunicado por departamento e mês; assunto, destinatário e corpo podem ser revisados antes de enviar.
- Registra rascunhos, envios SMTP e envios feitos pelo e-mail institucional fora do sistema.
- Importa uma planilha histórica `.xlsx` por prévia; a importação é idempotente para eventos já cadastrados com a mesma data e título.

## Importar a agenda existente

1. Inicie o aplicativo e entre com uma conta administradora.
2. Abra **Agenda e comunicação**.
3. Em **Importar agenda existente**, selecione o arquivo Excel `Eventos FMABC 2026 (2).xlsx`.
4. Clique em **Analisar planilha** e confira o resultado antes de confirmar.
5. A importação inclui somente eventos com data igual ou posterior à data em que o arquivo é importado. Eventos anteriores são ignorados.
6. Os registros entram como **Em planejamento** e recebem um checklist inicial. As notas de TI, Inspetoria, Limpeza, Manutenção e Imprensa são associadas às respectivas áreas.

O importador não inventa e-mails ou telefones ausentes. Observações que não sejam vinculadas a uma área — como as notas da Profª Bianca ou links — são preservadas nas informações adicionais do evento. A sigla **PSC** é mantida como texto de observação e não é interpretada pelo sistema.

O importador considera a planilha apenas uma fonte inicial. Depois da importação, corrija contatos e outros campos incompletos no processo administrativo. A planilha não será sincronizada automaticamente com o sistema.

## Preparar e revisar o comunicado do mês

1. Na página **Agenda e comunicação**, escolha o mês, ano e departamento.
2. O sistema lista eventos com status **Aprovado** ou **Em planejamento** no período. Eventos em triagem, cancelados ou realizados não entram automaticamente.
3. Para cada evento, selecione a participação da área:
   - **Ação necessária** — indicar claramente o que a área deve providenciar.
   - **Para conhecimento** — comunicar o evento sem atribuir uma tarefa específica.
   - **Não incluir no comunicado** — excluir esse evento da mensagem dessa área.
4. Preencha **Providências / informações para o comunicado** para texto que aparecerá na mensagem.
5. Use **Observação interna** para comentários que não devem ser enviados por e-mail.
6. Clique em **Criar prévia mensal**. O rascunho reúne os eventos não excluídos naquele período e é salvo no histórico.
7. Confira o destinatário, assunto e corpo da mensagem. É possível editar e salvar a prévia antes de enviar.
8. Envie por SMTP se estiver configurado, ou encaminhe pelo Outlook/e-mail institucional e depois clique em **Registrar como enviado**, confirmando a ação.

O padrão para evento sem classificação salva para uma área é **Para conhecimento**. Isso permite que a área veja a agenda completa até que uma ação específica ou exclusão seja indicada.

## Configurar destinatários

Uma pessoa administradora deve abrir a seção **Áreas e destinatários** na parte inferior da página. Cadastre os endereços confirmados para TI, Inspetoria, Limpeza, Manutenção, Imprensa e outras áreas necessárias. Nenhum endereço foi preenchido por suposição.

## Envio automático por SMTP

A TI da FMABC deve fornecer o servidor autorizado, porta, remetente e método de autenticação. Insira esses valores no arquivo `.env`:

```dotenv
SMTP_HOST=
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
SMTP_FROM=
SMTP_USE_TLS=1
```

O fluxo atual usa SMTP com `STARTTLS` quando `SMTP_USE_TLS=1`; a configuração precisa corresponder às regras do serviço de e-mail institucional. Faça um envio de teste para uma caixa interna autorizada. Se o SMTP não estiver configurado, a aplicação não declara o envio concluído: o rascunho permanece salvo para envio manual.

## Limites conhecidos

- A importação da planilha ocorre mediante ação de um administrador e não sincroniza alterações posteriores.
- Os e-mails das áreas precisam ser confirmados e cadastrados.
- O sistema gera comunicados quando solicitado; não envia um boletim recorrente sozinho.
- Se um evento for alterado depois do envio, a revisão e a comunicação da alteração continuam sob responsabilidade da equipe. Gere uma nova prévia corrigida para informar a área.
- O projeto ainda precisa ser executado localmente e testado no navegador com as dependências instaladas antes de uso institucional real.

## Atualização de interface: envio em uma única tela

A versão mais recente permite selecionar vários departamentos na própria página da agenda mensal e gerar um rascunho personalizado por área. As prévias ficam abaixo da agenda, sem redirecionar para outra página. Em cada rascunho, os campos Para, Assunto e Mensagem podem ser editados; as ações permitem salvar, enviar por SMTP configurado ou registrar envio realizado manualmente pelo Outlook. Consulte `ATUALIZAR_AGENDA_COMUNICACAO.md` para os passos de atualização local.
