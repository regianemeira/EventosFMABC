"""Painel, triagem, lista e detalhe do evento, edição, status, encerramento, linha do tempo, anexos, roteiro, ocorrências e agenda."""
from __future__ import annotations

from .core import *  # noqa: F401,F403



def _critical_task_rows(limit=12):
    today = date.today().isoformat()
    soon = (date.today() + timedelta(days=3)).isoformat()
    rows = get_db().execute("""SELECT t.*, e.title event_title, e.start_date event_date, e.id parent_event_id
        FROM tasks t JOIN events e ON e.id=t.event_id
        WHERE t.status NOT IN ('concluida','nao_se_aplica') AND t.due_date IS NOT NULL AND t.due_date<>'' AND t.due_date<=?
          AND e.status NOT IN ('cancelado','encerrado','realizado')
        ORDER BY t.due_date, e.start_date LIMIT ?""", (soon, limit)).fetchall()
    out=[]
    for row in rows:
        item=dict(row); item["overdue"] = item["due_date"] < today
        item["days_until_due"] = (date.fromisoformat(item["due_date"])-date.today()).days
        out.append(item)
    return out


def _pending_department_confirmations(limit=12):
    return get_db().execute("""SELECT u.*, e.title event_title, e.start_date event_date, e.id parent_event_id,
        d.name department_name, d.recipient_email FROM event_department_updates u
        JOIN events e ON e.id=u.event_id JOIN departments d ON d.id=u.department_id
        WHERE u.involvement='acao' AND (u.task_status<>'concluida'
           OR u.response_status IN ('aguardando','recebido','precisa_alinhar','nao_podera_atender'))
        AND u.response_token IS NOT NULL AND e.start_date>=? AND e.status IN ('aprovado','em_planejamento')
        ORDER BY CASE WHEN u.task_status='bloqueada' THEN 0 WHEN u.response_status='nao_podera_atender' THEN 1
                      WHEN u.response_status IN ('aguardando','recebido','precisa_alinhar') THEN 2 ELSE 3 END,
        COALESCE(u.due_date,e.start_date),e.start_date,d.name LIMIT ?""", (date.today().isoformat(), limit)).fetchall()


@app.get("/agenda")
@login_required
def institutional_calendar():
    today = date.today()
    try:
        year = int(request.args.get("year", str(today.year))); month = int(request.args.get("month", str(today.month)))
        if not 2000 <= year <= 2100 or not 1 <= month <= 12: raise ValueError
    except ValueError:
        year, month = today.year, today.month
    month_start = date(year, month, 1)
    month_end = date(year + (month == 12), 1 if month == 12 else month + 1, 1) - timedelta(days=1)
    events = [dict(r) for r in get_db().execute("""SELECT * FROM events WHERE status<>'cancelado'
        AND start_date<=? AND COALESCE(NULLIF(end_date,''),start_date)>=? ORDER BY start_date,start_time,title""", (month_end.isoformat(), month_start.isoformat())).fetchall()]
    by_day={}
    for item in events:
        start, end = _event_date_bounds(item)
        if not start or not end: continue
        cursor=max(start,month_start); last=min(end,month_end)
        while cursor<=last:
            by_day.setdefault(cursor.isoformat(), []).append(item); cursor += timedelta(days=1)
    weeks=pycalendar.Calendar(firstweekday=0).monthdatescalendar(year,month)
    conflicts=_find_schedule_conflicts(get_db().execute("SELECT * FROM events WHERE status<>'cancelado' AND start_date<=? AND COALESCE(NULLIF(end_date,''),start_date)>=? ORDER BY start_date,start_time", ((month_end+timedelta(days=1)).isoformat(),(month_start-timedelta(days=1)).isoformat())).fetchall())
    month_blocks = get_db().execute("""SELECT b.*, v.name AS venue_name FROM venue_blocks b JOIN venues v ON v.id=b.venue_id
        WHERE b.start_date<=? AND b.end_date>=? ORDER BY b.start_date, v.name""", (month_end.isoformat(), month_start.isoformat())).fetchall()
    return render_template("agenda.html", month_blocks=month_blocks, year=year, month=month, today=today, years=list(range(max(2024,year-2),min(2100,year+5)+1)), weeks=weeks, events_by_day=by_day, conflicts=conflicts, critical_tasks=_critical_task_rows(10), pending_confirmations=_pending_department_confirmations(10), month_names=["Janeiro","Fevereiro","Março","Abril","Maio","Junho","Julho","Agosto","Setembro","Outubro","Novembro","Dezembro"])


@app.route("/eventos/<int:event_id>/roteiro", methods=["GET","POST"])
@login_required
def event_run_sheet(event_id):
    event=get_event_or_404(event_id); db=get_db()
    if request.method=="POST":
        action=request.form.get("action","add"); item_id=request.form.get("item_id",type=int)
        if action=="delete":
            db.execute("DELETE FROM event_program_items WHERE id=? AND event_id=?",(item_id,event_id)); db.commit(); flash("Atividade removida do roteiro.","success")
            return redirect(url_for("event_run_sheet",event_id=event_id))
        start=(request.form.get("start_time") or "").strip(); end=(request.form.get("end_time") or "").strip() or None; activity=(request.form.get("activity") or "").strip()
        if not re.fullmatch(r"\d{2}:\d{2}",start) or (end and not re.fullmatch(r"\d{2}:\d{2}",end)) or not activity:
            flash("Informe a atividade e horários válidos (HH:MM).","error"); return redirect(url_for("event_run_sheet",event_id=event_id))
        if end and _time_to_minutes(end)<=_time_to_minutes(start):
            flash("O horário de término deve ser posterior ao início.","error"); return redirect(url_for("event_run_sheet",event_id=event_id))
        vals=(start,end,activity[:240],(request.form.get("location") or "").strip()[:180] or None,(request.form.get("responsible") or "").strip()[:180] or None,(request.form.get("notes") or "").strip()[:1500] or None,now_iso())
        if action=="edit" and item_id:
            db.execute("UPDATE event_program_items SET start_time=?,end_time=?,activity=?,location=?,responsible=?,notes=?,updated_at=? WHERE id=? AND event_id=?",vals+(item_id,event_id)); flash("Atividade do roteiro atualizada.","success")
        else:
            order=db.execute("SELECT COALESCE(MAX(sort_order),0)+1 FROM event_program_items WHERE event_id=?",(event_id,)).fetchone()[0]
            db.execute("INSERT INTO event_program_items(event_id,start_time,end_time,activity,location,responsible,notes,sort_order,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)",(event_id,start,end,activity[:240],vals[3],vals[4],vals[5],order,now_iso(),now_iso())); flash("Atividade adicionada ao roteiro operacional.","success")
        db.commit(); return redirect(url_for("event_run_sheet",event_id=event_id))
    items=db.execute("SELECT * FROM event_program_items WHERE event_id=? ORDER BY start_time,sort_order,id",(event_id,)).fetchall()
    return render_template("event_run_sheet.html",event=event,items=items)


@app.route("/eventos/<int:event_id>/ocorrencias", methods=["GET","POST"])
@login_required
def event_incidents(event_id):
    event=get_event_or_404(event_id); db=get_db()
    categories=["Infraestrutura","Tecnologia / audiovisual","Fornecedor","Programação","Público / credenciamento","Comunicação","Acessibilidade / segurança","Outro"]
    statuses={"aberta":"Aberta","em_tratamento":"Em tratamento","resolvida":"Resolvida"}
    if request.method=="POST":
        action=request.form.get("action","add"); incident_id=request.form.get("incident_id",type=int)
        if action=="delete":
            db.execute("DELETE FROM event_incidents WHERE id=? AND event_id=?",(incident_id,event_id)); db.commit(); flash("Ocorrência removida do evento.","success"); return redirect(url_for("event_incidents",event_id=event_id))
        title=(request.form.get("title") or "").strip()
        if not title: flash("Informe um título curto para a ocorrência.","error"); return redirect(url_for("event_incidents",event_id=event_id))
        when=(request.form.get("incident_date") or "").strip() or None
        if when and not re.fullmatch(r"\d{4}-\d{2}-\d{2}(?:T\d{2}:\d{2})?",when): flash("Informe uma data/hora válida.","error"); return redirect(url_for("event_incidents",event_id=event_id))
        category=request.form.get("category","Outro"); category=category if category in categories else "Outro"; status=request.form.get("status","aberta"); status=status if status in statuses else "aberta"
        impact=(request.form.get("impact") or "").strip()[:2000] or None; resolution=(request.form.get("resolution") or "").strip()[:2000] or None; preventive=(request.form.get("preventive_action") or "").strip()[:2000] or None; responsible=(request.form.get("responsible") or "").strip()[:180] or None; now=now_iso(); user=session.get("user_email")
        if action=="edit" and incident_id:
            db.execute("UPDATE event_incidents SET incident_date=?,category=?,title=?,impact=?,resolution=?,preventive_action=?,responsible=?,status=?,recorded_by=?,updated_at=? WHERE id=? AND event_id=?",(when,category,title[:240],impact,resolution,preventive,responsible,status,user,now,incident_id,event_id)); flash("Ocorrência atualizada.","success")
        else:
            db.execute("INSERT INTO event_incidents(event_id,incident_date,category,title,impact,resolution,preventive_action,responsible,status,recorded_by,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",(event_id,when,category,title[:240],impact,resolution,preventive,responsible,status,user,now,now)); flash("Ocorrência registrada no evento.","success")
        db.commit(); return redirect(url_for("event_incidents",event_id=event_id))
    incidents=db.execute("SELECT * FROM event_incidents WHERE event_id=? ORDER BY CASE status WHEN 'aberta' THEN 1 WHEN 'em_tratamento' THEN 2 ELSE 3 END, incident_date DESC,id DESC",(event_id,)).fetchall()
    counts={key:sum(1 for item in incidents if item["status"]==key) for key in statuses}
    return render_template("event_incidents.html",event=event,incidents=incidents,categories=categories,incident_statuses=statuses,counts=counts)


@app.get("/")
@login_required
def dashboard():
    db = get_db()
    counts = {r["status"]: r["total"] for r in db.execute("SELECT status, COUNT(*) total FROM events GROUP BY status").fetchall()}
    total = sum(counts.values())
    pending = counts.get("recebido", 0) + counts.get("em_triagem", 0) + counts.get("aguardando_informacoes", 0)
    active = counts.get("aprovado", 0) + counts.get("em_planejamento", 0)
    upcoming = db.execute(
        "SELECT * FROM events WHERE start_date >= ? AND status NOT IN ('cancelado', 'realizado', 'encerrado') ORDER BY start_date LIMIT 6",
        (date.today().isoformat(),),
    ).fetchall()
    recent = db.execute("SELECT * FROM events ORDER BY created_at DESC LIMIT 7").fetchall()
    future_events = db.execute("SELECT * FROM events WHERE status NOT IN ('cancelado','realizado','encerrado') AND start_date >= ? ORDER BY start_date LIMIT 100", (date.today().isoformat(),)).fetchall()
    schedule_conflicts = _find_schedule_conflicts(future_events)
    critical_tasks = _critical_task_rows(8)
    pending_confirmations = _pending_department_confirmations(8)
    alert_count = len(schedule_conflicts) + len(critical_tasks) + len(pending_confirmations)
    return render_template("dashboard.html", counts=counts, total=total, pending=pending, active=active, upcoming=upcoming, recent=recent,
                           schedule_conflicts=schedule_conflicts, critical_tasks=critical_tasks,
                           pending_confirmations=pending_confirmations, alert_count=alert_count)


def _resolve_internal_owner(db, event, form):
    """Resolve an internal owner only to an active registered account.

    Existing free-text owner values are preserved unless the select was changed,
    so updating status/notes does not silently erase legacy assignments. New
    assignments must always point to an active user account.
    """
    selected = (form.get("internal_owner") or "").strip()
    owner_changed = form.get("owner_changed") == "1"

    if selected == "__none__":
        return None, None
    if selected:
        user = db.execute(
            "SELECT email FROM users WHERE lower(email) = lower(?) AND is_active = 1",
            (selected,),
        ).fetchone()
        if not user:
            return None, "O responsável interno deve ser uma conta ativa cadastrada no sistema."
        return user["email"], None
    if owner_changed:
        return None, "Selecione uma conta ativa ou escolha 'Sem responsável'."
    return event["internal_owner"], None


def _log_triage_changes(db, event, status, priority, owner) -> None:
    changes = []
    if event["status"] != status:
        changes.append(f"Status: {STATUS_LABELS.get(event['status'], event['status'])} → {STATUS_LABELS.get(status, status)}")
    if (event["priority"] or "Normal") != priority:
        changes.append(f"Prioridade: {event['priority'] or 'Normal'} → {priority}")
    if (event["internal_owner"] or "") != (owner or ""):
        changes.append(f"Responsável interno: {event['internal_owner'] or 'sem responsável'} → {owner or 'sem responsável'}")
    if changes:
        log_event(db, event["id"], "status", "\n".join(changes))


def _active_internal_users(db):
    """Accounts that may be assigned as an internal event owner."""
    return db.execute(
        "SELECT id, email, role FROM users WHERE is_active = 1 ORDER BY email COLLATE NOCASE"
    ).fetchall()


EVENT_LIST_TABS = [
    ("triar", "Para triar", ("recebido", "em_triagem")),
    ("aguardando", "Aguardando informações", ("aguardando_informacoes",)),
    ("planejamento", "Em planejamento", ("aprovado", "em_planejamento")),
    ("finalizados", "Realizados e cancelados", ("realizado", "encerrado", "cancelado")),
    ("todos", "Todos", None),
]


@app.route("/triagem", methods=["GET", "POST"])
@login_required
def triage_queue():
    """A Triagem agora faz parte de Eventos (aba “Para triar”). Mantido para links e favoritos antigos."""
    return redirect(url_for("events_list", aba="triar", q=request.args.get("q") or None))


@app.get("/eventos")
@login_required
def events_list():
    """Lista única de solicitações e eventos, com abas por situação e triagem rápida na própria lista."""
    db = get_db()
    search = (request.args.get("q") or "").strip()[:160]
    tab = request.args.get("aba", "")
    legacy_status = request.args.get("status", "")  # links antigos: ?status=aprovado
    tabs_by_key = {key: (label, statuses) for key, label, statuses in EVENT_LIST_TABS}
    if tab not in tabs_by_key:
        tab = "todos" if legacy_status in STATUS_LABELS else "triar"
    counts_raw = {r["status"]: r["n"] for r in db.execute("SELECT status, COUNT(*) n FROM events GROUP BY status").fetchall()}
    tabs = []
    for key, label, statuses in EVENT_LIST_TABS:
        count = sum(counts_raw.values()) if statuses is None else sum(counts_raw.get(st, 0) for st in statuses)
        tabs.append({"key": key, "label": label, "count": count})
    sql = "SELECT * FROM events WHERE 1=1"
    params = []
    statuses = tabs_by_key[tab][1]
    if legacy_status in STATUS_LABELS and tab == "todos":
        sql += " AND status = ?"
        params.append(legacy_status)
    elif statuses:
        sql += f" AND status IN ({','.join('?' for _ in statuses)})"
        params.extend(statuses)
    if search:
        like = f"%{search}%"
        sql += " AND (title LIKE ? OR protocol LIKE ? OR department LIKE ? OR organizer_name LIKE ? OR venue LIKE ?)"
        params.extend([like, like, like, like, like])
    if tab == "finalizados":
        sql += " ORDER BY start_date DESC, id DESC"
    else:
        sql += (" ORDER BY CASE status WHEN 'recebido' THEN 1 WHEN 'em_triagem' THEN 2 WHEN 'aguardando_informacoes' THEN 3"
                " WHEN 'aprovado' THEN 4 WHEN 'em_planejamento' THEN 5 ELSE 6 END, start_date ASC, id DESC")
    events = db.execute(sql, params).fetchall()
    open_requests = {r["event_id"]: r for r in db.execute("SELECT * FROM info_requests WHERE status='aberta'").fetchall()}
    closed_ids = {r["event_id"] for r in db.execute("SELECT event_id FROM event_closures").fetchall()}
    return render_template("events.html", events=events, tabs=tabs, tab=tab, search=search,
                           legacy_status=legacy_status if tab == "todos" else "", active_users=_active_internal_users(db),
                           open_requests=open_requests, closed_ids=closed_ids, today=date.today().isoformat())


@app.get("/eventos/<int:event_id>")
@login_required
def event_detail(event_id):
    event = get_event_or_404(event_id)
    tasks = get_db().execute("SELECT * FROM tasks WHERE event_id = ? ORDER BY sort_order, id", (event_id,)).fetchall()
    completed = sum(1 for task in tasks if task["status"] in TASK_DONE_STATUSES)
    progress = round((completed / len(tasks)) * 100) if tasks else 0
    db = get_db()
    closure = db.execute("SELECT * FROM event_closures WHERE event_id = ?", (event_id,)).fetchone()
    evaluation = db.execute("SELECT * FROM event_evaluations WHERE event_id = ?", (event_id,)).fetchone()
    event_start, event_end = _event_date_bounds(event)
    event_start = event_start or date.today()
    event_end = event_end or event_start
    date_from = (event_start - timedelta(days=45)).isoformat()
    date_to = (event_end + timedelta(days=45)).isoformat()
    conflict_pool = db.execute("SELECT * FROM events WHERE status<>'cancelado' AND start_date<=? AND COALESCE(NULLIF(end_date,''),start_date)>=? ORDER BY start_date,start_time", (date_to,date_from)).fetchall()
    schedule_conflicts = [c for c in _find_schedule_conflicts(conflict_pool) if event_id in {c["event_a_id"],c["event_b_id"]}]
    program_count = db.execute("SELECT COUNT(*) FROM event_program_items WHERE event_id=?",(event_id,)).fetchone()[0]
    incident_count = db.execute("SELECT COUNT(*) FROM event_incidents WHERE event_id=?",(event_id,)).fetchone()[0]
    open_incident_count = db.execute("SELECT COUNT(*) FROM event_incidents WHERE event_id=? AND status<>'resolvida'",(event_id,)).fetchone()[0]
    task_fields = {
        template_id: [dict(field, options=field["options_list"]) for field in fields]
        for template_id, fields in _task_fields_by_template(db, {t["template_id"] for t in tasks}).items()
    }
    field_values = {}
    if tasks:
        for value in db.execute(
            f"SELECT task_id, field_id, value FROM task_field_values WHERE task_id IN ({','.join('?' for _ in tasks)})",
            [t["id"] for t in tasks],
        ).fetchall():
            field_values.setdefault(value["task_id"], {})[value["field_id"]] = value["value"] or ""
    budget = db.execute("SELECT COALESCE(SUM(estimated_amount),0) estimated,COALESCE(SUM(actual_amount),0) actual FROM event_budget_items WHERE event_id=? AND status<>'cancelado'",(event_id,)).fetchone()
    return render_template(
        "event_detail.html", event=event, tasks=tasks, completed=completed, progress=progress,
        event_support=event_support(event), event_modes=event_modes(event),
        event_venues=event_venues(event), event_items=event_requested_items(event),
        task_statuses=TASK_STATUSES, closure=closure, evaluation=evaluation,
        schedule_conflicts=schedule_conflicts, program_count=program_count, incident_count=incident_count,
        open_incident_count=open_incident_count, budget_estimated=budget["estimated"], budget_actual=budget["actual"],
        active_users=_active_internal_users(db),
        capacity_warning=_venue_capacity_warning(event_venues(event), event["expected_attendees"]),
        timeline=_event_timeline(db, event),
        checklist_counts=checklist_counts(db, event, session.get("user_email")),
        next_tasks=_next_tasks(db, event),
        open_info_request=db.execute("SELECT * FROM info_requests WHERE event_id=? AND status='aberta' ORDER BY id DESC LIMIT 1", (event_id,)).fetchone(),
        attachments=db.execute("SELECT * FROM event_attachments WHERE event_id=? ORDER BY uploaded_at DESC, id DESC", (event_id,)).fetchall(),
        attachment_categories=ATTACHMENT_CATEGORIES,
        available_task_templates=db.execute("SELECT * FROM task_templates WHERE active=1 ORDER BY category, sort_order, title").fetchall(),
        existing_task_keys={(str(t["title"]).strip().casefold(), str(t["category"] or "").strip().casefold()) for t in tasks},
        task_fields_by_template=task_fields,
        task_field_values=field_values,
    )


def _next_tasks(db, event, limit: int = 4) -> list[dict]:
    periods = checklist_periods(event)
    rows = db.execute("""SELECT * FROM tasks WHERE event_id=? AND status NOT IN ('concluida','nao_se_aplica')
                         ORDER BY CASE WHEN due_date IS NULL OR due_date='' THEN 1 ELSE 0 END, due_date, sort_order LIMIT ?""",
                      (event["id"], limit)).fetchall()
    return [dict(row, **task_view(row, periods)) for row in rows]


def _event_timeline(db, event) -> list[dict]:
    items = [dict(row) for row in db.execute(
        "SELECT * FROM event_change_log WHERE event_id=? ORDER BY changed_at DESC, id DESC LIMIT 60", (event["id"],)).fetchall()]
    items.append({"id": 0, "kind": "criacao", "changed_at": event["created_at"], "changed_by": event["organizer_name"],
                  "summary": f"Solicitação registrada (protocolo {event['protocol']})."})
    for item in items:
        item["kind_label"] = TIMELINE_KINDS.get(item.get("kind") or "edicao", "Registro")
    return items


@app.post("/eventos/<int:event_id>/comentarios")
@login_required
def add_event_comment(event_id):
    get_event_or_404(event_id)
    text = (request.form.get("comment") or "").strip()
    if not text:
        flash("Escreva o comentário antes de salvar.", "error")
    else:
        db = get_db()
        log_event(db, event_id, "comentario", text[:4000])
        db.execute("UPDATE events SET updated_at=? WHERE id=?", (now_iso(), event_id))
        db.commit()
        flash("Comentário registrado na linha do tempo.", "success")
    return redirect(url_for("event_detail", event_id=event_id) + "#linha-do-tempo")


@app.post("/eventos/<int:event_id>/anexos")
@login_required
def upload_event_attachment(event_id):
    get_event_or_404(event_id)
    back = redirect(url_for("event_detail", event_id=event_id) + "#anexos")
    upload = request.files.get("attachment")
    if not upload or not upload.filename:
        flash("Selecione um arquivo para anexar.", "error")
        return back
    db = get_db()
    ok, result = store_attachment(db, event_id, upload, request.form.get("category", "Outro"),
                                  request.form.get("description"), session.get("user_email"))
    if not ok:
        flash(result, "error")
        return back
    log_event(db, event_id, "anexo", f"Arquivo anexado: {result}.")
    db.commit()
    flash("Arquivo anexado ao evento.", "success")
    return back


@app.get("/eventos/<int:event_id>/anexos/<int:attachment_id>")
@login_required
def download_event_attachment(event_id, attachment_id):
    row = get_db().execute("SELECT * FROM event_attachments WHERE id=? AND event_id=?", (attachment_id, event_id)).fetchone()
    if not row:
        abort(404)
    path = ATTACHMENT_DIR / str(event_id) / row["stored_name"]
    if not path.is_file():
        abort(404)
    return send_file(path, as_attachment=True, download_name=row["original_name"])


@app.post("/eventos/<int:event_id>/anexos/<int:attachment_id>/excluir")
@login_required
def delete_event_attachment(event_id, attachment_id):
    db = get_db()
    row = db.execute("SELECT * FROM event_attachments WHERE id=? AND event_id=?", (attachment_id, event_id)).fetchone()
    if row:
        (ATTACHMENT_DIR / str(event_id) / row["stored_name"]).unlink(missing_ok=True)
        db.execute("DELETE FROM event_attachments WHERE id=?", (attachment_id,))
        log_event(db, event_id, "anexo", f"Arquivo removido: {row['original_name']}.")
        db.commit()
        flash("Anexo removido.", "success")
    return redirect(url_for("event_detail", event_id=event_id) + "#anexos")


def _time_option_for(value, position=0):
    """Map stored free-text time (e.g. '7h às 17h') to a 30-minute select value when possible."""
    values = _time_values_to_minutes(value)
    if len(values) <= position:
        return ""
    minutes = values[position]
    candidate = f"{minutes // 60:02d}h{minutes % 60:02d}"
    return candidate if candidate in TIME_OPTION_VALUES else ""


def _event_edit_defaults(event) -> dict:
    venues = [v for v in event_venues(event)]
    allowed = venue_options()
    # Rótulos antigos (ex.: antes de uma mudança de capacidade) são trazidos para o rótulo atual do cadastro.
    by_key = {_normalize_venue_key(label): label for label in allowed if label not in {"Outro"}}
    known, unknown = [], []
    for v in venues:
        if v == "Outro":
            continue
        current = v if v in allowed else by_key.get(_normalize_venue_key(v))
        (known if current else unknown).append(current or v)
    venue_other = event["venue_other"] or "; ".join(unknown)
    if venue_other and "Outro" not in known:
        known.append("Outro")
    start_time = _time_option_for(event["start_time"], 0)
    end_time = _time_option_for(event["end_time"], 0) or _time_option_for(event["start_time"], 1)
    return {
        "title": event["title"], "department": event["department"], "organizer_name": event["organizer_name"],
        "organizer_email": event["organizer_email"], "organizer_phone": event["organizer_phone"],
        "contact_email": event["contact_email"] or "", "event_category": event["event_type"],
        "event_category_other": event["event_type_other"] or "", "start_date": event["start_date"],
        "end_date": event["end_date"] or event["start_date"], "start_time": start_time, "end_time": end_time,
        "original_time": " – ".join(x for x in [event["start_time"], event["end_time"]] if x),
        "venues": known, "venue_other": venue_other, "event_modes": event_modes(event),
        "expected_attendees": event["expected_attendees"], "audience": event["audience"] or "",
        "description": event["description"] or "", "authorized_by": event["authorized_by"] or "",
        "cost_center": event["cost_center"] or "", "additional_info": event["additional_info"] or "",
    }


@app.route("/eventos/<int:event_id>/editar", methods=["GET", "POST"])
@login_required
def edit_event(event_id):
    """Internal edit of the event data, with conflict check, change history and optional task re-dating."""
    event = get_event_or_404(event_id)
    db = get_db()
    history = db.execute("SELECT * FROM event_change_log WHERE event_id=? AND kind='edicao' ORDER BY changed_at DESC, id DESC LIMIT 30", (event_id,)).fetchall()
    if request.method == "GET":
        return render_template("event_edit.html", event=event, form=_event_edit_defaults(event), history=history, conflicts=None)

    form = request.form
    values = {
        "form": {k: form.get(k, "").strip() for k in [
            "title", "department", "organizer_name", "organizer_email", "organizer_phone", "contact_email",
            "event_category", "event_category_other", "start_date", "end_date", "start_time", "end_time",
            "venue_other", "expected_attendees", "audience", "description", "authorized_by", "cost_center", "additional_info"]},
    }
    data = values["form"]
    allowed_venues = set(venue_options())
    data["venues"] = [v for v in form.getlist("venues") if v in allowed_venues]
    data["event_modes"] = [m for m in form.getlist("event_modes") if m in FORMATS]
    data["original_time"] = " – ".join(x for x in [event["start_time"], event["end_time"]] if x)

    def fail(message, conflicts=None):
        flash(message, "error" if not conflicts else "warning")
        return render_template("event_edit.html", event=event, form=data, history=history, conflicts=conflicts), 400

    for field in ["title", "department", "organizer_name", "start_date", "start_time", "end_time", "description"]:
        if not data[field]:
            return fail("Preencha nome, setor, responsável, data, horários e objetivo do evento.")
    start_date = normalize_date(data["start_date"])
    if not start_date:
        return fail("Informe uma data de início válida.")
    end_date, end_error = _validate_end_date(start_date, data["end_date"])
    if end_error:
        return fail(end_error)
    if data["start_time"] not in TIME_OPTION_VALUES or data["end_time"] not in TIME_OPTION_VALUES:
        return fail("Selecione os horários de início e término nas opções disponíveis.")
    if _time_to_minutes(data["end_time"]) <= _time_to_minutes(data["start_time"]):
        return fail("O horário de término precisa ser posterior ao de início (em eventos de vários dias, vale para cada dia).")
    if data["event_category"] not in EVENT_TYPES:
        return fail("Selecione a categoria do evento.")
    if data["event_category"] == "Outro" and not data["event_category_other"]:
        return fail("Especifique a categoria do evento.")
    if not data["venues"]:
        return fail("Selecione pelo menos um local.")
    if "Outro" in data["venues"] and not data["venue_other"]:
        return fail("Informe o nome do outro local.")
    if not data["event_modes"]:
        return fail("Selecione pelo menos um tipo de evento (presencial, on-line ou híbrido).")
    try:
        attendees = int(data["expected_attendees"] or 0)
        if attendees < 0:
            raise ValueError
    except ValueError:
        return fail("Informe um número válido de participantes.")
    for email_field in ["organizer_email", "contact_email"]:
        email = data[email_field].lower()
        data[email_field] = email
        if email and ("@" not in email or "." not in email.split("@")[-1]):
            return fail("Informe e-mails válidos.")

    venue_other = data["venue_other"] or None
    conflicts = []
    for blocker in _conflicts_for_range(start_date, end_date, data["start_time"], data["end_time"], data["venues"],
                                        venue_other, db=db, exclude_event_id=event_id):
        other = db.execute("SELECT id, title, start_date, start_time, end_time FROM events WHERE id=?", (blocker["event_id"],)).fetchone() if blocker["event_id"] else None
        conflicts.append({**blocker, "other": other})
    if conflicts and form.get("confirm_conflict") != "yes":
        return fail("Existe possível conflito de local e horário. Revise abaixo ou marque a confirmação para salvar mesmo assim.", conflicts)

    venues_text = "; ".join([v for v in data["venues"] if v != "Outro"] + ([venue_other] if "Outro" in data["venues"] and venue_other else []))
    new = {
        "title": data["title"][:180], "department": data["department"][:180], "organizer_name": data["organizer_name"][:180],
        "organizer_email": data["organizer_email"][:180], "organizer_phone": data["organizer_phone"][:80],
        "contact_email": data["contact_email"][:180] or None, "event_type": data["event_category"],
        "event_type_other": data["event_category_other"][:180] or None if data["event_category"] == "Outro" else None,
        "event_format": ", ".join(data["event_modes"]), "start_date": start_date, "end_date": end_date,
        "start_time": data["start_time"], "end_time": data["end_time"], "venue": venues_text or None,
        "expected_attendees": attendees, "audience": data["audience"][:300], "description": data["description"][:5000],
        "authorized_by": data["authorized_by"][:180] or None, "cost_center": data["cost_center"][:120] or None,
        "additional_info": data["additional_info"][:5000] or None,
    }
    changes = []
    for key, label in EVENT_EDIT_LABELS.items():
        old_value = event[key]
        if str(old_value or "") != str(new[key] or ""):
            changes.append(f"{label}: {old_value or 'vazio'} → {new[key] or 'vazio'}")
    if event["venues_json"] != json.dumps(data["venues"], ensure_ascii=False) and not any(c.startswith("Local:") for c in changes):
        changes.append("Local: seleção atualizada")
    if not changes:
        flash("Nenhuma alteração para salvar.", "success")
        return redirect(url_for("event_detail", event_id=event_id))

    now = now_iso()
    db.execute(f"""UPDATE events SET {', '.join(f'{k}=?' for k in new)}, venues_json=?, venue_other=?, event_modes_json=?, updated_at=?
                   WHERE id=?""",
               (*new.values(), json.dumps(data["venues"], ensure_ascii=False),
                venue_other if "Outro" in data["venues"] else None,
                json.dumps(data["event_modes"], ensure_ascii=False), now, event_id))
    shifted = 0
    old_start = normalize_date(event["start_date"])
    if old_start and old_start != start_date and form.get("shift_tasks") == "yes":
        delta = (date.fromisoformat(start_date) - date.fromisoformat(old_start)).days
        for task in db.execute("SELECT id, due_date FROM tasks WHERE event_id=? AND status NOT IN ('concluida','nao_se_aplica') AND due_date IS NOT NULL AND due_date<>''", (event_id,)).fetchall():
            due = normalize_date(task["due_date"])
            if due:
                db.execute("UPDATE tasks SET due_date=? WHERE id=?", ((date.fromisoformat(due) + timedelta(days=delta)).isoformat(), task["id"]))
                shifted += 1
        if shifted:
            changes.append(f"Prazos de {shifted} tarefa(s) pendente(s) deslocados em {delta:+d} dia(s)")
    if conflicts:
        changes.append(f"Salvo com {len(conflicts)} possível(is) conflito(s) de agenda confirmado(s) pela equipe")
    log_event(db, event_id, "edicao", "\n".join(changes))
    db.commit()
    flash("Dados do evento atualizados e registrados no histórico." + (f" {shifted} prazo(s) do checklist recalculado(s)." if shifted else ""), "success")
    return redirect(url_for("event_detail", event_id=event_id))


def _send_evaluation_invitation(event, token: str):
    cfg = smtp_settings()
    if not smtp_is_configured():
        return False, "O SMTP ainda não está configurado. O link foi criado e pode ser copiado para envio manual."
    base_url = _public_app_base_url()
    if not base_url:
        return False, "Como o sistema está em endereço local, o link não é acessível ao solicitante. Configure APP_BASE_URL após publicar o sistema para enviar o convite por e-mail."
    recipient = (event["organizer_email"] or "").strip()
    if not recipient or "@" not in recipient:
        return False, "O e-mail do solicitante não está válido; copie o link para envio manual."
    evaluation_url = base_url + url_for("public_event_evaluation", token=token)
    msg = EmailMessage()
    msg["Subject"] = f"Avaliação do evento: {event['title']} — FMABC"
    msg["From"] = cfg["from_email"]
    msg["To"] = recipient
    msg.set_content(
        f"Olá, {event['organizer_name']}.\n\n"
        f"O evento {event['title']} ({event['protocol']}) foi encerrado pelo Setor de Eventos da FMABC. "
        "Sua avaliação é importante para aprimorar nosso atendimento e a organização de futuros eventos.\n\n"
        f"Responda à avaliação neste link: {evaluation_url}\n\n"
        "O formulário leva poucos minutos. Obrigado pela colaboração.\n\nSetor de Eventos — Centro Universitário FMABC",
        cte="quoted-printable",
    )

    try:
        with smtplib.SMTP(cfg["host"], cfg["port"], timeout=20) as server:
            if cfg["use_tls"]:
                server.starttls()
            if cfg["user"]:
                server.login(cfg["user"], cfg["password"])
            server.send_message(msg)
        return True, f"Convite de avaliação enviado para {recipient}."
    except Exception as exc:
        return False, f"Falha no envio SMTP ({type(exc).__name__}). O link continua disponível para envio manual."


@app.route("/eventos/<int:event_id>/finalizar", methods=["GET", "POST"])
@login_required
def finalize_event(event_id):
    db = get_db()
    event = get_event_or_404(event_id)
    if event["status"] == "cancelado":
        flash("Um evento cancelado não pode ser finalizado como realizado.", "error")
        return redirect(url_for("event_detail", event_id=event_id))
    if request.method == "POST":
        if request.form.get("confirm_realizado") != "yes":
            flash("Confirme que o evento aconteceu antes de registrar o encerramento.", "error")
            return redirect(url_for("finalize_event", event_id=event_id))
        summary = request.form.get("summary", "").strip()
        if not summary:
            flash("Preencha o resumo do que aconteceu no evento.", "error")
            return redirect(url_for("finalize_event", event_id=event_id))
        raw_attendees = request.form.get("actual_attendees", "").strip()
        actual_attendees = None
        if raw_attendees:
            try:
                actual_attendees = int(raw_attendees)
                if actual_attendees < 0:
                    raise ValueError
            except ValueError:
                flash("Informe um número válido para o público real ou deixe o campo em branco.", "error")
                return redirect(url_for("finalize_event", event_id=event_id))
        now = now_iso()
        existing_closure = db.execute("SELECT id FROM event_closures WHERE event_id=?", (event_id,)).fetchone()
        if existing_closure:
            db.execute(
                """UPDATE event_closures SET actual_attendees=?, summary=?, positives=?, issues=?, improvements=?,
                   follow_up_actions=?, final_observations=?, updated_by=?, updated_at=? WHERE event_id=?""",
                (actual_attendees, summary, request.form.get("positives", "").strip() or None,
                 request.form.get("issues", "").strip() or None, request.form.get("improvements", "").strip() or None,
                 request.form.get("follow_up_actions", "").strip() or None,
                 request.form.get("final_observations", "").strip() or None,
                 session.get("user_email"), now, event_id),
            )
        else:
            db.execute(
                """INSERT INTO event_closures(event_id, actual_attendees, summary, positives, issues, improvements,
                   follow_up_actions, final_observations, closed_by, closed_at, updated_by, updated_at)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                (event_id, actual_attendees, summary, request.form.get("positives", "").strip() or None,
                 request.form.get("issues", "").strip() or None, request.form.get("improvements", "").strip() or None,
                 request.form.get("follow_up_actions", "").strip() or None,
                 request.form.get("final_observations", "").strip() or None,
                 session.get("user_email"), now, session.get("user_email"), now),
            )
        db.execute("UPDATE events SET status='encerrado', updated_at=? WHERE id=?", (now, event_id))
        log_event(db, event_id, "encerramento", "Relatório de pós-evento atualizado." if existing_closure else "Evento encerrado com relatório de pós-evento.")
        evaluation = db.execute("SELECT * FROM event_evaluations WHERE event_id=?", (event_id,)).fetchone()
        if not evaluation:
            token = secrets.token_urlsafe(32)
            db.execute(
                "INSERT INTO event_evaluations(event_id, token, requester_email, created_at) VALUES (?,?,?,?)",
                (event_id, token, event["organizer_email"], now),
            )
        db.commit()
        evaluation = db.execute("SELECT * FROM event_evaluations WHERE event_id=?", (event_id,)).fetchone()
        if request.form.get("send_evaluation") == "yes" and not evaluation["responded_at"]:
            refreshed_event = get_event_or_404(event_id)
            sent, message = _send_evaluation_invitation(refreshed_event, evaluation["token"])
            if sent:
                db.execute("UPDATE event_evaluations SET invitation_sent_at=?, invitation_method='smtp' WHERE event_id=?", (now_iso(), event_id))
                db.commit()
                flash("Encerramento registrado. " + message, "success")
            else:
                flash("Encerramento registrado. " + message, "error")
        else:
            flash("Encerramento registrado. O link para avaliação está disponível nesta página.", "success")
        return redirect(url_for("finalize_event", event_id=event_id))
    closure = db.execute("SELECT * FROM event_closures WHERE event_id=?", (event_id,)).fetchone()
    evaluation = db.execute("SELECT * FROM event_evaluations WHERE event_id=?", (event_id,)).fetchone()
    return render_template(
        "event_closure.html", event=event, closure=closure, evaluation=evaluation,
        evaluation_url=(url_for("public_event_evaluation", token=evaluation["token"], _external=True) if evaluation else None),
        smtp_configured=smtp_is_configured(), public_base_configured=bool(os.getenv("APP_BASE_URL", "").strip()),
    )


@app.post("/eventos/<int:event_id>/status")
@login_required
def update_event_status(event_id):
    event = get_event_or_404(event_id)
    return_to = request.form.get("return_to", "")
    safe_return = return_to if (return_to.startswith("/") and not return_to.startswith("//") and "\\" not in return_to) else ""

    def back(default):
        return redirect(safe_return or default)

    status = request.form.get("status", "")
    if status not in STATUS_LABELS:
        flash("Status inválido.", "error")
        return back(url_for("event_detail", event_id=event_id))
    existing_closure = get_db().execute("SELECT id FROM event_closures WHERE event_id=?", (event_id,)).fetchone()
    if status == "encerrado" and not existing_closure:
        flash("Para encerrar um evento, registre primeiro o relatório de pós-evento.", "error")
        return redirect(url_for("finalize_event", event_id=event_id))
    if existing_closure and status != "encerrado":
        flash("Este evento já tem um relatório de encerramento. Atualize o relatório de pós-evento para corrigir informações; o status final foi preservado.", "error")
        return back(url_for("event_detail", event_id=event_id))
    db = get_db()
    owner, owner_error = _resolve_internal_owner(db, event, request.form)
    if owner_error:
        flash(owner_error, "error")
        return back(url_for("event_detail", event_id=event_id) + "#triagem")
    owner = owner[:180] if owner else None
    priority = request.form.get("priority", "Normal") if request.form.get("priority") in {"Baixa", "Normal", "Alta", "Urgente"} else "Normal"
    requester_message = (request.form.get("message_to_requester") or "").strip()
    notify = request.form.get("notify_requester") == "yes"
    if status == "aguardando_informacoes" and event["status"] != status and not requester_message:
        flash("Para pedir informações ao solicitante, escreva em “Mensagem ao solicitante” o que está faltando.", "error")
        return back(url_for("event_detail", event_id=event_id) + "#triagem")
    db.execute(
        "UPDATE events SET status = ?, priority = ?, internal_owner = ?, internal_notes = ?, updated_at = ? WHERE id = ?",
        (status, priority, owner, request.form.get("internal_notes", "").strip() or None, now_iso(), event_id),
    )
    _log_triage_changes(db, event, status, priority, owner)
    for note in handle_status_change(db, event, status, notify, requester_message):
        flash(note, "success")
    db.commit()
    dispatch_emails_async()
    if status in {"aprovado", "em_planejamento"}:
        refreshed = get_event_or_404(event_id)
        # Aviso preventivo: conflitos precisam de conferência humana, não bloqueiam o fluxo.
        try:
            overlaps = _find_schedule_conflicts(db.execute("SELECT * FROM events WHERE status<>'cancelado' AND start_date BETWEEN ? AND ? ORDER BY start_date,start_time", ((date.fromisoformat(event["start_date"])-timedelta(days=1)).isoformat(), (date.fromisoformat(event["end_date"] or event["start_date"])+timedelta(days=1)).isoformat())).fetchall())
            if any(event_id in {c["event_a_id"],c["event_b_id"]} for c in overlaps):
                flash("Atenção: há possível conflito de local/horário. Confira a Agenda Institucional.", "warning")
        except (ValueError, TypeError):
            pass
        created_count = add_checklist(refreshed)
        if created_count:
            flash(f"Status atualizado. Checklist inicial criado com {created_count} tarefas.", "success")
        else:
            flash("Status atualizado. O checklist existente foi mantido.", "success")
    else:
        flash(f"“{event['title']}”: triagem salva." if safe_return else "Status e informações internas atualizados.", "success")
    return back(url_for("event_detail", event_id=event_id))


__all__ = [name for name in dict(globals()) if not name.startswith("__")]
