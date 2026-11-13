# Relatórios, encerramento e avaliação pós-evento

## Relatórios anuais
- Acesse `Relatórios de eventos` no menu interno (`/relatorios`).
- Selecione o ano e filtre por status, categoria e setor solicitante.
- Por padrão, o relatório mostra eventos marcados como Realizado ou Encerrado. Use “Todos os status no ano” para incluir também eventos cancelados ou ainda em planejamento.
- `Exportar Excel / CSV` baixa um CSV separado por ponto e vírgula, compatível com Excel. `Imprimir / salvar em PDF` usa a janela de impressão do navegador.
- O relatório apresenta público previsto e realizado, relatório pós-evento, avaliações e médias de satisfação.

## Encerramento pós-evento
1. Abra o evento no painel.
2. Na lateral, selecione `Finalizar evento`.
3. Registre o resumo do que aconteceu. Público real, pontos positivos, dificuldades, melhorias, ações de acompanhamento e observações podem ser preenchidos conforme disponíveis.
4. Confirme que o evento foi realizado e salve. O evento passa para o status `Encerrado`.
5. O sistema cria um link individual de avaliação para o solicitante. Se o convite não for enviado automaticamente, copie o link e envie pelo canal institucional.

## Pesquisa para o solicitante
A avaliação pergunta notas de 1 a 5 para a experiência geral, atendimento do Setor de Eventos, comunicação, agilidade e atendimento das necessidades. Há campos opcionais para pontos positivos, melhorias e comentários. Cada link é individual e só permite registrar uma resposta.

## Envio automático por e-mail
- O SMTP precisa estar configurado no arquivo `.env`.
- Configure `APP_BASE_URL` com o endereço público da aplicação (por exemplo, o endereço institucional após publicação).
- Não envie convite com endereço `127.0.0.1` ou `localhost`, pois esses endereços só funcionam no próprio computador.
- Em instalação local sem URL pública, copie o link e teste a pesquisa neste computador; o solicitante só conseguirá acessar quando a aplicação estiver hospedada num endereço acessível.

## Banco de dados
Na primeira inicialização, o sistema cria as tabelas `event_closures` e `event_evaluations` no banco existente. Nenhuma tabela antiga é removida. Faça backup de `instance/fmabc_eventos.db` antes de atualizar.
