# FMABC Eventos — MVP inicial

Aplicação web de apoio ao Setor de Eventos do Centro Universitário FMABC. Esta primeira versão demonstra o fluxo integrado entre solicitação, triagem, aprovação, checklist e acompanhamento por protocolo.

## O que já funciona

- **Formulário público de solicitação** em `/solicitar`, sem necessidade de login para o solicitante.
- **Protocolo único** ao registrar uma solicitação.
- **Consulta externa de andamento** em `/acompanhar`, protegida por protocolo + e-mail cadastrado.
- **Painel interno com login**: indicadores, solicitações recentes e agenda próxima.
- **Busca e filtros** por status, evento, protocolo, área e solicitante.
- **Triagem interna**: status, prioridade, responsável e observações internas.
- **Checklist automático configurável** quando o status muda para “Aprovado” ou “Em planejamento”. Tarefas gerais e condicionais são geradas conforme categoria, formato, serviços de apoio e itens selecionados; os prazos são calculados em relação à data do evento.
- **Categoria do evento** como pergunta adicional, distinta do formato presencial/on-line/híbrido, usada para personalizar o checklist.
- **Checklist operacional editável** com status individual (Não iniciada, Em andamento, Aguardando terceiro, Concluída e Não se aplica), prazo, responsável, detalhamento e observações.
- **Modelos de checklist** configuráveis por administradores em `/modelos-checklist`; ativar, inativar, criar e editar tarefas para futuros eventos.
- **Agenda e comunicação com áreas** em `/comunicacao`, com agenda mensal, participação por departamento, prévia editável, envio opcional SMTP e histórico de comunicados.
- **Cadastros de apoio** configuráveis por administradores em `/cadastros-apoio`, com material/recurso, categoria, quantidade, localização, disponibilidade e observações.
- **Itens do checklist manual incorporados**: autorização e assinaturas, programação, reunião inicial, artes e aprovações, palestrantes, minibiografias e fotos, montagem, lista de presença/QR Code, certificados, etiquetas, coffee break, estacionamento, materiais institucionais, recepção e pós-evento.
- **Gestão de acessos**: administradores podem criar contas individuais para a equipe.
- Interface responsiva, em português, com identidade visual inspirada nas cores verde e azul escuro da FMABC.

## Requisitos

- Python 3.10 ou superior (validado no desenvolvimento com Python 3.13).
- As dependências Flask, Waitress e Openpyxl são instaladas por `requirements.txt`; o Openpyxl é usado apenas para ler a planilha histórica selecionada para importação.
- Acesso à internet apenas para instalar as dependências na primeira execução.

## Executar no Windows

1. Extraia esta pasta em um local de trabalho.
2. Abra o Prompt de Comando ou PowerShell dentro da pasta `fmabc_eventos`.
3. Crie e ative o ambiente virtual:

   ```powershell
   python -m venv .venv
   .venv\Scripts\Activate.ps1
   ```

4. Instale as dependências:

   ```powershell
   python -m pip install -r requirements.txt
   ```

5. Copie `.env.example` para `.env` e abra o arquivo `.env` para editar. Antes da primeira execução, defina:
   - `SECRET_KEY`: uma chave longa, aleatória e exclusiva;
   - `ADMIN_EMAIL`: e-mail da pessoa administradora;
   - `ADMIN_PASSWORD`: senha inicial com pelo menos 6 caracteres.

   Caso `ADMIN_PASSWORD` fique vazio, o primeiro acesso administrativo será gerado automaticamente e exibido no console. Guarde a senha gerada. As variáveis de ambiente criam a primeira conta quando o banco ainda está vazio; mudar a variável depois não troca automaticamente a senha de uma conta já criada.

6. Inicie a aplicação:

   ```powershell
   python app.py
   ```

7. Abra no navegador:
   - Formulário do solicitante: `http://127.0.0.1:5000/solicitar`
   - Acesso da equipe: `http://127.0.0.1:5000/login`
   - Acompanhamento de protocolo: `http://127.0.0.1:5000/acompanhar`
   - Modelos de checklist (administrador): `http://127.0.0.1:5000/modelos-checklist`
   - Cadastros de apoio (administrador): `http://127.0.0.1:5000/cadastros-apoio`
   - Agenda e comunicação com áreas: `http://127.0.0.1:5000/comunicacao`

[Guia do módulo de agenda e comunicação](AGENDA_COMUNICACAO.md).

O banco SQLite é criado automaticamente em `instance/fmabc_eventos.db`. Para testes, use dados fictícios.

## Publicação em servidor

A aplicação pode ser servida com Waitress (incluído em `requirements.txt`), por exemplo:

```bash
waitress-serve --listen=0.0.0.0:5000 app:app
```

A publicação institucional exige HTTPS, `SECRET_KEY` forte, senha administrativa definida, banco de dados e cópias de segurança em armazenamento persistente, regras de acesso de rede e testes de recuperação. O SQLite nesta versão é adequado para protótipo e operação pequena; para múltiplas pessoas usando o sistema simultaneamente em produção, recomendo migrar para PostgreSQL e manter o banco fora do armazenamento efêmero do servidor.

## Limites desta versão — antes de colocar em uso real

Este é um **MVP funcional para validação do fluxo**, não uma implantação institucional pronta. Antes de inserir dados reais, recomendo validar com a área de TI e o encarregado de proteção de dados da FMABC:

- integração com login institucional Microsoft/Google (SSO);
- banco PostgreSQL gerenciado, rotinas de backup e restauração testada;
- envio automático de e-mails para confirmação, pendências e mudanças de status;
- trilha de auditoria de quem alterou status e tarefas;
- política de acesso por perfil e revisão de permissões;
- política de retenção, privacidade e tratamento de dados pessoais (LGPD);
- exportação de relatórios, anexos e calendário compartilhado, se necessário.

O acompanhamento público apresenta o status geral. As observações internas do evento ficam restritas à área autenticada da equipe. Ainda assim, use dados fictícios até concluir a revisão de segurança e privacidade.

## Estrutura do projeto

```text
fmabc_eventos/
├── app.py                 # Aplicação Flask, rotas e lógica do fluxo
├── requirements.txt       # Dependências Python
├── .env.example           # Modelo das configurações locais
├── Procfile               # Comando de inicialização em hosts compatíveis
├── instance/              # Banco SQLite local (criado na execução)
├── static/app.css         # Interface responsiva
└── templates/             # Páginas HTML
```

## Próxima etapa recomendada

Validar campos, status e regras do checklist com o Setor de Eventos; em seguida, migrar a persistência para PostgreSQL, adicionar notificações por e-mail institucional e autenticação corporativa antes da publicação oficial.


## Decisão de formulário confirmada

A pergunta 14 do formulário original foi mantida separada da pergunta 1. A pergunta 14 coleta telefone/WhatsApp e e-mail de contato da pessoa responsável; a pergunta 1 continua sendo o e-mail principal usado para consultar o andamento junto com o protocolo. Os dois e-mails não são unificados.


## Ajuste de formulário — opção “Nenhum” removida

Conforme decisão da coordenação, a opção “Nenhum” foi retirada das perguntas 8 (serviços de apoio) e 13 (itens necessários). Os dois grupos continuam obrigatórios, com validação para exigir ao menos uma opção disponível. A pergunta 14 continua separada da pergunta 1 e mantém telefone/WhatsApp e e-mail de contato.


## Implementação do checklist manual — 20/10/2026

- O formulário inclui uma pergunta adicional obrigatória de **categoria do evento** para distinguir o formato do evento de seu tipo operacional. O campo aceita categoria livre quando a opção “Outro” for escolhida.
- O checklist é composto por tarefas “Todos os eventos” e tarefas condicionais acionadas por serviço de apoio, item solicitado, modalidade ou categoria exata.
- Cada tarefa contém título, etapa/categoria, descrição, prazo, status, responsável e observações independentes.
- Modelos são alterados em **Modelos de checklist**. Mudanças se aplicam a checklists gerados posteriormente; não apagam nem substituem tarefas já registradas.
- O cadastro **Cadastros de apoio** recebe uma carga inicial a partir do checklist manual. Valores incompletos ou conflitantes foram marcados “Precisa confirmar”. Em especial, a planilha contém contagens divergentes para porta-banners; nenhuma quantidade foi fixada como inventário confirmado.
- Itens citados em anotações manuais (como restaurantes, toalhas de TNT, porta-banners e material institucional) foram incluídos como recursos/referências de apoio, com disponibilidade pendente de validação.

## Validação feita nesta versão

A sintaxe Python foi compilada com sucesso; os 11 templates HTML/Jinja foram analisados; o banco SQLite em memória foi usado para validar a criação de uma solicitação, a geração de tarefas por categoria/apoio/itens e os registros iniciais do catálogo. Não foi possível iniciar a aplicação Flask neste ambiente de desenvolvimento porque o pacote Flask não está instalado e a instalação de dependências não teve acesso à internet. Execute os passos de instalação acima em um computador com acesso à internet para fazer o teste no navegador.

## Agenda institucional e comunicação com áreas — 20/10/2026

O módulo `/comunicacao` centraliza a preparação da agenda mensal por departamento. As áreas iniciais são TI, Inspetoria, Limpeza, Manutenção e Imprensa; seus e-mails ficam vazios até serem confirmados e cadastrados por uma pessoa administradora.

- Seleção de mês, ano e departamento.
- Lista de eventos com status **Aprovado** ou **Em planejamento** no período escolhido. Eventos cancelados, realizados e ainda em triagem não entram automaticamente no comunicado.
- Classificação por evento/departamento: **Ação necessária**, **Para conhecimento** ou **Não incluir no comunicado**. Sem classificação salva, o padrão é **Para conhecimento**.
- Campo de providências que aparece no e-mail e campo de observação interna que não aparece no e-mail.
- Geração de prévia mensal por área, com assunto, destinatário e corpo editáveis antes de enviar.
- Histórico de rascunhos e envios, incluindo o método de envio (SMTP ou externo/manual) e quem registrou. O comunicado mantém um retrato dos eventos incluídos na data da geração.
- Cadastro e ativação/inativação de áreas e atualização dos destinatários (administradores).
- Importador de agenda histórica `.xlsx`: faz prévia da planilha e importa apenas eventos com data igual ou posterior ao dia da importação, marcando-os como “Em planejamento”, associando as observações de TI/Inspetoria/Limpeza/Manutenção/Imprensa e gerando checklist inicial. O importador não inventa contato ausente, preserva observações como “PSC” sem interpretar a sigla e ignora registros já cadastrados com mesma data e título.
- Envio SMTP opcional com biblioteca padrão do Python. Se o SMTP não estiver configurado, a prévia pode ser enviada pelo e-mail institucional e o envio registrado manualmente no sistema.

### Configurar envio automático

1. Confirme com a TI da FMABC o servidor SMTP autorizado, porta, método de autenticação e endereço remetente. Não presuma que uma conta Microsoft/Google aceita autenticação SMTP por senha comum.
2. Preencha no `.env` as variáveis `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM` e `SMTP_USE_TLS`.
3. Cadastre o e-mail oficial de cada departamento na seção **Áreas e destinatários** do módulo.
4. Faça um teste autorizado com um endereço interno de teste antes de enviar comunicados reais.

### Uso mensal recomendado

1. Aprove ou mova para planejamento os eventos que já podem constar da agenda.
2. Acesse **Agenda e comunicação**, selecione mês, ano e departamento.
3. Para cada evento, marque a participação da área e preencha as providências a comunicar quando necessário. O campo de observação interna é exclusivo para a equipe.
4. Clique em **Criar prévia mensal**, revise destinatário, assunto e conteúdo e salve as correções.
5. Envie por SMTP quando configurado ou encaminhe pelo e-mail institucional e registre o envio manual.
6. Consulte o histórico para verificar o que já foi comunicado. Se a agenda mudar depois do envio, gere um novo comunicado revisado para informar as alterações.

**Limites atuais:** o importador da planilha histórica já existe, mas é iniciado manualmente por administradores; ele não sincroniza alterações futuras da planilha nem detecta automaticamente alterações de eventos após o envio. O módulo não dispara comunicados recorrentes sozinho. A preparação e o envio continuam sob confirmação da equipe.


## Central de Conhecimento — Manual de Eventos FMABC (20/10/2026)

- A rota pública `/manual` oferece a área de consulta ao Manual de Cerimonial e Eventos do Centro Universitário FMABC (PDF de 2023, 67 páginas). Ela pode ser acessada por solicitantes e pela equipe sem login.
- O PDF integral foi incluído em `static/docs/manual_cerimonial_eventos_fmabc_2023.pdf` e pode ser visualizado no navegador ou baixado.
- O índice textual local está em `data/manual_eventos_index.json`. A busca recupera trechos do documento e exibe a página do PDF para conferência. Não consulta a internet nem outras fontes.
- Esta primeira implementação é uma busca conversacional/extrativa, não um modelo generativo: exibe passagens encontradas em vez de produzir paráfrases livres. Quando a correspondência é insuficiente, informa que não encontrou orientação suficiente e encaminha a pessoa ao PDF completo.
- As perguntas não são persistidas em banco de dados. O índice não é atualizado sozinho caso o PDF mude.
- Para reindexar uma nova edição, substitua o PDF e execute `python scripts/indexar_manual.py --input static/docs/manual_cerimonial_eventos_fmabc_2023.pdf --output data/manual_eventos_index.json`. Essa tarefa de desenvolvimento requer `pip install -r requirements-manual-index.txt`; a dependência PyMuPDF não é necessária para executar o site normalmente.
- O acesso ao manual é público nesta versão. Antes da publicação institucional, confirmar com a FMABC se o conteúdo deve ficar aberto a todos os visitantes do sistema ou ser restrito a usuários autenticados.


## Checklist compacto (atualização de interface)

A tela de detalhes do evento exibe agora cada tarefa como uma linha compacta, com nome, etapa, status, prazo e responsável. Ao expandir uma tarefa, a equipe pode editar detalhamento, observações e demais campos. A lista inclui busca e filtro por status.

Para aplicar a atualização em uma instalação local existente sem substituir o banco de dados nem o arquivo `.env`, pare o servidor com `Ctrl+C` e copie os arquivos `templates/event_detail.html` e `static/app.css` do pacote de atualização para a mesma pasta do projeto, sobrescrevendo apenas esses dois arquivos. Depois reinicie com `set PORT=5055` e `python app.py`.

## Visão geral com contagem regressiva

A página inicial foi atualizada para destacar o evento futuro mais próximo com contagem regressiva, indicadores por proximidade (até 3 dias, 7 dias, 30 dias ou mais) e layout responsivo. Para aplicar somente esta alteração em uma instalação local existente, consulte `ATUALIZAR_VISAO_GERAL.md`; o patch substitui apenas `templates/dashboard.html` e `static/app.css`, preservando o banco de dados.

## Agenda mensal e envio de comunicados na mesma página

Na versão atualizada, abra `/comunicacao`, selecione mês e ano e marque um ou mais departamentos destinatários. O sistema cria uma prévia individual por departamento e exibe os rascunhos na própria página para edição e envio. Os endereços não cadastrados devem ser confirmados antes do envio. Consulte `ATUALIZAR_AGENDA_COMUNICACAO.md` para instruções de aplicação do patch e uso do fluxo.

## Impressão compacta do checklist

Na tela de detalhes do evento, use **Imprimir checklist** para abrir a versão de impressão. Ela foi preparada para papel A4 em orientação paisagem, com caixa de marcação manual e campos de tarefa, categoria, status, prazo e responsável. Listas de até 24 itens são organizadas para caber em uma face; listas maiores são divididas em duas páginas, pensadas para impressão frente e verso em uma folha. Na janela do navegador, confira a prévia e selecione A4, Paisagem e Frente e verso se disponível.


## Relatórios anuais e encerramento pós-evento

A versão inclui o módulo `Relatórios de eventos` (`/relatorios`), com filtro por ano/status/categoria/setor, exportação CSV para abrir no Excel e impressão/salvamento em PDF pelo navegador.

Na tela do evento, use `Finalizar evento` para registrar o resumo da realização, público real, pontos positivos, dificuldades, melhorias e ações de acompanhamento. O evento passa ao status `Encerrado`, e o sistema cria um link individual de avaliação pós-evento para o solicitante.

O formulário de avaliação está disponível em `/avaliacao-evento/<token>` e coleta notas de 1 a 5 para experiência geral, atendimento do Setor de Eventos, comunicação, agilidade e atendimento das necessidades, além de comentários opcionais.

Para enviar convites automaticamente, configure SMTP e defina `APP_BASE_URL` no `.env` com o endereço público da aplicação. O sistema evita enviar links locais (`localhost`/`127.0.0.1`) ao solicitante. Consulte `RELATORIOS_ENCERRAMENTO_AVALIACAO.md`.


## Gestão avançada: calendário, confirmações, custos e ocorrências

Consulte `GESTAO_AVANCADA.md` para a visão funcional dos novos recursos. A aplicação inclui agenda institucional (`/agenda`), alertas de tarefas críticas, checagem preventiva de conflitos de espaço/horário, links para resposta dos departamentos, roteiro operacional por evento, controle de orçamento/custo realizado e registro de ocorrências/lições aprendidas. Os valores e endereços de departamentos precisam ser confirmados antes de uso institucional.

Antes de aplicar atualizações, faça backup de `instance/fmabc_eventos.db` e `.env`. Para que os departamentos respondam aos links recebidos por e-mail, a aplicação precisa estar publicada em um endereço acessível e usar `APP_BASE_URL` correto.

## Verificação de disponibilidade de espaços

O formulário público `/solicitar` tem seletores separados para horário de início e término, em intervalos fixos de 30 minutos (por exemplo, 10h, 10h30, 11h). O término precisa ser posterior ao início. O formulário consulta a agenda e bloqueia o envio quando há conflito no mesmo espaço/data e faixa de horário; a validação é repetida no servidor. Eventos antigos sem horário final são tratados de forma conservadora quando podem se sobrepor. Consulte `ATUALIZAR_HORARIOS_EVENTO.md` para instalar esta melhoria.

## Equipe e acesso à triagem

A área **Equipe e acessos** permite editar e-mail/perfil, redefinir senha, bloquear/desbloquear ou excluir contas. O sistema impede bloquear ou excluir a própria conta e protege o último administrador ativo. Consulte `ATUALIZAR_EQUIPE_ACESSOS.md` para atualizar uma instalação local sem substituir o banco de dados. Usuários de perfil `staff` entram diretamente em `Triagem e acompanhamento` (`/triagem`) depois do login.

## Gestão de tarefas por departamento

A página **Agenda e comunicação** permite atribuir uma providência a uma área, definir responsável e prazo e acompanhar o recebimento, a resposta e o status da execução. Cada ação necessária pode ter um link individual (`/confirmar-area/<token>`) para a área registrar que recebeu a solicitação, informar quem responde, atualizar o estado da providência e justificar bloqueios. O histórico de mudanças fica disponível ao Setor de Eventos na própria agenda mensal. Consulte `ATUALIZAR_TAREFAS_DEPARTAMENTO.md` para instalar e testar essa funcionalidade.
