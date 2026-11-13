# Colocando o sistema on-line (GitHub + Render)

Este guia parte do princípio de que o sistema já está rodando bem na sua máquina
local. Vamos publicá-lo para que você (e quem precisar) acesse por um link da
internet, sem depender do seu computador ligado.

## 0. Antes de tudo: um alerta importante sobre o banco de dados

Seu sistema usa **SQLite**, um arquivo único (`instance/fmabc_eventos.db`). Isso
é ótimo para rodar local, mas em um serviço como o Render, por padrão, o disco
é **apagado a cada novo deploy** (cada vez que você atualizar o código). Ou
seja: sem um passo extra, você perderia eventos, tarefas e usuários cadastrados
toda vez que subir uma correção.

A solução é um **disco persistente** (Render chama de "Disk"), que guarda o
banco fora da área que é recriada a cada deploy. Isso é explicado no passo 4.
Disco persistente **exige um plano pago** do Render (o plano "Starter", hoje
em torno de US$ 7/mês para o serviço web, mais um valor pequeno pelo disco).

Se por enquanto você só quer **testar a aparência e o funcionamento geral**,
pode usar o plano gratuito sem disco — tudo funciona normalmente, só que os
dados somem a cada deploy/reinício. Dá para avaliar o sistema, mas não é
seguro para uso real da equipe. Quando decidir usar de verdade, ative o disco.

## 1. Preparar os arquivos (já feito nesta entrega)

Este pacote já inclui:
- `.gitignore` corrigido (adicionei uma regra que faltava: o arquivo
  `.env.orig`, que tinha sua senha e chave secreta reais, **não estava
  protegido** e iria parar publicado no GitHub. Corrigido agora.)
- `render.yaml`: um "modelo" que o Render lê automaticamente para configurar
  o serviço, o disco e as variáveis de ambiente, sem você preencher tudo manual
  na tela.
- `Procfile` e `requirements.txt`: já existiam no seu projeto e já estão
  corretos para produção (usam `waitress`, um servidor adequado para produção
  — o `python app.py` que você usa localmente é só para desenvolvimento).

Extraia este pacote por cima da pasta do seu projeto, substituindo os arquivos
indicados, antes de seguir para o passo 2.

**Apague (ou deixe fora da pasta que vai para o GitHub) estes arquivos, que são
grandes, antigos ou não servem para produção:**
- `app_monolitico_antigo.py` (backup antigo, já fora do `.gitignore` agora)
- `fmabc_eventos.zip` (o zip original que você me enviou)
- a pasta `instance/` inteira (banco e anexos — nunca deve ir para o GitHub)
- `.env` e `.env.orig` (segredos reais)

## 2. Criar o repositório no GitHub

1. Entre em github.com, logado com sua conta (ou crie uma, é grátis).
2. Clique em **New repository**. Nome sugerido: `fmabc-eventos`. Marque como
   **Private** (o código tem lógica interna da FMABC; não precisa ser público).
   Não marque "Add a README" (você já tem um).
3. Na pasta do projeto, pelo terminal (Prompt de Comando/PowerShell no Windows,
   dentro da pasta do sistema):

   ```bash
   git init
   git add .
   git commit -m "Primeira versão para deploy"
   git branch -M main
   git remote add origin https://github.com/SEU-USUARIO/fmabc-eventos.git
   git push -u origin main
   ```

   Troque `SEU-USUARIO` pelo seu usuário do GitHub. Na primeira vez, o GitHub
   vai pedir login (ou um token de acesso, se pedir senha e não aceitar —
   gere em Settings → Developer settings → Personal access tokens).

4. Confira no site do GitHub se a pasta `instance/` e os arquivos `.env*` **não
   aparecem** no repositório. Se aparecerem, pare e me avise antes de continuar
   — significa que o `.gitignore` não pegou algo e precisamos remover do
   histórico antes de prosseguir.

## 3. Criar a conta no Render

1. Entre em render.com e crie uma conta (dá para entrar direto com o GitHub).
2. Autorize o Render a acessar seus repositórios (ele pede permissão na
   primeira vez).

## 4. Criar o serviço a partir do `render.yaml`

1. No painel do Render, clique em **New +** → **Blueprint**.
2. Selecione o repositório `fmabc-eventos`.
3. O Render vai ler o `render.yaml` e mostrar o serviço `fmabc-eventos`
   configurado, com:
   - plano `starter` (pago, necessário para o disco persistente — veja o
     passo 0; se quiser só testar de graça, veja a observação no fim deste
     passo),
   - um disco de 1 GB montado em `/var/data`,
   - as variáveis de ambiente já nomeadas (algumas pedem para você preencher
     o valor, porque são segredos — veja o próximo passo).
4. Clique em **Apply** / **Create**.

Durante a criação, o Render vai pedir para você preencher os valores marcados
como "sync: false" no `render.yaml` (ele pede isso direto na tela, não precisa
editar o arquivo):

| Variável | O que colocar |
|---|---|
| `ADMIN_EMAIL` | e-mail da conta administradora inicial |
| `ADMIN_PASSWORD` | senha inicial (mínimo 6 caracteres) — troque depois do primeiro login |
| `APP_BASE_URL` | preencha **depois** que o Render gerar o endereço do site (passo 5), algo como `https://fmabc-eventos.onrender.com` |
| `SMTP_HOST`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM` | dados do servidor de e-mail da FMABC, se for usar o envio de comunicados e lembretes. Pode deixar em branco por enquanto e preencher depois, em Settings → Environment, quando a TI passar os dados. |

`SECRET_KEY` é gerado automaticamente pelo Render (`generateValue: true`) —
você não precisa preencher.

**Se quiser testar de graça primeiro:** na tela de criação, troque o plano de
`Starter` para `Free` e remova a seção de disco (ou simplesmente ignore o
aviso sobre disco — o Render cria o serviço mesmo sem disco no plano grátis,
só que os dados não persistem). Depois, quando for para uso real, edite o
serviço e mude o plano — o Render permite ativar o disco a qualquer momento.

## 5. Primeiro acesso

1. Espere o build terminar (alguns minutos, acompanhe o log na tela do Render).
2. O Render mostra um endereço parecido com
   `https://fmabc-eventos.onrender.com`. Abra-o.
3. Volte em Settings → Environment e preencha `APP_BASE_URL` com esse mesmo
   endereço (ele é usado para montar os links enviados por e-mail, como
   confirmação e avaliação pós-evento). Salvar essa variável reinicia o
   serviço automaticamente.
4. Faça login com o `ADMIN_EMAIL`/`ADMIN_PASSWORD` que você definiu.
5. Troque a senha administrativa pelo próprio sistema, em Equipe.

## 6. Depois do primeiro deploy

- Qualquer `git push` para o branch `main` faz o Render atualizar o site
  sozinho (`autoDeploy: true`), em 1 a 3 minutos.
- O banco e os anexos ficam no disco (`/var/data`), então sobrevivem aos
  updates — só não existirá mais no plano `Free` sem disco.
- Para ver os dados ao vivo ou copiar o banco, use a aba **Shell** do próprio
  serviço no painel do Render (terminal dentro do servidor).
- Quer migrar os dados que já existem na sua máquina local para o Render?
  Me avise — dá para enviar o arquivo `instance/fmabc_eventos.db` atual pelo
  Shell do Render, para já subir com o histórico que você tem hoje em vez de
  começar do zero.

## Resumo do que muda do "rodando local" para "rodando no Render"

| Local | Render |
|---|---|
| `python app.py` | `waitress-serve ... app:app` (já configurado no `Procfile`) |
| `.env` na pasta | Variáveis de ambiente na tela do Render |
| Banco em `instance/` | Banco em `/var/data` (disco persistente) |
| Acesso só na sua rede | Acesso por `https://...onrender.com` (ou um domínio seu, configurável depois em Settings → Custom Domain) |
