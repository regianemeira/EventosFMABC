# FMABC Eventos — Regras do checklist e cadastros de apoio

## Como o checklist é gerado

Quando o status do pedido for alterado para **Aprovado** ou **Em planejamento**, o sistema verifica o catálogo de modelos ativos e cria as tarefas correspondentes. O checklist não é gerado antes da triagem e não substitui as tarefas já existentes.

Cada modelo tem:
- Nome da tarefa;
- Etapa/categoria;
- Orientação de execução;
- Condição de ativação: todos os eventos, serviço de apoio, item solicitado, modalidade ou categoria do evento;
- Prazo relativo à data do evento em dias (valor negativo = antes; zero = dia do evento; positivo = depois);
- Responsável padrão opcional;
- Indicador ativo/inativo.

Atenção: os valores da condição precisam corresponder exatamente às opções do formulário. A tela oferece uma lista de sugestões para reduzir erros de digitação.

## Status de tarefa

- **Não iniciada** — ainda não começou;
- **Em andamento** — alguém está trabalhando;
- **Aguardando terceiro** — depende de uma área, fornecedor ou convidado;
- **Concluída** — finalizada;
- **Não se aplica** — dispensada para aquele evento.

Cada tarefa também tem prazo, responsável, detalhamento e observações separados.

## Cadastro de apoio

O cadastro mantém o nome, categoria, quantidade conhecida, localização/responsável, disponibilidade e observações. Os cadastros iniciais vieram do checklist manual enviado em 20/10/2026. Eles devem ser revisados pela equipe antes de serem usados para confirmar disponibilidade a um solicitante. Registros que não tenham quantidade conhecida ficam em branco; divergências históricas, especialmente para porta-banners, estão anotadas para validação.

## Categorias iniciais de evento

Congresso / Simpósio; Aula / Atividade acadêmica; Cerimônia / Colação de grau; Evento institucional; Palestra / Mesa-redonda; Curso / Oficina; Visita institucional; Reunião; Inauguração / Lançamento; Premiação / Homenagem; Outro.

A categoria é uma pergunta adicional ao formulário original. Ela não substitui a pergunta original de modalidade (Presencial, On-line, Híbrido).
