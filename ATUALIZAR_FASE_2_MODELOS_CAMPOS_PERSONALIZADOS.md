# Atualização — Fase 2: modelos e campos personalizados

## O que foi incluído
- Cadastro de campos personalizados por modelo de tarefa.
- Tipos de campo: texto curto, texto longo, lista de opções, data, número e Sim/Não.
- Opção de tornar cada campo obrigatório.
- Preenchimento e salvamento dos valores dentro da tarefa do evento.
- Associação de tarefas automáticas e tarefas adicionadas pela biblioteca ao respectivo modelo.
- Migração aditiva do SQLite: cria tabelas auxiliares e adiciona `template_id` sem apagar registros existentes.
- Tentativa de associação das tarefas antigas aos modelos por título e categoria correspondentes.

## Instalação recomendada
1. Pare o servidor local do FMABC Eventos.
2. Faça cópia de segurança de `instance/fmabc_eventos.db` e de toda a pasta do projeto.
3. Extraia o pacote de atualização em uma pasta temporária.
4. Para o pacote patch, copie os arquivos mantendo os mesmos caminhos: `app.py`, `templates/checklist_templates.html`, `templates/event_detail.html` e `static/app.css`.
5. Não substitua o banco de dados nem o arquivo `.env`.
6. Inicie o sistema como de costume. A migração cria as novas tabelas na inicialização.
7. Entre com uma conta administradora e abra **Modelos de checklist**. Edite um modelo, adicione um campo e abra um evento que tenha uma tarefa vinculada àquele modelo.

## Observações importantes
- Campos novos passam a aparecer nas tarefas vinculadas ao modelo. Tarefas antigas são associadas automaticamente quando o título e a categoria coincidem; tarefas renomeadas ou muito modificadas podem exigir conferência manual.
- Excluir um campo remove também os valores preenchidos para aquele campo. Os demais dados da tarefa permanecem.
- A edição dos modelos não altera automaticamente títulos, prazos ou tarefas dos eventos já existentes.
- Esta entrega foi validada quanto à sintaxe Python. O teste de integração com Flask não pôde ser executado neste ambiente de preparação porque a dependência Flask não está instalada; valide primeiro em uma cópia local antes de usar em produção.
