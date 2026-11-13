# Atualização: remover atalho de login da área azul

## O que muda

A área azul da tela de login passa a exibir somente três atalhos públicos:

- **Solicitar evento** — abre o formulário público (`/solicitar`).
- **Manual de Eventos** — abre a consulta do manual (`/manual`).
- **Consultar evento** — abre a consulta por protocolo e e-mail (`/acompanhar`).

O atalho **Área restrita** foi removido da coluna azul, porque o formulário de login já está disponível na coluna branca à direita. A lista foi reorganizada em uma única coluna para evitar um cartão isolado e manter a apresentação visual equilibrada. A caixa de login e a autenticação não foram alteradas.

## Como atualizar no Windows

1. Faça uma cópia de segurança do projeto e, principalmente, de `instance\fmabc_eventos.db` e `.env`.
2. Pare o servidor com `Ctrl+C`.
3. Extraia o patch na pasta `C:\Users\regiane.meira\Downloads\fmabc_eventos`, preservando a estrutura de pastas e substituindo os arquivos solicitados.
4. Inicie novamente:

```bat
set PORT=5055
python app.py
```

5. Abra `http://127.0.0.1:5055/login` e pressione `Ctrl+F5`.

O patch contém `templates/login.html`, `static/app.css` e este guia. Não altera banco de dados, usuários, senhas nem `.env`.
