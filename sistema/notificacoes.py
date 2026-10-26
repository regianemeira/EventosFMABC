"""Comunicação: resposta do solicitante a pedidos de informação, caixa de saída de e-mails, lembretes e calendários (.ics)."""
from __future__ import annotations

from .core import *  # noqa: F401,F403


@app.route("/responder/<token>", methods=["GET", "POST"])
def answer_info_request(token):
    """Página pública em que o solicitante responde ao pedido de informações e anexa arquivos."""
    if not re.fullmatch(r"[A-Za-z0-9_-]{24,80}", token or ""):
        abort(404)
    db = get_db()
    req = db.execute("""SELECT r.*, e.title, e.protocol, e.start_date, e.end_date, e.start_time, e.end_time, e.venue,
                               e.organizer_name, e.internal_owner, e.status AS event_status
                        FROM info_requests r JOIN events e ON e.id = r.event_id WHERE r.token=?""", (token,)).fetchone()
    if not req:
        abort(404)
    if request.method == "POST" and req["status"] == "aberta":
        limit_key = f"answer:{request.remote_addr}"
        if _too_many_attempts(limit_key, 20):
            flash("Muitos envios em pouco tempo. Aguarde alguns minutos.", "error")
            return render_template("info_answer.html", req=req), 429
        _register_attempt(limit_key)
        answer = (request.form.get("answer") or "").strip()[:5000]
        name = (request.form.get("answered_by") or "").strip()[:120]
        files = [f for f in request.files.getlist("files") if f and f.filename][:5]
        if not answer:
            flash("Escreva sua resposta antes de enviar.", "error")
            return render_template("info_answer.html", req=req), 400
        if not name:
            flash("Informe seu nome.", "error")
            return render_template("info_answer.html", req=req), 400
        saved, problems = [], []
        for upload in files:
            ok, result = store_attachment(db, req["event_id"], upload, "Enviado pelo solicitante",
                                          "Enviado na resposta ao pedido de informações", f"{name} (solicitante)")
            (saved if ok else problems).append(result)
        now = now_iso()
        db.execute("UPDATE info_requests SET status='respondida', answer=?, answered_by=?, answered_at=? WHERE id=?",
                   (answer, name, now, req["id"]))
        if req["event_status"] == "aguardando_informacoes":
            db.execute("UPDATE events SET status='em_triagem', updated_at=? WHERE id=?", (now, req["event_id"]))
        summary = f"Resposta do solicitante ({name}):\n{answer}"
        if saved:
            summary += "\nArquivos enviados: " + ", ".join(saved)
        db.execute("INSERT INTO event_change_log(event_id, changed_at, changed_by, summary, kind) VALUES (?,?,?,?, 'comentario')",
                   (req["event_id"], now, f"{name} (solicitante)", summary[:8000]))
        if req["event_status"] == "aguardando_informacoes":
            db.execute("INSERT INTO event_change_log(event_id, changed_at, changed_by, summary, kind) VALUES (?,?,?,?, 'status')",
                       (req["event_id"], now, "sistema", "Status: Aguardando informações → Em triagem (o solicitante respondeu)"))
        # Avisa a equipe: responsável interno ou, sem responsável, os administradores.
        owner = (req["internal_owner"] or "").strip()
        recipients = [owner] if _valid_email(owner) else [r["email"] for r in db.execute(
            "SELECT email FROM users WHERE role='admin' AND is_active=1").fetchall()]
        link = public_link("event_detail", event_id=req["event_id"])
        body = (f"O solicitante respondeu ao pedido de informações.\n\nEvento: {req['title']} ({req['protocol']})\n"
                f"Pergunta: {req['question']}\n\nResposta de {name}:\n{answer}\n"
                + (f"\nArquivos anexados ao evento: {', '.join(saved)}\n" if saved else "")
                + (f"\nAbrir o evento: {link}\n" if link else "")
                + "\nO status voltou para “Em triagem”.")
        for person in recipients:
            queue_email(db, person, f"Resposta recebida — {req['title']} ({req['protocol']})", body, "resposta_info", req["event_id"])
        db.commit()
        dispatch_emails_async()
        for problem in problems:
            flash(problem + " Os demais dados foram enviados.", "error")
        return redirect(url_for("answer_info_request", token=token))
    return render_template("info_answer.html", req=req)


@app.route("/emails", methods=["GET", "POST"])
@login_required
def email_center():
    """Caixa de saída de e-mails, lembretes automáticos e link do calendário."""
    db = get_db()
    if request.method == "POST":
        action = request.form.get("action", "")
        email_id = request.form.get("email_id", type=int)
        if action == "retry" and email_id:
            db.execute("UPDATE email_outbox SET status='pendente', attempts=0, last_error=NULL WHERE id=? AND status IN ('erro','pendente','cancelado')", (email_id,))
            db.commit()
            if smtp_is_configured():
                result = send_pending_emails()
                flash(f"Envio tentado: {result['enviados']} enviado(s), {result['falhas']} falha(s).", "success" if not result["falhas"] else "error")
            else:
                flash("O e-mail voltou para a fila, mas o SMTP não está configurado. Envie manualmente e marque como enviado.", "warning")
        elif action == "manual" and email_id:
            db.execute("UPDATE email_outbox SET status='manual', sent_at=? WHERE id=? AND status IN ('pendente','erro')", (now_iso(), email_id))
            db.commit()
            flash("Marcado como enviado manualmente.", "success")
        elif action == "cancel" and email_id:
            db.execute("UPDATE email_outbox SET status='cancelado' WHERE id=? AND status IN ('pendente','erro')", (email_id,))
            db.commit()
            flash("E-mail cancelado; ele não será enviado.", "success")
        elif action == "send_all":
            if not smtp_is_configured():
                flash("Configure o SMTP no arquivo .env para enviar automaticamente.", "error")
            else:
                result = send_pending_emails(limit=200)
                flash(f"Envio concluído: {result['enviados']} enviado(s), {result['falhas']} falha(s).", "success" if not result["falhas"] else "error")
        elif action == "run_reminders":
            result = run_daily_reminders(db, force=True)
            dispatch_emails_async()
            flash(f"Lembretes gerados: {result['tarefas']} resumo(s) de tarefas, {result['areas']} para áreas, "
                  f"{result['solicitantes']} para solicitantes. Lembretes já enviados hoje não se repetem.", "success")
        elif action == "new_ics_token":
            db.execute("UPDATE users SET ics_token=? WHERE id=?", (secrets.token_urlsafe(24), session.get("user_id")))
            db.commit()
            flash("Novo link de calendário criado. O link anterior deixou de funcionar.", "success")
        return redirect(url_for("email_center", status=request.args.get("status", "")))

    status_filter = request.args.get("status", "")
    sql = "SELECT o.*, e.title AS event_title FROM email_outbox o LEFT JOIN events e ON e.id=o.event_id"
    params = []
    if status_filter in EMAIL_STATUS_LABELS:
        sql += " WHERE o.status=?"
        params.append(status_filter)
    emails = db.execute(sql + " ORDER BY o.id DESC LIMIT 200", params).fetchall()
    counts = {r["status"]: r["n"] for r in db.execute("SELECT status, COUNT(*) n FROM email_outbox GROUP BY status").fetchall()}
    user = db.execute("SELECT ics_token FROM users WHERE id=?", (session.get("user_id"),)).fetchone()
    token = user["ics_token"] if user else None
    if not token:
        token = secrets.token_urlsafe(24)
        db.execute("UPDATE users SET ics_token=? WHERE id=?", (token, session.get("user_id")))
        db.commit()
    feed_url = (link_base_url() or request.url_root.rstrip("/")) + url_for("calendar_feed", token=token)
    last_summary = _setting(db, "lembretes_ultimo_resumo")
    return render_template(
        "emails.html", emails=emails, counts=counts, status_filter=status_filter,
        email_status_labels=EMAIL_STATUS_LABELS, email_kind_labels=EMAIL_KIND_LABELS,
        smtp_configured=smtp_is_configured(), base_url_configured=bool(link_base_url()),
        last_run=_setting(db, "lembretes_ultima_execucao"), last_summary=json.loads(last_summary) if last_summary else None,
        auto_reminders=os.getenv("LEMBRETES_AUTOMATICOS", "1") != "0", feed_url=feed_url,
    )


# ---------------------------------------------------------------------------
# Calendário (.ics)
# ---------------------------------------------------------------------------

def _ics_escape(text) -> str:
    return (str(text or "").replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,")
            .replace("\r\n", "\\n").replace("\n", "\\n"))


def _ics_fold(line: str) -> str:
    """Quebra linhas longas (máx. 75 octetos) como exige o padrão iCalendar."""
    out, current = [], ""
    for char in line:
        if len((current + char).encode("utf-8")) > 74:
            out.append(current)
            current = " " + char
        else:
            current += char
    out.append(current)
    return "\r\n".join(out)


def _ics_event(event) -> list[str]:
    start_day, end_day = _event_date_bounds(event)
    if not start_day:
        return []
    end_day = end_day or start_day
    start_min, end_min = _time_interval_from_values(event["start_time"], event["end_time"])
    lines = ["BEGIN:VEVENT", f"UID:evento-{event['id']}@fmabc-eventos",
             f"DTSTAMP:{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}"]
    if start_min is None:
        lines += [f"DTSTART;VALUE=DATE:{start_day.strftime('%Y%m%d')}",
                  f"DTEND;VALUE=DATE:{(end_day + timedelta(days=1)).strftime('%Y%m%d')}"]
    else:
        end_min = end_min if end_min is not None else min(start_min + 60, 23 * 60 + 59)
        lines += [f"DTSTART;TZID=America/Sao_Paulo:{start_day.strftime('%Y%m%d')}T{start_min // 60:02d}{start_min % 60:02d}00",
                  f"DTEND;TZID=America/Sao_Paulo:{end_day.strftime('%Y%m%d')}T{end_min // 60:02d}{end_min % 60:02d}00"]
    status = STATUS_LABELS.get(event["status"], event["status"])
    description = f"Protocolo {event['protocol']} · {status}\nSolicitante: {event['organizer_name']}\nSetor: {event['department']}"
    link = public_link("event_detail", event_id=event["id"])
    if link:
        description += f"\n{link}"
    lines += [f"SUMMARY:{_ics_escape(event['title'])}", f"LOCATION:{_ics_escape(event['venue'] or '')}",
              f"DESCRIPTION:{_ics_escape(description)}",
              "STATUS:" + ("TENTATIVE" if event["status"] in {"recebido", "em_triagem", "aguardando_informacoes"} else "CONFIRMED"),
              "END:VEVENT"]
    return lines


ICS_TIMEZONE = ["BEGIN:VTIMEZONE", "TZID:America/Sao_Paulo", "BEGIN:STANDARD", "DTSTART:19700101T000000",
                "TZOFFSETFROM:-0300", "TZOFFSETTO:-0300", "TZNAME:-03", "END:STANDARD", "END:VTIMEZONE"]


def _ics_response(events, name: str, filename: str) -> Response:
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//FMABC//Gestao de Eventos//PT-BR", "CALSCALE:GREGORIAN",
             "METHOD:PUBLISH", f"X-WR-CALNAME:{_ics_escape(name)}", "X-WR-TIMEZONE:America/Sao_Paulo", *ICS_TIMEZONE]
    for event in events:
        lines += _ics_event(event)
    lines.append("END:VCALENDAR")
    body = "\r\n".join(_ics_fold(line) for line in lines) + "\r\n"
    return Response(body, content_type="text/calendar; charset=utf-8",
                    headers={"Content-Disposition": f'inline; filename="{filename}"', "Cache-Control": "no-store"})


@app.get("/agenda.ics")
def calendar_feed():
    """Calendário para assinar no Outlook/Google/celular; o link pessoal funciona sem login."""
    token = request.args.get("token", "")
    if not re.fullmatch(r"[A-Za-z0-9_-]{20,80}", token):
        abort(404)
    db = get_db()
    user = db.execute("SELECT id FROM users WHERE ics_token=? AND is_active=1", (token,)).fetchone()
    if not user:
        abort(404)
    since = (date.today() - timedelta(days=60)).isoformat()
    until = (date.today() + timedelta(days=400)).isoformat()
    events = db.execute("""SELECT * FROM events WHERE status <> 'cancelado' AND start_date <= ?
                           AND COALESCE(NULLIF(end_date,''), start_date) >= ? ORDER BY start_date""", (until, since)).fetchall()
    return _ics_response(events, "Eventos FMABC", "eventos_fmabc.ics")


@app.get("/eventos/<int:event_id>/evento.ics")
@login_required
def event_ics(event_id):
    event = get_event_or_404(event_id)
    return _ics_response([event], event["title"], f"evento_{event['protocol']}.ics")


__all__ = [name for name in dict(globals()) if not name.startswith("__")]
