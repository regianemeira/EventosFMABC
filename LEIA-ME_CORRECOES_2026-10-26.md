# Correções de 26/10/2026 — Sistema de Eventos FMABC

## O que este pacote corrige

**Erros que derrubavam páginas**
- **Orçamento e custos** voltou a abrir (antes dava erro 500 em todos os eventos).
- **Modelos de checklist** voltou a abrir (antes dava erro 500).

**Funções das Fases 2 e 3 reconstruídas** (o `app.py` anterior tinha perdido essas partes)
- Orçamento com valor contratado, status de aprovação, aprovador, data, centro de custo, pedido/OC e nota fiscal.
- Cotações por despesa: registrar, excluir e selecionar a cotação de referência. Ao selecionar, o fornecedor e o valor contratado da despesa são atualizados.
- Resumo por categoria e gráfico de pizza do orçamento (o estilo do gráfico estava faltando).
- Campos personalizados nos modelos de checklist (texto, texto longo, lista, data, número, Sim/Não), que aparecem e são salvos dentro das tarefas.
- As despesas e cotações que você já tinha cadastrado continuam lá e passam a aparecer de novo.

**Erros de lógica**
- Horários como `7h`, `9h`, `7h às 17h` e `18h30 às 23h` passam a ser entendidos na checagem de conflito de espaço.
- O mesmo espaço escrito de formas diferentes é reconhecido: "Auditório David Uip - 280 lugares", "Anfiteatro Dr. David Uip", "Anf. David Uip" e "David Uip" contam como o mesmo local.
- Valores como `1.500` agora são lidos como mil e quinhentos (antes viravam R$ 1,50).
- A importação de planilha passou a ser "tudo ou nada": se der erro no meio, nada é gravado. Ao final, avisa se algum evento importado conflita com outro.
- Totais de orçamento (evento, relatórios, comparativo e CSV) ignoram despesas canceladas e o comparativo usa o valor contratado real. O CSV ganhou a coluna "Valor contratado".

**Novo: editar dados do evento**
- Botão **Editar dados do evento** na página do evento.
- Permite alterar nome, datas (inclusive **data de término para eventos de vários dias**), horários, local, tipo, categoria e dados do solicitante.
- Confere conflito de local em cada dia do período. Se houver conflito, mostra os eventos envolvidos e só salva com uma confirmação.
- Pode deslocar automaticamente os prazos das tarefas pendentes quando a data muda.
- Toda alteração fica registrada no **Histórico de alterações**, com data e autor.

**Segurança**
- Login bloqueado por 15 minutos após 5 senhas erradas para o mesmo e-mail (ou 20 tentativas do mesmo computador).
- A consulta pública de protocolo também tem limite de tentativas.
- O redirecionamento após o login não aceita mais endereços externos disfarçados.
- Prévias de importação (com nomes e telefones) são apagadas automaticamente após 24 horas.
- Erros inesperados mostram uma página amigável e ficam registrados em `instance/erros.log`.

## Como instalar

1. Pare o sistema (Ctrl+C no terminal).
2. **Faça uma cópia de segurança** da pasta do projeto inteira, principalmente `instance/fmabc_eventos.db`.
3. Copie os arquivos deste pacote para a pasta do projeto, mantendo as pastas e substituindo os existentes:
   - `app.py`
   - `templates/event_edit.html` (novo)
   - `templates/event_detail.html`
   - `templates/base.html`
   - `static/app.css`
   - `tests/test_sistema.py` (novo)
4. **Não** substitua o banco de dados nem o `.env`.
5. Inicie o sistema normalmente (`python app.py` ou `iniciar_windows.bat`). Na inicialização, o banco recebe apenas acréscimos: uma tabela de histórico de alterações e o vínculo das tarefas antigas aos modelos. Nenhum dado é apagado.
6. No navegador, aperte Ctrl+F5 para carregar o CSS novo.

## Como conferir

- Abra um evento → **Planejamento financeiro**: a página deve abrir com os quatro totais e o gráfico.
- Abra **Modelos de checklist**: cada modelo mostra a seção "Campos personalizados desta tarefa".
- Abra um evento → **Editar dados do evento**.
- Opcional, no terminal com o ambiente ativo: `python -m unittest tests.test_sistema -v` deve mostrar 4 testes OK. Esse teste usa um banco temporário e não mexe no seu.

## Ações que dependem de você

- **Troque a `SECRET_KEY` e a senha do administrador.** O `.env` com esses dados estava dentro do arquivo compartilhado. Para a chave, gere um texto aleatório longo; para a senha, use `python redefinir_senha_admin.py`.
- Na tela de edição de eventos importados da planilha, confira os horários sugeridos: o sistema converte "7h às 17h" para 07h–17h e mostra o texto original logo abaixo, para você comparar.

## Limites conhecidos

- O formulário público continua com uma única data. Eventos de vários dias são ajustados pela equipe na tela de edição.
- Serviços de apoio e itens solicitados não são editáveis na tela de edição, porque eles geram o checklist. Ajuste as tarefas diretamente no checklist.
- O limite de tentativas de login fica na memória e é zerado quando o sistema reinicia.
