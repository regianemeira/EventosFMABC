# Atualização: senha mínima de 6 caracteres

## Alteração

A validação de senha no cadastro de usuários e na redefinição administrativa agora aceita senhas com no mínimo 6 caracteres. A mesma regra foi aplicada ao script `redefinir_senha_admin.py` para manter a recuperação da conta consistente.

- Cadastro de novo usuário: `minlength="6"` no formulário e validação no servidor. A criação da conta administrativa inicial também valida `ADMIN_PASSWORD` com mínimo de 6 caracteres quando essa variável é preenchida.
- Redefinição de senha: `minlength="6"` nos campos de senha e confirmação, com validação no servidor.
- A senha continua sendo armazenada como hash; não é salva em texto puro.

## Como aplicar no Windows

1. Na janela em que o FMABC Eventos está rodando, pressione `Ctrl+C`.
2. Faça uma cópia de segurança de `instance\fmabc_eventos.db` e do arquivo `.env`.
3. Extraia este patch na pasta em que está o `app.py`, mantendo a estrutura dos arquivos e autorizando a substituição.
4. Reinicie:

```bat
set PORT=5055
python app.py
```

5. Atualize a página no navegador com `Ctrl+F5`.

Esta atualização não altera o banco de dados nem as senhas já cadastradas. Ela muda apenas o mínimo aceito para novas senhas e redefinições futuras. Se houver uma senha antiga com mais de 6 caracteres, ela continuará funcionando normalmente.

## Observação de segurança

Seis caracteres é o mínimo solicitado para este ambiente. Para publicação institucional, recomenda-se validar a política de senhas com a TI da FMABC e aplicar controles complementares de acesso e proteção.
