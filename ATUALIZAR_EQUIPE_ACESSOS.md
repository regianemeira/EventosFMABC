# Atualização: Equipe, acessos e triagem inicial

## O que esta atualização acrescenta

- Edição do e-mail e do perfil de cada conta.
- Redefinição administrativa de senha com confirmação e mínimo de 6 caracteres.
- Bloqueio e desbloqueio de usuários.
- Exclusão de contas com confirmação.
- Proteções para impedir que o usuário bloqueie/exclua a própria conta e para preservar pelo menos um administrador ativo.
- Validação de conta ativa em cada rota protegida. Uma conta bloqueada ou excluída perde acesso na próxima navegação.
- Página `Triagem e acompanhamento` em `/triagem`, com lista de solicitações, filtros e edição de status, prioridade, responsável e observações internas.
- Usuários com perfil `Equipe — triagem e eventos` são encaminhados diretamente para `/triagem` após o login. Administradores continuam iniciando na visão geral.
- O cadastro criado pelo administrador não abre uma sessão para a nova pessoa automaticamente. A nova pessoa deverá entrar com o e-mail e a senha temporária que recebeu; no primeiro login, será direcionada à triagem.
- A senha inicial e a senha de redefinição devem ter no mínimo 6 caracteres.

## Atualização no Windows

1. Pare o servidor na janela preta com `Ctrl+C`.
2. Faça uma cópia de segurança de `instance\fmabc_eventos.db` e do arquivo `.env`.
3. Extraia o ZIP de atualização na pasta em que está o `app.py`, por exemplo `C:\Users\regiane.meira\Downloads\fmabc_eventos`, mantendo a estrutura `templates` e `static` e autorizando a substituição dos arquivos.
4. A atualização não traz banco de dados nem `.env`; não apague a pasta `instance`.
5. Inicie novamente:

```bat
set PORT=5055
python app.py
```

6. Acesse `http://127.0.0.1:5055/login`. Para testar o redirecionamento, encerre a sessão e entre com uma conta de perfil `Equipe`.

## Notas

- A migração adiciona a coluna `is_active` à tabela `users` caso o banco local ainda não tenha esse campo, sem apagar registros.
- Senhas são armazenadas como hash; não há visualização da senha atual, apenas redefinição.
- Antes de usar institucionalmente, troque senhas temporárias por canal seguro e confirme a política de acesso com a TI.
