# Novo checklist do evento (26/10/2026)

Pacote **cumulativo**: inclui as correções e as Fases 2 e 3. Se ainda não instalou os anteriores, instale só este.

## O que mudou

**Abas no evento.** Cada evento agora tem as abas Resumo · **Checklist** · Roteiro · Orçamento · Ocorrências · Anexos · Linha do tempo. A aba Checklist mostra quantas tarefas já foram feitas (ex.: 5/16).

**Aba Checklist** (`/eventos/<id>/checklist`), seguindo o design aprovado:
- **Concluir com um clique** no círculo da tarefa. Clicar de novo reabre.
- **Grupos por prazo**, em ordem de data: *Atrasadas*, *Esta semana*, *Próximas semanas*, *Semana do evento*, *Pós-evento*, *Sem prazo*. As concluídas ficam recolhidas no fim.
- **Prazo legível:** "Atrasada 8 dias" em vermelho, "Em 3 dias" em amarelo, data simples quando ainda está longe.
- **Contadores que filtram:** Atrasadas, Vencem esta semana, Sem responsável e Minhas tarefas. "Minhas" são as tarefas cujo responsável é o seu e-mail de acesso.
- **Busca** instantânea e opção de **agrupar por prazo, por etapa ou por responsável**.
- **Painel de detalhes** ao lado: situação em botões, prazo (com "X dias antes do evento"), responsável (com sugestões de pessoas e áreas), etapa, orientação, campos do modelo e **observações em lista**, com autor e data. **Tudo salva sozinho** e aparece "Salvo às 14:32".
- **Adicionar tarefa** direto em cada grupo, já com uma data sugerida para o período, ou pelo botão *+ Nova tarefa*, que também dá acesso à biblioteca de modelos.
- **Ações em lote:** marque a caixinha à esquerda de várias tarefas para *Concluir*, *Atribuir a*, *Adiar prazo X dias*, *Não se aplica* ou *Reabrir* de uma vez.
- **Excluir tarefa** no rodapé do painel. A exclusão fica registrada na linha do tempo do evento.
- **No celular,** o painel abre em tela cheia, com "← Voltar à lista".
- **Evento sem checklist:** aparece o botão *Gerar checklist pelos modelos*.

**Página do evento (aba Resumo).** No lugar da lista longa entrou um resumo com a porcentagem, as atrasadas, as próximas tarefas e o botão *Abrir checklist*.

**Links atualizados.** O Checklist consolidado, o painel, a agenda e os e-mails de lembrete agora abrem a tarefa direto na aba nova.

**Observações antigas.** O texto que já existia no campo "Observações" de cada tarefa aparece como *Registro anterior*, no topo da lista de observações. Nada se perde.

## Como instalar

1. Pare o sistema e **faça uma cópia de segurança da pasta inteira** (incluindo `instance/`).
2. Extraia este pacote na pasta do projeto, substituindo os arquivos. **Não** substitua o banco nem o `.env`.
3. Inicie normalmente. O banco ganha só a tabela de observações das tarefas.
4. Ctrl+F5 no navegador.
5. Teste rápido: `python -m unittest tests.test_sistema -v` deve mostrar 9 testes OK.
