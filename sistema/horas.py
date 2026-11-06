"""Banco de horas e horas extras: controla quem trabalhou em cada evento, calcula
automaticamente as horas extras (dia útil acima de 8h, ou qualquer hora em fim de
semana) e mantém um saldo por funcionário — ou registra o pagamento em dinheiro
daquelas horas, com relatório imprimível para a folha de pagamento."""
from __future__ import annotations

from .core import *  # noqa: F401,F403


def _require_admin():
    if session.get("user_role") != "admin":
        abort(404)


def _active_employees(db):
    return db.execute("SELECT * FROM employees WHERE active=1 ORDER BY name").fetchall()


def _parse_hours_worked(form) -> tuple[float | None, str | None, str | None, str | None]:
    """Retorna (horas_trabalhadas, start_time, end_time, erro). Aceita horário de início/fim
    (calcula a duração) ou um total de horas informado diretamente."""
    start_time = (form.get("start_time") or "").strip()
    end_time = (form.get("end_time") or "").strip()
    hours_raw = (form.get("hours_worked") or "").strip()
    if start_time and end_time:
        try:
            t1 = datetime.strptime(start_time, "%H:%M")
            t2 = datetime.strptime(end_time, "%H:%M")
            delta = (t2 - t1).total_seconds() / 3600
            if delta <= 0:
                delta += 24  # virou a noite (ex.: 20:00 às 02:00)
            return round(delta, 2), start_time, end_time, None
        except ValueError:
            return None, None, None, "Horário inválido. Use o formato HH:MM."
    if hours_raw:
        try:
            hours = float(hours_raw.replace(",", "."))
            if hours <= 0 or hours > 24:
                return None, None, None, "Informe um total de horas válido (entre 0 e 24)."
            return round(hours, 2), None, None, None
        except ValueError:
            return None, None, None, "Informe um total de horas válido."
    return None, None, None, "Informe o horário de início/fim ou o total de horas trabalhadas."


@app.route("/horas", methods=["GET", "POST"])
@login_required
def time_bank_hub():
    """Painel do banco de horas: cadastro de funcionários, lançamento de horas trabalhadas
    e de folgas tiradas, com o saldo atual de cada um."""
    _require_admin()
    db = get_db()
    if request.method == "POST":
        action = (request.form.get("action") or "").strip()

        if action == "create_employee":
            name = (request.form.get("name") or "").strip()
            role = (request.form.get("role") or "").strip() or None
            if not name:
                flash("Informe o nome do funcionário.", "error")
            else:
                db.execute("INSERT INTO employees(name, role, active, created_at) VALUES (?, ?, 1, ?)",
                           (name, role, now_iso()))
                db.commit()
                flash("Funcionário cadastrado.", "success")

        elif action == "toggle_employee":
            emp_id = request.form.get("employee_id", type=int)
            emp = db.execute("SELECT * FROM employees WHERE id=?", (emp_id,)).fetchone()
            if emp:
                db.execute("UPDATE employees SET active=? WHERE id=?", (0 if emp["active"] else 1, emp_id))
                db.commit()
                flash("Funcionário reativado." if not emp["active"] else "Funcionário desativado.", "success")

        elif action == "add_work_entry":
            return _save_work_entry(db, redirect_to=url_for("time_bank_hub"))

        elif action == "add_time_off":
            return _save_time_off(db, redirect_to=url_for("time_bank_hub"))

        return redirect(url_for("time_bank_hub"))

    employees = employee_summary_rows(db)
    recent_entries = db.execute(
        """SELECT w.*, e.name AS employee_name, ev.title AS event_title, ev.protocol AS event_protocol
           FROM work_entries w JOIN employees e ON e.id = w.employee_id
           LEFT JOIN events ev ON ev.id = w.event_id
           ORDER BY w.work_date DESC, w.id DESC LIMIT 15"""
    ).fetchall()
    all_employees = db.execute("SELECT * FROM employees ORDER BY active DESC, name").fetchall()
    upcoming_events = db.execute(
        "SELECT id, title, protocol, start_date FROM events WHERE status NOT IN ('encerrado','cancelado') ORDER BY start_date DESC LIMIT 200"
    ).fetchall()
    totals = {
        "balance": round(sum(r["balance"] for r in employees), 2),
        "paid_total": round(sum(r["paid_total"] for r in employees), 2),
    }
    return render_template("time_bank.html", employees=employees, all_employees=all_employees,
                           recent_entries=recent_entries, upcoming_events=upcoming_events,
                           standard_hours=STANDARD_WORKDAY_HOURS, totals=totals)


@app.get("/horas/funcionario/<int:employee_id>")
@login_required
def time_bank_employee(employee_id):
    """Extrato individual: todos os lançamentos de horas e de folgas, em ordem cronológica,
    com o saldo corrente após cada um — pronto para imprimir."""
    _require_admin()
    db = get_db()
    employee = db.execute("SELECT * FROM employees WHERE id=?", (employee_id,)).fetchone()
    if not employee:
        abort(404)
    work_rows = db.execute(
        """SELECT w.*, ev.title AS event_title, ev.protocol AS event_protocol
           FROM work_entries w LEFT JOIN events ev ON ev.id = w.event_id
           WHERE w.employee_id=? ORDER BY w.work_date, w.id""",
        (employee_id,),
    ).fetchall()
    off_rows = db.execute(
        "SELECT * FROM time_off_entries WHERE employee_id=? ORDER BY off_date, id", (employee_id,)
    ).fetchall()
    ledger = []
    for w in work_rows:
        if w["settlement_type"] == "banco":
            ledger.append({"kind": "credito", "date": w["work_date"], "row": w})
    for o in off_rows:
        ledger.append({"kind": "debito", "date": o["off_date"], "row": o})
    ledger.sort(key=lambda item: (item["date"], item["row"]["id"]))
    running = 0.0
    for item in ledger:
        if item["kind"] == "credito":
            running += item["row"]["extra_hours"]
        else:
            running -= item["row"]["hours"]
        item["running_balance"] = round(running, 2)
    paid_rows = [w for w in work_rows if w["settlement_type"] == "pago"]
    paid_total = round(sum(w["paid_amount"] or 0 for w in paid_rows), 2)
    upcoming_events = db.execute(
        "SELECT id, title, protocol, start_date FROM events ORDER BY start_date DESC LIMIT 200"
    ).fetchall()
    return render_template("time_bank_employee.html", employee=employee, work_rows=work_rows,
                           off_rows=off_rows, ledger=ledger, balance=employee_balance(db, employee_id),
                           paid_rows=paid_rows, paid_total=paid_total, upcoming_events=upcoming_events,
                           standard_hours=STANDARD_WORKDAY_HOURS)


def _save_work_entry(db, redirect_to: str):
    employee_id = request.form.get("employee_id", type=int)
    new_name = (request.form.get("new_employee_name") or "").strip()
    if not employee_id and new_name:
        cur = db.execute("INSERT INTO employees(name, active, created_at) VALUES (?, 1, ?)", (new_name, now_iso()))
        employee_id = cur.lastrowid
    employee = db.execute("SELECT * FROM employees WHERE id=?", (employee_id,)).fetchone() if employee_id else None
    work_date = (request.form.get("work_date") or "").strip()
    event_id = request.form.get("event_id", type=int) or None
    settlement_type = request.form.get("settlement_type") or "banco"
    notes = (request.form.get("notes") or "").strip()[:500] or None

    if not employee:
        flash("Selecione ou cadastre o nome do funcionário.", "error")
        return redirect(redirect_to)
    try:
        date.fromisoformat(work_date)
    except ValueError:
        flash("Informe uma data válida para o dia trabalhado.", "error")
        return redirect(redirect_to)
    if settlement_type not in ("banco", "pago"):
        settlement_type = "banco"

    hours_worked, start_time, end_time, error = _parse_hours_worked(request.form)
    if error:
        flash(error, "error")
        return redirect(redirect_to)

    standard = standard_hours_for_date(work_date)
    extra = compute_extra_hours(hours_worked, standard)
    hourly_rate = None
    paid_amount = None
    if settlement_type == "pago":
        rate_raw = (request.form.get("hourly_rate") or "").strip()
        try:
            hourly_rate = float(rate_raw.replace(",", "."))
            if hourly_rate <= 0:
                raise ValueError
        except ValueError:
            flash("Informe o valor da hora para lançar como pago em dinheiro.", "error")
            return redirect(redirect_to)
        paid_amount = round(extra * hourly_rate, 2)

    db.execute(
        """INSERT INTO work_entries(employee_id, event_id, work_date, start_time, end_time, hours_worked,
             standard_hours, extra_hours, settlement_type, hourly_rate, paid_amount, notes, created_at, created_by)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (employee_id, event_id, work_date, start_time, end_time, hours_worked, standard, extra,
         settlement_type, hourly_rate, paid_amount, notes, now_iso(), session.get("user_email")),
    )
    db.commit()
    if extra <= 0:
        flash(f"Lançamento salvo para {employee['name']}. Sem horas extras nesse dia (dentro da jornada padrão).", "success")
    elif settlement_type == "pago":
        flash(f"Lançamento salvo: {extra:g}h extras de {employee['name']}, pago em dinheiro (R$ {paid_amount:.2f}).", "success")
    else:
        flash(f"Lançamento salvo: {extra:g}h extras creditadas no banco de horas de {employee['name']}.", "success")
    return redirect(redirect_to)


def _save_time_off(db, redirect_to: str):
    employee_id = request.form.get("employee_id", type=int)
    employee = db.execute("SELECT * FROM employees WHERE id=?", (employee_id,)).fetchone() if employee_id else None
    off_date = (request.form.get("off_date") or "").strip()
    hours_raw = (request.form.get("off_hours") or "").strip()
    notes = (request.form.get("off_notes") or "").strip()[:500] or None
    if not employee:
        flash("Selecione o funcionário para lançar a folga.", "error")
        return redirect(redirect_to)
    try:
        date.fromisoformat(off_date)
    except ValueError:
        flash("Informe uma data válida para a folga.", "error")
        return redirect(redirect_to)
    try:
        hours = float(hours_raw.replace(",", "."))
        if hours <= 0:
            raise ValueError
    except ValueError:
        flash("Informe quantas horas de folga foram tiradas.", "error")
        return redirect(redirect_to)
    db.execute(
        "INSERT INTO time_off_entries(employee_id, off_date, hours, notes, created_at, created_by) VALUES (?,?,?,?,?,?)",
        (employee_id, off_date, round(hours, 2), notes, now_iso(), session.get("user_email")),
    )
    db.commit()
    flash(f"Folga de {hours:g}h lançada para {employee['name']} — descontada do banco de horas.", "success")
    return redirect(redirect_to)


@app.post("/horas/lancamento/excluir")
@login_required
def delete_work_entry():
    _require_admin()
    db = get_db()
    entry_id = request.form.get("entry_id", type=int)
    entry = db.execute("SELECT * FROM work_entries WHERE id=?", (entry_id,)).fetchone()
    if entry:
        db.execute("DELETE FROM work_entries WHERE id=?", (entry_id,))
        db.commit()
        flash("Lançamento de horas excluído.", "success")
    back = request.form.get("back") or url_for("time_bank_hub")
    return redirect(back)


@app.post("/horas/folga/excluir")
@login_required
def delete_time_off_entry():
    _require_admin()
    db = get_db()
    entry_id = request.form.get("entry_id", type=int)
    entry = db.execute("SELECT * FROM time_off_entries WHERE id=?", (entry_id,)).fetchone()
    if entry:
        db.execute("DELETE FROM time_off_entries WHERE id=?", (entry_id,))
        db.commit()
        flash("Lançamento de folga excluído.", "success")
    back = request.form.get("back") or url_for("time_bank_hub")
    return redirect(back)


@app.get("/horas/relatorio")
@login_required
def time_bank_report():
    """Relatório imprimível: saldo de banco de horas por funcionário e detalhamento das
    horas extras pagas em dinheiro no período — pronto para a folha de pagamento."""
    _require_admin()
    db = get_db()
    start = (request.args.get("inicio") or "").strip()
    end = (request.args.get("fim") or "").strip()
    employee_id = request.args.get("funcionario", type=int)
    today = date.today()
    if not start:
        start = today.replace(day=1).isoformat()
    if not end:
        end = today.isoformat()

    employees = _active_employees(db)
    if employee_id:
        employees = [e for e in employees if e["id"] == employee_id]

    paid_query = (
        """SELECT w.*, e.name AS employee_name, ev.title AS event_title, ev.protocol AS event_protocol
           FROM work_entries w JOIN employees e ON e.id=w.employee_id LEFT JOIN events ev ON ev.id=w.event_id
           WHERE w.settlement_type='pago' AND w.work_date BETWEEN ? AND ?"""
    )
    params = [start, end]
    if employee_id:
        paid_query += " AND w.employee_id=?"
        params.append(employee_id)
    paid_query += " ORDER BY w.work_date, e.name"
    paid_rows = db.execute(paid_query, params).fetchall()
    paid_total = round(sum(r["paid_amount"] or 0 for r in paid_rows), 2)
    paid_hours_total = round(sum(r["extra_hours"] or 0 for r in paid_rows), 2)

    banked_query = (
        """SELECT w.*, e.name AS employee_name, ev.title AS event_title, ev.protocol AS event_protocol
           FROM work_entries w JOIN employees e ON e.id=w.employee_id LEFT JOIN events ev ON ev.id=w.event_id
           WHERE w.settlement_type='banco' AND w.work_date BETWEEN ? AND ?"""
    )
    params2 = [start, end]
    if employee_id:
        banked_query += " AND w.employee_id=?"
        params2.append(employee_id)
    banked_query += " ORDER BY w.work_date, e.name"
    banked_rows = db.execute(banked_query, params2).fetchall()
    banked_hours_total = round(sum(r["extra_hours"] or 0 for r in banked_rows), 2)

    balance_rows = [{"id": e["id"], "name": e["name"], "role": e["role"], "balance": employee_balance(db, e["id"])}
                    for e in employees]

    return render_template("time_bank_report.html", balance_rows=balance_rows, paid_rows=paid_rows,
                           banked_rows=banked_rows, paid_total=paid_total, paid_hours_total=paid_hours_total,
                           banked_hours_total=banked_hours_total, start=start, end=end,
                           employee_id=employee_id, all_employees=db.execute("SELECT * FROM employees ORDER BY name").fetchall())


@app.route("/eventos/<int:event_id>/horas", methods=["GET", "POST"])
@login_required
def event_time_bank(event_id):
    """Aba do evento: quem trabalhou, quando e quantas horas — com o cálculo automático de
    horas extras já feito na hora de salvar."""
    _require_admin()
    event = get_event_or_404(event_id)
    db = get_db()
    if request.method == "POST":
        return _save_work_entry(db, redirect_to=url_for("event_time_bank", event_id=event_id))
    entries = db.execute(
        """SELECT w.*, e.name AS employee_name FROM work_entries w JOIN employees e ON e.id=w.employee_id
           WHERE w.event_id=? ORDER BY w.work_date, w.id""",
        (event_id,),
    ).fetchall()
    totals = {
        "worked": round(sum(e["hours_worked"] for e in entries), 2),
        "extra_banco": round(sum(e["extra_hours"] for e in entries if e["settlement_type"] == "banco"), 2),
        "extra_pago_horas": round(sum(e["extra_hours"] for e in entries if e["settlement_type"] == "pago"), 2),
        "extra_pago_valor": round(sum((e["paid_amount"] or 0) for e in entries if e["settlement_type"] == "pago"), 2),
    }
    all_employees = db.execute("SELECT * FROM employees WHERE active=1 ORDER BY name").fetchall()
    return render_template("event_time_bank.html", event=event, entries=entries, totals=totals,
                           all_employees=all_employees, standard_hours=STANDARD_WORKDAY_HOURS)
