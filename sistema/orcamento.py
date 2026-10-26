"""Orçamento e custos do evento, cotações e comparativo histórico."""
from __future__ import annotations

from .core import *  # noqa: F401,F403


def _parse_money(raw):
    """Converte valores digitados no padrão brasileiro: 1500 · 1.500 · 1.500,00 · 1500,5 · 1500.50."""
    value = (raw or "").strip().replace("R$", "").replace(" ", "").replace("\u00a0", "")
    if not value:
        return None
    if "," in value:
        # Vírgula decimal: pontos são separadores de milhar.
        value = value.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"\d{1,3}(\.\d{3})+", value):
        # 1.500 ou 1.250.000 sem centavos: pontos de milhar.
        value = value.replace(".", "")
    if not re.fullmatch(r"\d+(\.\d{1,2})?", value):
        raise ValueError("Informe um valor monetário válido, por exemplo 1.500,00.")
    amount = float(value)
    if amount > 1_000_000_000:
        raise ValueError("O valor informado é alto demais. Confira o número digitado.")
    return round(amount, 2)


def _optional_date(raw):
    raw = (raw or "").strip()
    if not raw:
        return None
    parsed = normalize_date(raw)
    if not parsed:
        raise ValueError("Informe uma data válida.")
    return parsed


@app.route("/eventos/<int:event_id>/orcamento", methods=["GET","POST"])
@login_required
def event_budget(event_id):
    event = get_event_or_404(event_id)
    db = get_db()
    back = redirect(url_for("event_budget", event_id=event_id))
    if request.method == "POST":
        action = request.form.get("action", "add")
        item_id = request.form.get("item_id", type=int)
        now = now_iso()

        if action == "delete":
            db.execute("DELETE FROM event_budget_quotes WHERE budget_item_id=? AND event_id=?", (item_id, event_id))
            db.execute("DELETE FROM event_budget_items WHERE id=? AND event_id=?", (item_id, event_id))
            db.commit()
            flash("Despesa e cotações vinculadas removidas.", "success")
            return back

        if action in {"quote_add", "select_quote"}:
            item = db.execute("SELECT * FROM event_budget_items WHERE id=? AND event_id=?", (item_id, event_id)).fetchone()
            if not item:
                flash("Despesa não encontrada neste evento.", "error")
                return back

        if action == "quote_add":
            supplier = (request.form.get("quote_supplier") or "").strip()[:180]
            try:
                amount = _parse_money(request.form.get("quote_amount"))
                quote_date = _optional_date(request.form.get("quote_date"))
                valid_until = _optional_date(request.form.get("valid_until"))
            except ValueError as exc:
                flash(str(exc), "error")
                return back
            if not supplier or amount is None:
                flash("Informe o fornecedor e o valor cotado.", "error")
                return back
            db.execute("""INSERT INTO event_budget_quotes(event_id,budget_item_id,supplier,quote_amount,quote_date,valid_until,selected,notes,created_at,updated_at)
                          VALUES (?,?,?,?,?,?,0,?,?,?)""",
                       (event_id, item_id, supplier, amount, quote_date, valid_until,
                        (request.form.get("quote_notes") or "").strip()[:1500] or None, now, now))
            if item["status"] == "previsto":
                db.execute("UPDATE event_budget_items SET status='em_cotacao', updated_at=? WHERE id=?", (now, item_id))
            db.commit()
            flash("Cotação registrada.", "success")
            return back

        if action == "select_quote":
            quote_id = request.form.get("quote_id", type=int)
            quote = db.execute("SELECT * FROM event_budget_quotes WHERE id=? AND budget_item_id=? AND event_id=?",
                               (quote_id, item_id, event_id)).fetchone()
            if not quote:
                flash("Cotação não encontrada.", "error")
                return back
            db.execute("UPDATE event_budget_quotes SET selected = CASE WHEN id=? THEN 1 ELSE 0 END, updated_at=? WHERE budget_item_id=?",
                       (quote_id, now, item_id))
            db.execute("UPDATE event_budget_items SET supplier=?, contracted_amount=?, updated_at=? WHERE id=?",
                       (quote["supplier"], quote["quote_amount"], now, item_id))
            db.commit()
            flash(f"Cotação de {quote['supplier']} selecionada como referência. Fornecedor e valor contratado da despesa foram atualizados; isso não substitui a aprovação financeira oficial.", "success")
            return back

        if action == "quote_delete":
            quote_id = request.form.get("quote_id", type=int)
            db.execute("DELETE FROM event_budget_quotes WHERE id=? AND event_id=?", (quote_id, event_id))
            db.commit()
            flash("Cotação removida.", "success")
            return back

        name = (request.form.get("item_name") or "").strip()
        if not name:
            flash("Informe o nome da despesa ou serviço.", "error")
            return back
        try:
            est = _parse_money(request.form.get("estimated_amount"))
            con = _parse_money(request.form.get("contracted_amount"))
            act = _parse_money(request.form.get("actual_amount"))
            approved_at = _optional_date(request.form.get("approved_at"))
        except ValueError as exc:
            flash(str(exc), "error")
            return back
        status = request.form.get("status", "previsto")
        status = status if status in BUDGET_STATUSES else "previsto"
        approval = request.form.get("approval_status", "nao_solicitada")
        approval = approval if approval in BUDGET_APPROVAL_STATUSES else "nao_solicitada"
        category = (request.form.get("category") or "Outros").strip()[:100] or "Outros"
        def text(field, size):
            return (request.form.get(field) or "").strip()[:size] or None
        vals = (name[:240], category, text("supplier", 180), est, con, act, status, approval,
                text("approved_by", 180), approved_at, text("cost_center", 120), text("purchase_order", 120),
                text("invoice_reference", 120), text("notes", 1500), now)
        if action == "edit" and item_id:
            db.execute("""UPDATE event_budget_items SET item_name=?,category=?,supplier=?,estimated_amount=?,contracted_amount=?,
                          actual_amount=?,status=?,approval_status=?,approved_by=?,approved_at=?,cost_center=?,purchase_order=?,
                          invoice_reference=?,notes=?,updated_at=? WHERE id=? AND event_id=?""", vals + (item_id, event_id))
            flash("Despesa atualizada.", "success")
        else:
            db.execute("""INSERT INTO event_budget_items(item_name,category,supplier,estimated_amount,contracted_amount,actual_amount,
                          status,approval_status,approved_by,approved_at,cost_center,purchase_order,invoice_reference,notes,updated_at,
                          event_id,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", vals + (event_id, now))
            flash("Despesa incluída no orçamento do evento.", "success")
        db.commit()
        return back

    items = db.execute("SELECT * FROM event_budget_items WHERE event_id=? ORDER BY category,item_name,id", (event_id,)).fetchall()
    quotes_by_item = {}
    for quote in db.execute("SELECT * FROM event_budget_quotes WHERE event_id=? ORDER BY selected DESC, quote_amount, id", (event_id,)).fetchall():
        quotes_by_item.setdefault(quote["budget_item_id"], []).append(quote)
    active = [x for x in items if x["status"] != "cancelado"]
    est = sum(float(x["estimated_amount"] or 0) for x in active)
    con = sum(float(x["contracted_amount"] or 0) for x in active)
    act = sum(float(x["actual_amount"] or 0) for x in active)
    by_category = {}
    for x in active:
        row = by_category.setdefault(x["category"] or "Outros", {"category": x["category"] or "Outros", "estimated": 0.0, "contracted": 0.0, "actual": 0.0})
        row["estimated"] += float(x["estimated_amount"] or 0)
        row["contracted"] += float(x["contracted_amount"] or 0)
        row["actual"] += float(x["actual_amount"] or 0)
    return render_template("event_budget.html", event=event, items=items, quotes_by_item=quotes_by_item,
                           total_estimated=est, total_contracted=con, total_actual=act, variance=act - est,
                           by_category=sorted(by_category.values(), key=lambda r: r["category"]))


@app.get("/relatorios/comparativo-custos")
@login_required
def budget_comparison_report():
    """Comparativo histórico dos valores previstos, contratados e realizados."""
    db = get_db()
    selected_type = (request.args.get("event_type") or "").strip()
    if selected_type and selected_type not in EVENT_TYPES:
        # Permite também categorias livres registradas em event_type_other.
        valid_other = db.execute(
            "SELECT 1 FROM events WHERE event_type_other = ? LIMIT 1", (selected_type,)
        ).fetchone()
        if not valid_other:
            selected_type = ""

    where = []
    params = []
    if selected_type:
        if selected_type == "Outro":
            where.append("e.event_type = ?")
            params.append("Outro")
        else:
            where.append("(e.event_type = ? OR e.event_type_other = ?)")
            params.extend([selected_type, selected_type])
    where_sql = (" WHERE " + " AND ".join(where)) if where else ""
    rows = db.execute(f"""
        SELECT e.id, e.protocol, e.title, e.start_date, e.event_type, e.event_type_other,
               COALESCE((SELECT SUM(bi.estimated_amount) FROM event_budget_items bi
                         WHERE bi.event_id = e.id AND bi.status <> 'cancelado'), 0) AS estimated_total,
               COALESCE((SELECT SUM(bi.contracted_amount) FROM event_budget_items bi
                         WHERE bi.event_id = e.id AND bi.status <> 'cancelado'), 0) AS contracted_total,
               COALESCE((SELECT SUM(bi.actual_amount) FROM event_budget_items bi
                         WHERE bi.event_id = e.id AND bi.status <> 'cancelado'), 0) AS actual_total,
               (SELECT COUNT(*) FROM event_budget_items bi WHERE bi.event_id = e.id AND bi.status <> 'cancelado') AS expense_count
        FROM events e
        {where_sql}
        ORDER BY e.start_date DESC, e.title COLLATE NOCASE
    """, params).fetchall()

    grouped_map = {}
    for row in rows:
        year = (row["start_date"] or "")[:4] or "Sem data"
        kind = (row["event_type_other"] or row["event_type"] or "Não informado")
        key = (year, kind)
        if key not in grouped_map:
            grouped_map[key] = {"year": year, "kind": kind, "count": 0,
                                "estimated": 0.0, "contracted": 0.0, "actual": 0.0}
        group = grouped_map[key]
        group["count"] += 1
        group["estimated"] += float(row["estimated_total"] or 0)
        group["contracted"] += float(row["contracted_total"] or 0)
        group["actual"] += float(row["actual_total"] or 0)

    grouped = sorted(grouped_map.values(),
                     key=lambda item: (item["year"], item["kind"]), reverse=True)
    return render_template(
        "budget_comparison.html", rows=rows, grouped=grouped,
        event_types=EVENT_TYPES, selected_type=selected_type,
    )


__all__ = [name for name in dict(globals()) if not name.startswith("__")]
