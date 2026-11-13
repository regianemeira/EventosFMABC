# Banco de dados gratuito e permanente (PostgreSQL via Neon)

Este pacote muda o sistema para aceitar dois bancos de dados:

- **SQLite** (como sempre foi): continua funcionando exatamente igual na sua
  máquina local, sem precisar mudar nada. É o que o sistema usa quando a
  variável `DATABASE_URL` não está definida.
- **PostgreSQL**: usado automaticamente quando `DATABASE_URL` estiver
  preenchida. É o que vamos configurar no Render, usando o **Neon**
  (neon.tech), que tem um plano gratuito permanente (sem prazo de expiração),
  suficiente para o seu sistema.

Você não perde a praticidade de testar local com SQLite, e ganha persistência
de verdade em produção, sem pagar nada.

## 1. Extrair este pacote

Extraia por cima da pasta do seu projeto, substituindo os arquivos. Ele inclui:
- `sistema/db.py` (novo): a "camada de tradução" entre o sistema e o PostgreSQL.
- `sistema/core.py` (atualizado): passa a usar essa camada para abrir conexões.
- `requirements.txt` (atualizado): adicionei `psycopg2-binary`, a biblioteca
  que fala com PostgreSQL.
- `.env.example` (atualizado): documenta a nova variável `DATABASE_URL`.
- `render.yaml` (atualizado): agora usa o plano **gratuito** do Render, sem
  disco pago — o banco fica no Neon, não no Render.
- `tests/test_sistema.py`: sem mudanças — todos os 17 testes automatizados
  continuam passando (rodei contra uma cópia do seu banco real antes de
  fechar este pacote).

## 2. Criar o banco gratuito no Neon

1. Entre em **neon.tech** e crie uma conta (dá para entrar com o GitHub).
2. Crie um projeto novo. Nome sugerido: `fmabc-eventos`.
3. O Neon já cria um banco padrão e mostra uma **connection string**, algo como:
   ```
   postgresql://usuario:senha@ep-xxxxx.sa-east-1.aws.neon.tech/neondb?sslmode=require
   ```
4. Copie essa string inteira — é ela que vai na variável `DATABASE_URL`.

**Atenção a um detalhe do Neon:** o banco gratuito "dorme" depois de alguns
minutos sem uso, e acorda sozinho na primeira consulta seguinte (leva cerca
de 1 segundo a mais nesse primeiro acesso). Isso é normal e não é um erro —
é assim que o plano gratuito funciona.

## 3. (Recomendado) Testar antes de mexer no Render

Se sua máquina tiver acesso à internet (diferente deste ambiente onde eu
trabalho, que é isolado), vale testar a conexão com o Neon antes de apontar o
site no ar para lá — assim, se algo precisar de ajuste, descobrimos localmente
primeiro.

1. Na pasta do projeto, com o ambiente virtual ativo:
   ```bash
   pip install -r requirements.txt
   ```
2. Defina a variável temporariamente e rode os testes automatizados contra o
   Neon (troque pela sua connection string real):

   **Windows (PowerShell):**
   ```powershell
   $env:DATABASE_URL="postgresql://usuario:senha@ep-xxxxx.sa-east-1.aws.neon.tech/neondb?sslmode=require"
   python -m unittest tests.test_sistema -v
   ```
   **Linux/Mac:**
   ```bash
   DATABASE_URL="postgresql://usuario:senha@ep-xxxxx.sa-east-1.aws.neon.tech/neondb?sslmode=require" python -m unittest tests.test_sistema -v
   ```
3. Se aparecer `OK` no final (seguido dos nomes dos testes com `ok`), está
   tudo funcionando contra o Neon. Se der erro, me cole a mensagem completa
   que eu ajusto.

Este teste cria e usa um banco de teste à parte (não mexe nos seus dados
reais) — ele só usa a mesma connection string para validar que o sistema
consegue conversar com o PostgreSQL do Neon.

## 4. Apontar o Render para o Neon

No painel do Render, no seu serviço já criado:

1. Vá em **Environment**.
2. Adicione a variável `DATABASE_URL` com a connection string do Neon.
3. Se você tinha configurado `DATABASE_PATH` antes, pode deixar — ela só é
   usada quando `DATABASE_URL` está vazia, então não atrapalha.
4. Se você havia criado um **Disk** (disco pago) seguindo o guia anterior e
   quer economizar, pode removê-lo agora em **Disks** (não é mais necessário)
   e trocar o plano do serviço de `Starter` para `Free` em **Settings**.
5. Salve. O Render reinicia o serviço sozinho, já lendo a nova variável.

Acompanhe o log do deploy: na primeira inicialização com o Neon, o sistema
cria as tabelas automaticamente (é a mesma rotina que já cria o banco SQLite
na primeira vez) e, se ainda não existir nenhum usuário, cria a conta
administrativa com `ADMIN_EMAIL`/`ADMIN_PASSWORD`.

## 5. Sobre os dados que você já tinha

Se o site no Render já estava no ar e você cadastrou eventos de teste nele
antes de fazer essa mudança, esses dados **ficaram no SQLite antigo** (que
será substituído) e não aparecem automaticamente no Neon — o sistema começa
"zerado" no banco novo, só com a conta administrativa recriada.

Se isso importa (por exemplo, se já tem eventos reais cadastrados que você
quer manter), me avise antes de aplicar a variável `DATABASE_URL` em
produção — eu preparo um script para copiar os dados do SQLite atual para o
Neon, para não perder nada.

## 6. Resumo do que mudou no sistema

- `sistema/db.py` é a única parte nova de verdade: ele traduz automaticamente
  as instruções que o sistema já usava (pensadas para SQLite) para o formato
  que o PostgreSQL entende — isso evita reescrever cada rota do sistema.
- Nenhuma tela, rota ou funcionalidade do sistema mudou. O que muda é só
  *onde* os dados ficam guardados.
- Rodando localmente sem `DATABASE_URL`, está tudo exatamente como antes
  (SQLite, arquivo em `instance/`).
