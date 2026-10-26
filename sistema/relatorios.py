"""Relatórios anuais e exportação CSV."""
from __future__ import annotations

from .core import *  # noqa: F401,F403


def _report_filters(args):
    raw_year = (args.get("ano") or str(date.today().year)).strip()
    try:
        year = int(raw_year)
        if year < 2000 or year > 2100:
            raise ValueError
    except ValueError:
        year = date.today().year
    status_filter = (args.get("status") or "realizados").strip()
    allowed_filters = {"realizados", "encerrados", "todos", *STATUS_LABELS.keys()}
    if status_filter not in allowed_filters:
        status_filter = "realizados"
    event_type = (args.get("categoria") or "").strip()
    department = (args.get("setor") or "").strip()
    return year, status_filter, event_type, department


def _annual_report_rows(year: int, status_filter: str, event_type: str = "", department: str = ""):
    db = get_db()
    start = f"{year:04d}-01-01"
    end = f"{year + 1:04d}-01-01"
    sql = """SELECT e.*, c.actual_attendees, c.summary AS closure_summary,
        c.positives AS closure_positives, c.issues AS closure_issues,
        c.improvements AS closure_improvements, c.follow_up_actions AS closure_follow_up,
        c.final_observations AS closure_observations, c.closed_by, c.closed_at,
        ev.rating_overall, ev.rating_sector, ev.rating_communication,
        ev.rating_responsiveness, ev.rating_needs_met, ev.positive_feedback,
        ev.improvement_suggestions, ev.additional_comments, ev.responded_at,
        (SELECT COALESCE(SUM(bi.estimated_amount),0) FROM event_budget_items bi WHERE bi.event_id=e.id AND bi.status<>'cancelado') AS budget_estimated_total,
        (SELECT COALESCE(SUM(bi.contracted_amount),0) FROM event_budget_items bi WHERE bi.event_id=e.id AND bi.status<>'cancelado') AS budget_contracted_total,
        (SELECT COALESCE(SUM(bi.actual_amount),0) FROM event_budget_items bi WHERE bi.event_id=e.id AND bi.status<>'cancelado') AS budget_actual_total,
        (SELECT COUNT(*) FROM event_budget_items bi WHERE bi.event_id=e.id AND bi.status<>'cancelado' AND bi.estimated_amount IS NOT NULL) AS budget_estimated_count,
        (SELECT COUNT(*) FROM event_budget_items bi WHERE bi.event_id=e.id AND bi.status<>'cancelado' AND bi.actual_amount IS NOT NULL) AS budget_actual_count,
        (SELECT COUNT(*) FROM event_incidents ei WHERE ei.event_id=e.id) AS incident_count,
        (SELECT COUNT(*) FROM event_incidents ei WHERE ei.event_id=e.id AND ei.status<>'resolvida') AS open_incident_count
        FROM events e
        LEFT JOIN event_closures c ON c.event_id=e.id
        LEFT JOIN event_evaluations ev ON ev.event_id=e.id
        WHERE e.start_date >= ? AND e.start_date < ?"""
    params = [start, end]
    if status_filter == "realizados":
        sql += " AND e.status IN ('realizado','encerrado')"
    elif status_filter == "encerrados":
        sql += " AND e.status = 'encerrado'"
    elif status_filter != "todos":
        sql += " AND e.status = ?"
        params.append(status_filter)
    if event_type:
        if event_type == "Outro":
            sql += " AND e.event_type = ?"
            params.append(event_type)
        else:
            sql += " AND (e.event_type = ? OR e.event_type_other = ?)"
            params.extend([event_type, event_type])
    if department:
        sql += " AND e.department = ?"
        params.append(department)
    sql += " ORDER BY e.start_date, e.start_time, e.title"
    return db.execute(sql, params).fetchall()


def _rating_average(rows, field):
    values = [int(row[field]) for row in rows if row[field] is not None]
    return round(sum(values) / len(values), 1) if values else None


@app.get("/relatorios")
@login_required
def event_reports():
    year, status_filter, event_type, department = _report_filters(request.args)
    rows = _annual_report_rows(year, status_filter, event_type, department)
    db = get_db()
    departments = [r["department"] for r in db.execute(
        "SELECT DISTINCT department FROM events WHERE department IS NOT NULL AND department <> '' ORDER BY department"
    ).fetchall()]
    finished = [r for r in rows if r["status"] in {"realizado", "encerrado"}]
    closed = [r for r in rows if r["status"] == "encerrado"]
    actual_attendance = sum(r["actual_attendees"] or 0 for r in rows)
    evaluated = sum(1 for r in rows if r["responded_at"])
    budget_estimated_total = sum(float(r["budget_estimated_total"] or 0) for r in rows)
    budget_actual_total = sum(float(r["budget_actual_total"] or 0) for r in rows)
    incident_total = sum(int(r["incident_count"] or 0) for r in rows)
    incident_open_total = sum(int(r["open_incident_count"] or 0) for r in rows)
    budget_estimated_count = sum(int(r["budget_estimated_count"] or 0) for r in rows)
    budget_actual_count = sum(int(r["budget_actual_count"] or 0) for r in rows)
    return render_template(
        "reports.html", rows=rows, year=year, status_filter=status_filter,
        event_type_filter=event_type, department_filter=department,
        departments=departments, event_types=EVENT_TYPES,
        finished_count=len(finished), closed_count=len(closed),
        actual_attendance=actual_attendance, evaluated_count=evaluated,
        budget_estimated_total=budget_estimated_total, budget_actual_total=budget_actual_total,
        budget_estimated_count=budget_estimated_count, budget_actual_count=budget_actual_count,
        incident_total=incident_total, incident_open_total=incident_open_total,
        avg_overall=_rating_average(rows, "rating_overall"),
        avg_sector=_rating_average(rows, "rating_sector"),
    )


def _safe_csv_cell(value):
    """Avoid spreadsheet formula execution for exported user-entered text."""
    if isinstance(value, str) and value.startswith(("=", "+", "-", "@", "\t", "\r")):
        return "'" + value
    return value


@app.get("/relatorios/exportar.csv")
@login_required
def export_annual_report():
    year, status_filter, event_type, department = _report_filters(request.args)
    rows = _annual_report_rows(year, status_filter, event_type, department)
    output = io.StringIO(newline="")
    output.write("\ufeff")  # BOM makes Portuguese text display correctly in Excel.
    writer = csv.writer(output, delimiter=";")
    writer.writerow([
        "Protocolo", "Evento", "Data", "Horário de início", "Horário de término", "Categoria", "Setor solicitante", "Responsável",
        "Formato", "Local", "Público previsto", "Público real", "Status",
        "Resumo pós-evento", "Pontos positivos", "Falhas/dificuldades", "Melhorias sugeridas",
        "Ações de acompanhamento", "Avaliação geral (1-5)", "Avaliação Setor de Eventos (1-5)",
        "Comunicação (1-5)", "Agilidade (1-5)", "Necessidades atendidas (1-5)",
        "Pontos positivos do solicitante", "Sugestões do solicitante", "Comentários", "Respondida em", "Encerrado em",
        "Orçamento previsto (R$)", "Valor contratado (R$)", "Custo realizado (R$)", "Ocorrências registradas", "Ocorrências em aberto",
    ])
    for row in rows:
        csv_values = [
            row["protocol"], row["title"], row["start_date"], row["start_time"], row["end_time"],
            row["event_type_other"] or row["event_type"], row["department"], row["organizer_name"], row["event_format"], row["venue"],
            row["expected_attendees"], row["actual_attendees"], STATUS_LABELS.get(row["status"], row["status"]),
            row["closure_summary"], row["closure_positives"], row["closure_issues"], row["closure_improvements"],
            row["closure_follow_up"], row["rating_overall"], row["rating_sector"],
            row["rating_communication"], row["rating_responsiveness"], row["rating_needs_met"],
            row["positive_feedback"], row["improvement_suggestions"], row["additional_comments"],
            row["responded_at"], row["closed_at"], row["budget_estimated_total"] if row["budget_estimated_count"] else "",
            row["budget_contracted_total"] or "",
            row["budget_actual_total"] if row["budget_actual_count"] else "",
            row["incident_count"], row["open_incident_count"],
        ]
        writer.writerow([_safe_csv_cell(value) for value in csv_values])
    filename = f"relatorio_eventos_fmabc_{year}.csv"
    return Response(
        output.getvalue(), content_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


__all__ = [name for name in dict(globals()) if not name.startswith("__")]
