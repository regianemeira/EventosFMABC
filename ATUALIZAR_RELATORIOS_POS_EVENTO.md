# Atualização: relatórios anuais, encerramento e avaliação pós-evento

## Instalação na máquina local

1. Pare o servidor com `Ctrl+C` na janela preta.
2. Faça uma cópia de `instance/fmabc_eventos.db` e de `.env`.
3. Extraia o ZIP do patch diretamente dentro da pasta `fmabc_eventos`, onde está `app.py`, mantendo as subpastas `templates` e `static` e aceitando a substituição dos arquivos.
4. Inicie novamente o sistema (no Windows):

```bat
set PORT=5055
python app.py
```

5. Atualize o navegador com `Ctrl+F5`.

Não apague nem substitua a pasta `instance`; o banco existente será mantido. Na próxima inicialização, o sistema cria as novas tabelas de encerramento e avaliação sem excluir dados antigos.

## Como usar

- **Relatórios:** abra `Relatórios de eventos` no menu lateral ou acesse `/relatorios`. Escolha o ano e filtre por status, categoria e setor. O padrão mostra eventos marcados como realizados ou encerrados; selecione todos os status para conferir também solicitações em andamento e canceladas. É possível exportar CSV para abrir no Excel ou imprimir/salvar em PDF pelo navegador.
- **Encerrar um evento:** abra a página do evento, clique em `Finalizar evento`, descreva o que ocorreu e confirme que o evento foi realizado. O registro é usado no relatório anual. O status passa para `Encerrado`.
- **Avaliação do solicitante:** ao salvar o encerramento, o sistema cria um link individual para avaliar a experiência geral, atendimento do Setor de Eventos, comunicação, agilidade e atendimento das necessidades. O solicitante também pode deixar pontos positivos e sugestões.
- **Envio do convite:** sem SMTP configurado, copie o link e envie manualmente. Para e-mail automático, configure SMTP e `APP_BASE_URL` no `.env` com a URL pública da aplicação. Não encaminhe links `localhost`/`127.0.0.1` ao solicitante; eles só funcionam no próprio computador.

## Campos do relatório pós-evento

- Público real presente
- Resumo do que aconteceu (obrigatório)
- Pontos positivos
- Falhas, dificuldades e imprevistos
- Melhorias recomendadas
- Ações de acompanhamento
- Observações finais internas

As notas de avaliação variam de 1 a 5. A pesquisa fica vinculada ao evento e o link permite apenas uma resposta. O relatório anual apresenta as avaliações recebidas e as médias disponíveis.

## Rotas

- Relatório anual: `/relatorios`
- Exportação: `/relatorios/exportar.csv`
- Encerramento: `/eventos/ID/finalizar`
- Avaliação pública: `/avaliacao-evento/TOKEN`

Substitua `ID` e `TOKEN` pelos valores reais gerados no sistema; eles não são valores fixos.
