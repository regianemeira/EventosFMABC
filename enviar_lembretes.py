"""Gera os lembretes do dia e envia os e-mails pendentes, sem abrir o navegador.

Uso (na pasta do projeto, com o ambiente virtual ativo):
    python enviar_lembretes.py

Pode ser agendado no Agendador de Tarefas do Windows para rodar todo dia às 7h30.
Lembretes já gerados no dia não se repetem.
"""
import os

os.environ.setdefault("LEMBRETES_AUTOMATICOS", "0")  # não inicia o agendador interno neste processo
os.environ["FMABC_ENVIO_SINCRONO"] = "1"

from app import app, get_db, run_daily_reminders, send_pending_emails, smtp_is_configured  # noqa: E402

with app.app_context():
    resumo = run_daily_reminders(get_db())
    if resumo is None:
        print("Os lembretes de hoje já tinham sido gerados.")
    else:
        print(f"Lembretes gerados: {resumo['tarefas']} de tarefas, {resumo['areas']} para áreas, {resumo['solicitantes']} para solicitantes.")
    if smtp_is_configured():
        envio = send_pending_emails(limit=500)
        print(f"E-mails enviados: {envio['enviados']}; falhas: {envio['falhas']}.")
    else:
        print("SMTP não configurado: os e-mails ficaram na caixa de saída do sistema (menu E-mails e lembretes).")
