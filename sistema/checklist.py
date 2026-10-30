"""Tarefas do evento, checklist consolidado, impressão e modelos de checklist com campos personalizados."""
from __future__ import annotations

from .core import *  # noqa: F401,F403


def _safe_event_day(event) -> date:
    try:
        return date.fromisoformat(event["start_date"])
    except (TypeError, ValueError, KeyError, IndexError):
        return date.today()


@app.get("/eventos/<int:event_id>/checklist/imprimir")
@login_required
def print_event_checklist(event_id):
    """Render a compact checklist designed to print on no more than one A4 sheet, duplex."""
    event = get_event_or_404(event_id)
    tasks = list(get_db().execute(
        "SELECT * FROM tasks WHERE event_id = ? ORDER BY sort_order, id", (event_id,)
    ).fetchall())
    if not tasks:
        flash("Este evento ainda não possui checklist para imprimir.", "error")
        return redirect(url_for("event_checklist", event_id=event_id))

    # Short checklists fit on one side. Longer checklists are explicitly divided into
    # two printable sheets so that duplex printing uses at most one A4 physical sheet.
    if len(tasks) <= 24:
        task_pages = [tasks]
    else:
        midpoint = (len(tasks) + 1) // 2
        task_pages = [tasks[:midpoint], tasks[midpoint:]]
    completed = sum(1 for task in tasks if task["status"] in TASK_DONE_STATUSES)
    progress = round((completed / len(tasks)) * 100)
    max_page_tasks = max(len(page) for page in task_pages)
    density = "ultra" if max_page_tasks > 28 else ("dense" if max_page_tasks > 22 else "normal")
    return render_template(
        "checklist_print.html", event=event, tasks=tasks, task_pages=task_pages,
        task_statuses=TASK_STATUSES, completed=completed, progress=progress,
        auto_print=request.args.get("auto") == "1", density=density,
    )


@app.post("/eventos/<int:event_id>/tarefas/<int:task_id>/alternar")
@login_required
def toggle_task(event_id, task_id):
    """Concluir/reabrir com um clique. Responde em JSON quando chamada pela página."""
    event = get_event_or_404(event_id)
    db = get_db()
    task = db.execute("SELECT * FROM tasks WHERE id = ? AND event_id = ?", (task_id, event_id)).fetchone()
    if not task:
        abort(404)
    reopen = task["status"] in TASK_DONE_STATUSES
    new_status = "pendente" if reopen else "concluida"
    db.execute("UPDATE tasks SET status = ?, completed_at = ? WHERE id = ?",
               (new_status, None if reopen else now_iso(), task_id))
    db.execute("UPDATE events SET updated_at = ? WHERE id = ?", (now_iso(), event_id))
    db.commit()
    if request.headers.get("X-Requested-With") == "fetch":
        updated = db.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
        return jsonify({"ok": True, "task": _task_json(updated, event), "counts": checklist_counts(db, event, session.get("user_email"))})
    return redirect(url_for("event_checklist", event_id=event_id) + f"#tarefa-{task_id}")


@app.post("/eventos/<int:event_id>/tarefas/<int:task_id>/nao-se-aplica")
@login_required
def toggle_task_na(event_id, task_id):
    """Marca/desmarca uma tarefa como 'Não se aplica' com um clique, sem precisar concluí-la."""
    event = get_event_or_404(event_id)
    db = get_db()
    task = db.execute("SELECT * FROM tasks WHERE id = ? AND event_id = ?", (task_id, event_id)).fetchone()
    if not task:
        abort(404)
    reopen = task["status"] == "nao_se_aplica"
    new_status = "pendente" if reopen else "nao_se_aplica"
    db.execute("UPDATE tasks SET status = ?, completed_at = ? WHERE id = ?", (new_status, None, task_id))
    db.execute("UPDATE events SET updated_at = ? WHERE id = ?", (now_iso(), event_id))
    db.commit()
    if request.headers.get("X-Requested-With") == "fetch":
        updated = db.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
        return jsonify({"ok": True, "task": _task_json(updated, event), "counts": checklist_counts(db, event, session.get("user_email"))})
    return redirect(url_for("event_checklist", event_id=event_id) + f"#tarefa-{task_id}")


def _task_json(task, event) -> dict:
    view = task_view(task, checklist_periods(event), session.get("user_email"))
    return {"id": task["id"], "title": task["title"], "category": task["category"], "status": task["status"],
            "status_label": view["status_label"], "show_status": view["show_status"], "done": view["done"],
            "due_text": view["due_text"], "tone": view["tone"], "who": view["who"] or "Sem responsável",
            "initials": view["initials"], "relative": view["relative"], "mine": view["mine"], "bucket": view["bucket"]}


GROUP_MODES = {"prazo": "Por prazo", "etapa": "Por etapa", "responsavel": "Por responsável"}


@app.get("/eventos/<int:event_id>/checklist")
@login_required
def event_checklist(event_id):
    """Aba Checklist: tarefas agrupadas por prazo, etapa ou responsável, com painel de detalhes."""
    event = get_event_or_404(event_id)
    db = get_db()
    me = session.get("user_email")
    mode = request.args.get("agrupar", "prazo")
    mode = mode if mode in GROUP_MODES else "prazo"
    periods = checklist_periods(event)
    tasks = db.execute("SELECT * FROM tasks WHERE event_id=? ORDER BY sort_order, id", (event_id,)).fetchall()
    items = []
    for task in tasks:
        item = dict(task)
        item.update(task_view(task, periods, me))
        items.append(item)

    def sort_key(item):
        due = normalize_date(item["due_date"]) or "9999-12-31"
        return (due, item["sort_order"], item["id"])

    groups = []
    if mode == "prazo":
        sunday, event_week = periods["sunday"], periods["event_week"]
        subs = {
            "atrasadas": "prazo já passou",
            "semana": f"até domingo, {sunday.strftime('%d/%m')}",
            "proximas": f"{(sunday + timedelta(days=1)).strftime('%d/%m')} a {(event_week - timedelta(days=1)).strftime('%d/%m')}",
            "evento": f"{event_week.strftime('%d/%m')} a {periods['event_end'].strftime('%d/%m')}",
            "pos": f"depois de {periods['event_end'].strftime('%d/%m')}",
            "sem_prazo": "defina um prazo", "concluidas": "",
        }
        default_dates = {
            "semana": max(periods["today"], periods["today"]).isoformat(),
            "proximas": (sunday + timedelta(days=1)).isoformat(),
            "evento": periods["event_start"].isoformat(),
            "pos": (periods["event_end"] + timedelta(days=1)).isoformat(),
        }
        for key, label, tone in CHECKLIST_GROUPS:
            members = sorted([i for i in items if i["bucket"] == key], key=sort_key)
            if members:
                groups.append({"key": key, "label": label, "tone": tone, "sub": subs.get(key, ""), "tasks": members,
                               "collapsed": key == "concluidas", "quick_date": default_dates.get(key)})
    else:
        def key_of(item):
            return (item["category"] or "Sem etapa") if mode == "etapa" else (item["who"] or "Sem responsável")
        names = []
        for item in sorted(items, key=sort_key):
            if key_of(item) not in names:
                names.append(key_of(item))
        for name in names:
            members = sorted([i for i in items if key_of(i) == name], key=sort_key)
            done = sum(1 for i in members if i["done"])
            groups.append({"key": re.sub(r"\W+", "-", name.lower()), "label": name, "tone": "neutral",
                           "sub": f"{done} de {len(members)} concluídas", "tasks": members, "collapsed": False,
                           "quick_date": None, "category": name if mode == "etapa" else None,
                           "assigned": name if mode == "responsavel" and name != "Sem responsável" else None})

    fields_by_template = _task_fields_by_template(db, {t["template_id"] for t in tasks})
    field_values = {}
    notes = {}
    if tasks:
        marks = ",".join("?" for _ in tasks)
        ids = [t["id"] for t in tasks]
        for row in db.execute(f"SELECT task_id, field_id, value FROM task_field_values WHERE task_id IN ({marks})", ids).fetchall():
            field_values.setdefault(row["task_id"], {})[row["field_id"]] = row["value"] or ""
        for row in db.execute(f"SELECT * FROM task_notes WHERE task_id IN ({marks}) ORDER BY created_at, id", ids).fetchall():
            notes.setdefault(row["task_id"], []).append(row)
    for item in items:
        item["note_list"] = notes.get(item["id"], [])
        item["notes_count"] = len(item["note_list"]) + (1 if (item["notes"] or "").strip() else 0)

    people = [r["email"] for r in db.execute("SELECT email FROM users WHERE is_active=1 ORDER BY email").fetchall()]
    people += [r["name"] for r in db.execute("SELECT name FROM departments WHERE active=1 ORDER BY name").fetchall()]
    people += ["Setor de Eventos"]
    people += [r["assigned_to"] for r in db.execute("SELECT DISTINCT assigned_to FROM tasks WHERE event_id=? AND assigned_to IS NOT NULL AND assigned_to<>''", (event_id,)).fetchall()]
    existing_keys = {(str(t["title"]).strip().casefold(), str(t["category"] or "").strip().casefold()) for t in tasks}
    days_left = (periods["event_start"] - periods["today"]).days
    return render_template(
        "event_checklist.html", event=event, groups=groups, tasks=items, mode=mode, group_modes=GROUP_MODES,
        counts=checklist_counts(db, event, me), periods=periods, days_left=days_left, me=me,
        task_statuses=TASK_STATUSES, task_fields_by_template={k: [dict(f, options=f["options_list"]) for f in v] for k, v in fields_by_template.items()},
        task_field_values=field_values, people=list(dict.fromkeys(p for p in people if p)),
        categories=sorted({t["category"] for t in tasks if t["category"]} | {"Planejamento", "Infraestrutura", "Comunicação", "Operação", "Pós-evento"}),
        available_task_templates=db.execute("SELECT * FROM task_templates WHERE active=1 ORDER BY category, sort_order, title").fetchall(),
        existing_task_keys=existing_keys,
    )


@app.post("/eventos/<int:event_id>/checklist/gerar")
@login_required
def generate_event_checklist(event_id):
    event = get_event_or_404(event_id)
    created = add_checklist(event)
    flash(f"Checklist criado com {created} tarefas a partir dos modelos." if created else "O checklist já existia; nada foi alterado.", "success")
    return redirect(url_for("event_checklist", event_id=event_id))


@app.post("/eventos/<int:event_id>/tarefas/<int:task_id>/observacoes")
@login_required
def add_task_note(event_id, task_id):
    event = get_event_or_404(event_id)
    db = get_db()
    task = db.execute("SELECT * FROM tasks WHERE id=? AND event_id=?", (task_id, event_id)).fetchone()
    if not task:
        abort(404)
    text = (request.form.get("text") or "").strip()[:3000]
    wants_json = request.headers.get("X-Requested-With") == "fetch"
    if not text:
        if wants_json:
            return jsonify({"ok": False, "message": "Escreva a observação."}), 400
        flash("Escreva a observação.", "error")
        return redirect(url_for("event_checklist", event_id=event_id) + f"#tarefa-{task_id}")
    now = now_iso()
    author = session.get("user_email")
    db.execute("INSERT INTO task_notes(task_id, author, text, created_at) VALUES (?,?,?,?)", (task_id, author, text, now))
    db.execute("UPDATE events SET updated_at=? WHERE id=?", (now, event_id))
    db.commit()
    if wants_json:
        count = db.execute("SELECT COUNT(*) FROM task_notes WHERE task_id=?", (task_id,)).fetchone()[0] + (1 if (task["notes"] or "").strip() else 0)
        return jsonify({"ok": True, "note": {"author": author, "when": f"{now[8:10]}/{now[5:7]} {now[11:16]}", "text": text}, "notes_count": count})
    return redirect(url_for("event_checklist", event_id=event_id) + f"#tarefa-{task_id}")


@app.post("/eventos/<int:event_id>/tarefas/<int:task_id>/excluir")
@login_required
def delete_task(event_id, task_id):
    get_event_or_404(event_id)
    db = get_db()
    task = db.execute("SELECT * FROM tasks WHERE id=? AND event_id=?", (task_id, event_id)).fetchone()
    if task:
        db.execute("DELETE FROM tasks WHERE id=?", (task_id,))
        log_event(db, event_id, "edicao", f"Tarefa removida do checklist: {task['title']}")
        db.commit()
        flash("Tarefa excluída do checklist.", "success")
    return redirect(url_for("event_checklist", event_id=event_id))


@app.post("/eventos/<int:event_id>/tarefas/lote")
@login_required
def bulk_tasks(event_id):
    """Ações em várias tarefas de uma vez: concluir, não se aplica, reabrir, atribuir, adiar."""
    get_event_or_404(event_id)
    db = get_db()
    ids = [i for i in request.form.getlist("task_ids", type=int) if i]
    action = request.form.get("action", "")
    back = redirect(url_for("event_checklist", event_id=event_id, agrupar=request.form.get("agrupar") or None))
    if not ids:
        flash("Selecione pelo menos uma tarefa.", "error")
        return back
    marks = ",".join("?" for _ in ids)
    rows = db.execute(f"SELECT * FROM tasks WHERE event_id=? AND id IN ({marks})", [event_id, *ids]).fetchall()
    now = now_iso()
    if action in {"concluida", "nao_se_aplica", "pendente"}:
        for row in rows:
            completed = (row["completed_at"] or now) if action == "concluida" else None
            db.execute("UPDATE tasks SET status=?, completed_at=? WHERE id=?", (action, completed, row["id"]))
        message = f"{len(rows)} tarefa(s) marcada(s) como “{TASK_STATUSES[action]}”."
    elif action == "atribuir":
        who = (request.form.get("assigned_to") or "").strip()[:180] or None
        for row in rows:
            db.execute("UPDATE tasks SET assigned_to=? WHERE id=?", (who, row["id"]))
        message = f"{len(rows)} tarefa(s) atribuída(s) a {who}." if who else f"Responsável removido de {len(rows)} tarefa(s)."
    elif action == "adiar":
        try:
            days = int(request.form.get("days") or 0)
        except ValueError:
            days = 0
        if not days or abs(days) > 365:
            flash("Informe quantos dias adiar (use número negativo para antecipar).", "error")
            return back
        moved = 0
        for row in rows:
            due = normalize_date(row["due_date"])
            if due:
                db.execute("UPDATE tasks SET due_date=? WHERE id=?", ((date.fromisoformat(due) + timedelta(days=days)).isoformat(), row["id"]))
                moved += 1
        message = f"Prazo de {moved} tarefa(s) {'adiado' if days > 0 else 'antecipado'} em {abs(days)} dia(s)."
    else:
        flash("Ação não reconhecida.", "error")
        return back
    db.execute("UPDATE events SET updated_at=? WHERE id=?", (now, event_id))
    db.commit()
    flash(message, "success")
    return back


@app.post("/eventos/<int:event_id>/tarefas/<int:task_id>/editar")
@login_required
def edit_task(event_id, task_id):
    """Salva a tarefa. Responde em JSON quando chamada pela página sem recarregar (X-Requested-With: fetch)."""
    get_event_or_404(event_id)
    db = get_db()
    task = db.execute("SELECT * FROM tasks WHERE id = ? AND event_id = ?", (task_id, event_id)).fetchone()
    if not task:
        abort(404)
    wants_json = request.headers.get("X-Requested-With") == "fetch"
    task_anchor = url_for("event_checklist", event_id=event_id) + "#tarefa-" + str(task_id)

    def fail(message):
        if wants_json:
            return jsonify({"ok": False, "message": message}), 400
        flash(message, "error")
        return redirect(task_anchor)

    title = request.form.get("title", "").strip()
    status = request.form.get("status", "pendente")
    if not title:
        return fail("O título da tarefa é obrigatório.")
    if status not in TASK_STATUSES:
        return fail("Status da tarefa inválido.")
    due = normalize_date(request.form.get("due_date"))
    if (request.form.get("due_date") or "").strip() and not due:
        return fail("Informe um prazo válido.")
    custom_values = {}
    for field in _task_fields_by_template(db, [task["template_id"]]).get(task["template_id"], []):
        raw = (request.form.get(f"custom_field_{field['id']}") or "").strip()
        raw = raw[:3000] if field["field_type"] == "textarea" else raw[:300]
        if field["required"] and not raw and status != "nao_se_aplica":
            return fail(f"Preencha o campo obrigatório “{field['label']}”.")
        if raw and field["field_type"] == "date" and not normalize_date(raw):
            return fail(f"O campo “{field['label']}” precisa de uma data válida.")
        if raw and field["field_type"] == "number":
            try:
                float(raw.replace(",", "."))
            except ValueError:
                return fail(f"O campo “{field['label']}” precisa de um número.")
        if raw and field["field_type"] == "select" and raw not in field["options_list"]:
            return fail(f"Escolha uma opção válida em “{field['label']}”.")
        if raw and field["field_type"] == "boolean" and raw not in {"Sim", "Não"}:
            raw = ""
        custom_values[field["id"]] = raw or None
    for field_id, value in custom_values.items():
        db.execute("""INSERT INTO task_field_values(task_id, field_id, value, updated_at) VALUES (?, ?, ?, ?)
                      ON CONFLICT(task_id, field_id) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at""",
                   (task_id, field_id, value, now_iso()))
    completed_at = (task["completed_at"] or now_iso()) if status == "concluida" else None
    category = request.form.get("category", "Organização").strip()[:80] or "Organização"
    assigned = request.form.get("assigned_to", "").strip()[:180] or None
    db.execute(
        """UPDATE tasks SET title = ?, category = ?, due_date = ?, status = ?, assigned_to = ?,
           description = ?, notes = ?, completed_at = ? WHERE id = ? AND event_id = ?""",
        (title[:240], category, due, status, assigned,
         request.form.get("description", "").strip()[:1500] or None,
         request.form.get("notes", "").strip()[:3000] or None,
         completed_at, task_id, event_id),
    )
    db.execute("UPDATE events SET updated_at = ? WHERE id = ?", (now_iso(), event_id))
    db.commit()
    if wants_json:
        event = get_event_or_404(event_id)
        updated = db.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
        counts = checklist_counts(db, event, session.get("user_email"))
        return jsonify({"ok": True, "message": "Tarefa salva.", "task": _task_json(updated, event), "counts": counts,
                        "progress": counts["pct"], "completed": counts["done"], "total": counts["total"],
                        "saved_at": datetime.now().strftime("%H:%M")})
    flash("Tarefa atualizada.", "success")
    return redirect(task_anchor)


@app.post("/eventos/<int:event_id>/tarefas/adicionar")
@login_required
def add_task(event_id):
    get_event_or_404(event_id)
    title = request.form.get("title", "").strip()
    if not title:
        flash("Digite o nome da tarefa.", "error")
        return redirect(url_for("event_checklist", event_id=event_id))
    due = normalize_date(request.form.get("due_date"))
    if (request.form.get("due_date") or "").strip() and not due:
        flash("Informe um prazo válido.", "error")
        return redirect(url_for("event_checklist", event_id=event_id))
    status = request.form.get("status", "pendente")
    if status not in TASK_STATUSES:
        status = "pendente"
    db = get_db()
    next_order = db.execute("SELECT COALESCE(MAX(sort_order), 0) + 1 n FROM tasks WHERE event_id = ?", (event_id,)).fetchone()["n"]
    cursor = db.execute(
        """INSERT INTO tasks(event_id, title, category, due_date, status, assigned_to, description, notes, sort_order, created_at, completed_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (event_id, title[:240], request.form.get("category", "Organização").strip()[:80] or "Organização", due, status,
         request.form.get("assigned_to", "").strip()[:180] or None,
         request.form.get("description", "").strip()[:1500] or None,
         request.form.get("notes", "").strip()[:3000] or None, next_order, now_iso(), now_iso() if status == "concluida" else None),
    )
    new_id = cursor.lastrowid
    db.execute("UPDATE events SET updated_at = ? WHERE id = ?", (now_iso(), event_id))
    db.commit()
    flash("Tarefa adicionada ao checklist.", "success")
    return redirect(url_for("event_checklist", event_id=event_id) + f"#tarefa-{new_id}")


@app.post("/eventos/<int:event_id>/tarefas/adicionar-modelos")
@login_required
def add_tasks_from_library(event_id):
    """Add selected active library templates to this event without changing the shared model."""
    event = get_event_or_404(event_id)
    db = get_db()
    selected_ids = []
    for raw_id in request.form.getlist("template_ids"):
        try:
            selected_ids.append(int(raw_id))
        except (TypeError, ValueError):
            continue
    if not selected_ids:
        flash("Selecione pelo menos uma atividade da biblioteca.", "error")
        return redirect(url_for("event_checklist", event_id=event_id))

    event_day = _safe_event_day(event)
    existing = {(str(row["title"]).strip().casefold(), str(row["category"] or "").strip().casefold())
                for row in db.execute("SELECT title, category FROM tasks WHERE event_id=?", (event_id,)).fetchall()}
    rows = db.execute(
        f"SELECT * FROM task_templates WHERE active=1 AND id IN ({','.join('?' for _ in selected_ids)}) ORDER BY category, sort_order, title",
        selected_ids,
    ).fetchall()
    added = 0
    skipped = 0
    next_order = db.execute("SELECT COALESCE(MAX(sort_order),0)+1 AS n FROM tasks WHERE event_id=?", (event_id,)).fetchone()["n"]
    for template in rows:
        key = (str(template["title"]).strip().casefold(), str(template["category"] or "").strip().casefold())
        if key in existing:
            skipped += 1
            continue
        due_date = (event_day + timedelta(days=int(template["due_offset"] or 0))).isoformat()
        db.execute("""INSERT INTO tasks(event_id,title,category,due_date,status,assigned_to,description,notes,sort_order,created_at,template_id)
                      VALUES(?,?,?,?, 'pendente', ?, ?, NULL, ?, ?, ?)""",
                   (event_id, template["title"], template["category"], due_date,
                    template["assigned_to"], template["description"], next_order, now_iso(), template["id"]))
        next_order += 1
        existing.add(key)
        added += 1
    db.execute("UPDATE events SET updated_at=? WHERE id=?", (now_iso(), event_id))
    db.commit()
    message = f"Adicionadas {added} atividade(s) da biblioteca ao checklist."
    if skipped:
        message += f" {skipped} já existiam e foram ignoradas para evitar duplicidade."
    flash(message, "success" if added else "warning")
    return redirect(url_for("event_checklist", event_id=event_id))


@app.get("/checklist-consolidado")
@login_required
def consolidated_checklist():
    """Cross-event checklist view for the Events team."""
    db = get_db()
    event_id = request.args.get("evento", type=int)
    status = request.args.get("status", "").strip()
    responsible = request.args.get("responsavel", "").strip()
    search = request.args.get("q", "").strip()
    period = request.args.get("prazo", "").strip()
    sql = "SELECT t.*, e.title AS event_title, e.protocol AS event_protocol, e.start_date AS event_date FROM tasks t JOIN events e ON e.id=t.event_id WHERE e.status NOT IN ('cancelado','realizado','encerrado')"
    params = []
    if event_id:
        sql += " AND e.id = ?"; params.append(event_id)
    if status in TASK_STATUSES:
        sql += " AND t.status = ?"; params.append(status)
    if responsible:
        sql += " AND COALESCE(t.assigned_to,'') = ?"; params.append(responsible)
    if search:
        like = f"%{search}%"; sql += " AND (t.title LIKE ? OR e.title LIKE ? OR e.protocol LIKE ?)"; params.extend([like, like, like])
    today = date.today().isoformat()
    if period == "atrasadas":
        sql += " AND t.due_date IS NOT NULL AND t.due_date<>'' AND t.due_date < ? AND t.status NOT IN ('concluida','nao_se_aplica')"; params.append(today)
    elif period == "7dias":
        end = (date.today() + timedelta(days=7)).isoformat(); sql += " AND t.due_date IS NOT NULL AND t.due_date<>'' AND t.due_date BETWEEN ? AND ? AND t.status NOT IN ('concluida','nao_se_aplica')"; params.extend([today, end])
    sql += " ORDER BY CASE WHEN t.due_date IS NULL OR t.due_date='' THEN 1 ELSE 0 END, t.due_date, e.start_date, t.sort_order, t.id"
    tasks = [dict(r) for r in db.execute(sql, params).fetchall()]
    for task in tasks:
        task['overdue'] = bool(task.get('due_date') and task['due_date'] < today and task['status'] not in TASK_DONE_STATUSES)
    events = db.execute("SELECT id,title,protocol FROM events WHERE status NOT IN ('cancelado','realizado','encerrado') ORDER BY start_date DESC").fetchall()
    people = db.execute("SELECT DISTINCT assigned_to FROM tasks WHERE assigned_to IS NOT NULL AND TRIM(assigned_to)<>'' ORDER BY assigned_to").fetchall()
    counts = {'total': len(tasks), 'pendentes': sum(1 for t in tasks if t['status'] not in TASK_DONE_STATUSES), 'atrasadas': sum(1 for t in tasks if t['overdue']), 'concluidas': sum(1 for t in tasks if t['status'] == 'concluida')}
    return render_template('checklist_consolidado.html', tasks=tasks, events=events, people=people, selected_event=event_id, selected_status=status, selected_responsible=responsible, selected_period=period, search=search, counts=counts, task_statuses=TASK_STATUSES)


@app.route("/modelos-checklist", methods=["GET", "POST"])
@login_required
def checklist_templates():
    if session.get("user_role") != "admin":
        abort(404)
    db = get_db()
    categories = ["Planejamento", "Administrativo", "Infraestrutura", "Manutenção", "Limpeza", "TI / Audiovisual", "Comunicação", "Inscrições", "Credenciamento", "Certificados", "Fornecedores", "Materiais", "Cerimonial", "Convidados", "Recepção", "Logística", "Transmissão", "Dia do evento", "Pós-evento", "Operação", "Outro"]
    trigger_types = {"always": "Todos os eventos", "support": "Serviço de apoio", "item": "Item solicitado", "mode": "Modalidade", "category": "Categoria do evento"}
    trigger_values = list(dict.fromkeys(SUPPORT_OPTIONS + REQUESTED_ITEM_OPTIONS + FORMATS + EVENT_TYPES))
    if request.method == "POST":
        action = request.form.get("action", "create")
        if action == "toggle":
            template_id = request.form.get("template_id", type=int)
            row = db.execute("SELECT * FROM task_templates WHERE id = ?", (template_id,)).fetchone()
            if row:
                db.execute("UPDATE task_templates SET active = ?, updated_at = ? WHERE id = ?", (0 if row["active"] else 1, now_iso(), template_id))
                db.commit()
                flash("Modelo ativado." if not row["active"] else "Modelo inativado: ele não entra em novos checklists.", "success")
            return redirect(url_for("checklist_templates") + f"#template-{template_id}")
        if action in {"add_field", "delete_field"}:
            template_id = request.form.get("template_id", type=int)
            if not db.execute("SELECT 1 FROM task_templates WHERE id=?", (template_id,)).fetchone():
                flash("Modelo de tarefa não encontrado.", "error")
                return redirect(url_for("checklist_templates"))
            anchor = f"#template-{template_id}"
            if action == "delete_field":
                db.execute("DELETE FROM task_template_fields WHERE id=? AND template_id=?",
                           (request.form.get("field_id", type=int), template_id))
                db.commit()
                flash("Campo removido do modelo, junto com os valores preenchidos nas tarefas.", "success")
                return redirect(url_for("checklist_templates") + anchor)
            label = (request.form.get("field_label") or "").strip()[:160]
            field_type = request.form.get("field_type", "text")
            options = _split_field_options(request.form.get("field_options"))
            if not label:
                flash("Informe o nome do campo.", "error")
            elif field_type not in TASK_FIELD_TYPES:
                flash("Tipo de campo inválido.", "error")
            elif field_type == "select" and len(options) < 2:
                flash("Para uma lista de opções, informe pelo menos duas opções separadas por vírgula ou linha.", "error")
            else:
                order = db.execute("SELECT COALESCE(MAX(sort_order),0)+1 FROM task_template_fields WHERE template_id=?", (template_id,)).fetchone()[0]
                db.execute("""INSERT INTO task_template_fields(template_id,label,field_type,options,required,sort_order,created_at)
                              VALUES (?,?,?,?,?,?,?)""",
                           (template_id, label, field_type, "\n".join(options) if field_type == "select" else None,
                            1 if request.form.get("required") else 0, order, now_iso()))
                db.commit()
                flash("Campo adicionado. Ele aparece nas tarefas deste modelo, inclusive nas já criadas.", "success")
            return redirect(url_for("checklist_templates") + anchor)
        title = request.form.get("title", "").strip()
        trigger_type = request.form.get("trigger_type", "always")
        trigger_value = request.form.get("trigger_value", "").strip() or None
        try:
            due_offset = int(request.form.get("due_offset", "-7"))
        except ValueError:
            due_offset = -7
        if not title:
            flash("Informe o nome da tarefa do modelo.", "error")
        elif trigger_type not in trigger_types:
            flash("Condição de ativação inválida.", "error")
        elif trigger_type != "always" and not trigger_value:
            flash("Informe o valor que ativará esta tarefa.", "error")
        elif trigger_type == "support" and trigger_value not in SUPPORT_OPTIONS:
            flash("Selecione um serviço de apoio válido.", "error")
        elif trigger_type == "item" and trigger_value not in REQUESTED_ITEM_OPTIONS:
            flash("Selecione um item válido do formulário.", "error")
        elif trigger_type == "mode" and trigger_value not in FORMATS:
            flash("Selecione uma modalidade válida.", "error")
        elif trigger_type == "category" and trigger_value not in EVENT_TYPES:
            flash("Selecione uma categoria de evento válida.", "error")
        else:
            values = (title[:240], request.form.get("category", "Planejamento")[:80],
                      request.form.get("description", "").strip()[:1500] or None,
                      trigger_type, trigger_value, max(-365, min(365, due_offset)),
                      request.form.get("assigned_to", "").strip()[:180] or None)
            if action == "update":
                template_id = request.form.get("template_id", type=int)
                db.execute("""UPDATE task_templates SET title=?, category=?, description=?, trigger_type=?, trigger_value=?,
                           due_offset=?, assigned_to=?, updated_at=? WHERE id=?""", (*values, now_iso(), template_id))
                flash("Modelo de tarefa atualizado. A alteração vale para checklists gerados daqui em diante.", "success")
                db.commit()
                return redirect(url_for("checklist_templates") + f"#template-{template_id}")
            else:
                order = db.execute("SELECT COALESCE(MAX(sort_order),0)+1 n FROM task_templates").fetchone()["n"]
                db.execute("""INSERT INTO task_templates(title, category, description, trigger_type, trigger_value,
                           due_offset, assigned_to, active, sort_order, created_at, updated_at)
                           VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?)""", (*values, order, now_iso(), now_iso()))
                flash("Modelo de tarefa criado. Ele será aplicado a novas solicitações aprovadas.", "success")
            db.commit()
            return redirect(url_for("checklist_templates"))
    templates = db.execute("SELECT * FROM task_templates ORDER BY active DESC, sort_order, id").fetchall()
    fields_by_template = {
        template_id: [dict(field, options=", ".join(field["options_list"])) for field in fields]
        for template_id, fields in _task_fields_by_template(db).items()
    }
    return render_template("checklist_templates.html", templates=templates, categories=categories, trigger_types=trigger_types,
                           trigger_values=trigger_values, fields_by_template=fields_by_template, field_types=TASK_FIELD_TYPES)


__all__ = [name for name in dict(globals()) if not name.startswith("__")]
