ATUALIZAÇÃO — VISÃO GERAL FMABC EVENTOS

Alterações desta revisão:
- Mantém os três eventos mais próximos em cartões azuis, seguindo o azul institucional solicitado.
- Move a faixa de indicadores para imediatamente abaixo dos três eventos em destaque.
- Os quatro indicadores passam a ser clicáveis e abrem o conteúdo em nova aba: solicitações/eventos para os três primeiros e agenda institucional para Agenda próxima.
- Não altera banco de dados nem app.py.

Instalação:
1. Faça backup do projeto.
2. Pare o servidor Flask.
3. Substitua templates/dashboard.html e static/app.css pelos arquivos deste pacote.
4. Reinicie e atualize o navegador com Ctrl+F5.

Observação: os indicadores “Precisam de triagem” e “Em organização” abrem a lista geral de solicitações porque a base do template não fornece, neste pacote, URLs de filtros específicos para esses estados.
