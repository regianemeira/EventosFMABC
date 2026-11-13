ATUALIZAÇÃO DE NAVEGAÇÃO — FMABC EVENTOS

Objetivo
- Remover a aba separada “Triagem e acompanhamento” do menu lateral.
- Manter “Solicitações e eventos” como área principal para consulta e acompanhamento.
- Fazer com que usuários do perfil Equipe (staff) entrem diretamente em “Solicitações e eventos”.
- Manter as rotas internas de triagem existentes no código, para não apagar funcionalidades nem dados neste ajuste.

Instalação segura
1. Pare o servidor local do FMABC Eventos.
2. Faça backup da pasta do projeto e do banco instance/fmabc_eventos.db.
3. Extraia este ZIP em uma pasta temporária.
4. Copie app.py para a raiz do projeto e templates/base.html para a pasta templates, substituindo os arquivos correspondentes.
5. Não substitua o banco de dados nem o arquivo .env.
6. Reinicie o servidor e entre com um usuário do perfil Equipe para confirmar que a tela inicial é “Solicitações e eventos”.

Observação
Esta atualização unifica a navegação e remove a aba duplicada do menu. As rotas e ações de triagem foram preservadas para evitar perda de funcionalidade. Uma futura reorganização poderá incorporar ações específicas de triagem diretamente na listagem, caso seja necessário, após validar a tela atual e seus fluxos.
