"""Ponto de entrada do Sistema de Gestão de Eventos FMABC.

O código fica na pasta `sistema/`:
    core.py         configuração, banco de dados, constantes e funções compartilhadas
    publico.py      formulário público, acompanhamento, login, manual, avaliação
    eventos.py      painel, triagem, eventos, edição, linha do tempo, anexos, agenda
    checklist.py    tarefas, checklist consolidado e modelos de checklist
    orcamento.py    orçamento, cotações e comparativo de custos
    relatorios.py   relatórios anuais e CSV
    comunicacao.py  agenda por área, comunicados e importação de planilha
    admin.py        cadastros de apoio, equipe e espaços
    notificacoes.py e-mails, pedidos de informação, lembretes e calendário (.ics)

Iniciar: python app.py   (ou waitress-serve app:app)
"""
import os

from sistema.core import *  # noqa: F401,F403  (expõe `app` e as funções compartilhadas)
from sistema.publico import *  # noqa: F401,F403
from sistema.eventos import *  # noqa: F401,F403
from sistema.checklist import *  # noqa: F401,F403
from sistema.orcamento import *  # noqa: F401,F403
from sistema.relatorios import *  # noqa: F401,F403
from sistema.comunicacao import *  # noqa: F401,F403
from sistema.admin import *  # noqa: F401,F403
from sistema.notificacoes import *  # noqa: F401,F403

with app.app_context():
    init_db()
    _cleanup_import_previews()

# Lembretes diários automáticos enquanto o sistema estiver ligado (desative com LEMBRETES_AUTOMATICOS=0 no .env).
start_reminder_scheduler()

if __name__ == "__main__":
    app.run(host=os.getenv("HOST", "127.0.0.1"), port=int(os.getenv("PORT", "5000")), debug=os.getenv("DEBUG", "0") == "1")
