# Fase 2 — Organizar a base (26/10/2026)

Este pacote é **cumulativo**: já inclui todas as correções de 26/10 (orçamento, modelos de checklist, horários, valores, edição de evento, segurança). Se você ainda não instalou o pacote anterior, instale só este.

## O que há de novo

**1. Espaços e bloqueios** (menu lateral → *Espaços e bloqueios*, só administradores)
- Os 10 espaços da lista antiga são cadastrados automaticamente na primeira inicialização, com a capacidade que já aparecia no nome.
- Para cada espaço: capacidade, prédio, recursos, acessibilidade, observações e **apelidos** (outras grafias). Os apelidos fazem a checagem de conflito reconhecer o local mesmo quando ele foi escrito de outro jeito.
- Na mesma tela, um quadro lista os **locais dos eventos que não batem com nenhum espaço cadastrado**. Nos seus dados aparece "CENFORPE · 2 eventos": cadastre-o como espaço, ou como apelido de um espaço existente, se for controlado pela FMABC.
- **Bloqueios**: bloqueie um espaço por um período, de dia inteiro ou em parte do dia, informando o motivo (ex.: manutenção). Novas solicitações nesse período são recusadas e o motivo aparece para o solicitante. Ao bloquear, o sistema avisa se já existem eventos naquele espaço e período.
- A opção "Controlar agenda deste espaço" desligada serve para locais que não precisam de checagem de conflito.
- Espaços inativados somem do formulário, mas os eventos antigos são mantidos.
- Se você renomear um espaço, o nome antigo vira apelido automaticamente, e os eventos já registrados continuam sendo reconhecidos.
- **Aviso de capacidade**: se o público previsto passar da capacidade do espaço, o formulário público mostra um aviso (não bloqueia) e a página do evento exibe um alerta amarelo.
- A **Agenda institucional** mostra os bloqueios do mês.

**2. Eventos de vários dias no formulário público**
- Ao lado da data do evento há um campo opcional de término.
- A disponibilidade é conferida em todos os dias do período, inclusive na verificação automática enquanto o solicitante preenche o formulário.
- Limite de 31 dias por evento.

**3. Linha do tempo do evento** (página do evento, abaixo do checklist)
- Registra automaticamente: a criação da solicitação, mudanças de status, prioridade e responsável (na triagem e na página do evento), edições dos dados, anexos e o encerramento.
- Campo para **comentários internos** da equipe (ex.: "liguei para a solicitante; o público subiu para 120").

**4. Anexos do evento** (página do evento → *Anexos*)
- Envie ofícios, contratos, notas fiscais, artes, listas de presença e fotos, com até 15 MB por arquivo.
- Tipos aceitos: PDF, Word, Excel, PowerPoint, OpenDocument, texto, CSV, imagens e ZIP.
- Os arquivos ficam em `instance/anexos/` e só são baixados por quem está logado.

**5. Código dividido em módulos**
O antigo `app.py`, de cerca de 4.300 linhas, virou um ponto de entrada curto e uma pasta `sistema/`:

| Arquivo | Conteúdo |
| --- | --- |
| `sistema/core.py` | configuração, banco de dados, constantes e funções compartilhadas |
| `sistema/publico.py` | formulário público, acompanhamento, login, manual, avaliação |
| `sistema/eventos.py` | painel, triagem, eventos, edição, linha do tempo, anexos, roteiro, ocorrências, agenda |
| `sistema/checklist.py` | tarefas, checklist consolidado, impressão, modelos |
| `sistema/orcamento.py` | orçamento, cotações, comparativo de custos |
| `sistema/relatorios.py` | relatórios anuais e CSV |
| `sistema/comunicacao.py` | agenda por área, comunicados, importação de planilha |
| `sistema/admin.py` | cadastros de apoio, equipe e acessos, espaços |

Os endereços das páginas e a forma de iniciar o sistema (`python app.py` ou `iniciar_windows.bat`) não mudaram.

## Como instalar

1. Pare o sistema (Ctrl+C).
2. **Faça uma cópia de segurança da pasta inteira do projeto**, incluindo `instance/fmabc_eventos.db`.
3. Extraia este pacote na pasta do projeto, substituindo os arquivos quando o Windows perguntar. São eles:
   - `app.py`, que agora é curto (é normal);
   - a pasta `sistema/` (nova);
   - `templates/`: `agenda.html`, `base.html`, `event_detail.html`, `event_edit.html`, `request_form.html`, `venues.html`;
   - `static/app.css`;
   - `tests/test_sistema.py`;
   - `.gitignore` (novo; veja abaixo).
4. **Não** substitua o banco de dados nem o `.env`.
5. Inicie normalmente. Na primeira inicialização o banco recebe só acréscimos: as tabelas de espaços, bloqueios e anexos, e a coluna de tipo na linha do tempo. Nenhum dado é apagado.
6. Ctrl+F5 no navegador.

## Como conferir

- No terminal, com o ambiente ativo: `python -m unittest tests.test_sistema -v` deve mostrar 6 testes OK. O teste usa banco e pasta temporários.
- Abra **Espaços e bloqueios**: devem aparecer os 10 espaços e o aviso sobre o CENFORPE.
- No formulário público, escolha o Salão Nobre (81 lugares) com público de 150: deve aparecer o aviso de capacidade.
- Abra um evento: os painéis **Anexos** e **Linha do tempo** ficam abaixo do checklist.

## Cópia de segurança a partir de agora

Além do banco `instance/fmabc_eventos.db`, inclua a pasta `instance/anexos/` nos backups.

## Sugestão: controle de versão (Git)

O `.gitignore` incluído deixa de fora o banco, os anexos, o `.env` e o ambiente virtual. Se instalar o Git, rode na pasta do projeto:

```
git init
git add .
git commit -m "Fase 2"
```

A partir daí, cada atualização vira um commit e dá para voltar atrás se algo der errado. Assim, o problema da Fase 3 (um patch apagando o outro) não se repete.

## Ainda pendente com você

- Trocar a `SECRET_KEY` e a senha do administrador (veja o pacote anterior).
- Na edição dos eventos importados, conferir os horários sugeridos.
- Cadastrar o CENFORPE (ou outros locais externos recorrentes) em **Espaços e bloqueios**.
