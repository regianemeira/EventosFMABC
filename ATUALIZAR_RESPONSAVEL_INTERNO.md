# Atualização: responsável interno vinculado a usuários cadastrados

## O que muda

- O campo **Responsável interno** na triagem e na ficha do evento passa a ser uma lista suspensa alimentada por contas ativas cadastradas em `Equipe e acessos`.
- Uma conta criada pelo administrador aparece na lista assim que a tela é carregada; não precisa cadastrar o responsável manualmente em outro lugar.
- Administradores e usuários com perfil Equipe podem ser escolhidos, desde que a conta esteja ativa.
- Há uma opção **Sem responsável**.
- O servidor valida todas as novas atribuições contra a tabela de usuários ativos. Não é possível enviar um nome ou e-mail arbitrário para atribuição.
- Valores antigos de responsável que não correspondam a uma conta ativa são preservados enquanto ninguém altera esse campo. A tela mostra um aviso e oferece a seleção de uma conta válida para substituir o valor antigo.
- Usuários com perfil **Equipe — triagem e eventos** são direcionados à página `/triagem` após o login, mesmo se o link do login continha um `next` antigo. Administradores seguem para a visão geral ou para a página local originalmente solicitada.

## Instalação local (Windows)

1. Pare o servidor com `Ctrl+C`.
2. Faça uma cópia de segurança de `instance\fmabc_eventos.db` e `.env`.
3. Extraia o patch na pasta que contém `app.py`, preservando a estrutura `templates` e autorizando a substituição dos arquivos incluídos.
4. Reinicie:

```bat
set PORT=5055
python app.py
```

5. Atualize o navegador com `Ctrl+F5`. Em `Equipe e acessos`, cadastre um usuário de teste; depois abra um evento e confira a lista **Responsável interno**.

O patch não inclui nem substitui banco de dados ou `.env`.
