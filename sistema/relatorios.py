"""Relatórios anuais, central de relatórios personalizados e exportação CSV."""
from __future__ import annotations

from .core import *  # noqa: F401,F403

MONTH_NAMES_PT = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho",
                   "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]

INCIDENT_CATEGORIES = ["Infraestrutura", "Tecnologia / audiovisual", "Fornecedor", "Programação",
                        "Público / credenciamento", "Comunicação", "Acessibilidade / segurança", "Outro"]
INCIDENT_STATUS_LABELS = {"aberta": "Aberta", "em_tratamento": "Em tratamento", "resolvida": "Resolvida"}

# Catálogo de modelos de relatório oferecidos na Central de Relatórios. A ordem aqui
# define a ordem de exibição dos cartões na página.
REPORT_MODELS = {
    "detalhado": {
        "label": "Lista detalhada de eventos",
        "description": "Todos os eventos do ano, evento a evento: público, custos, avaliações e ocorrências.",
        "icon": "📋",
    },
    "gastos": {
        "label": "Gastos do período",
        "description": "Quanto foi gasto no ano — em todos os eventos ou em um evento específico.",
        "icon": "💰",
    },
    "eventos_periodo": {
        "label": "Eventos realizados por período",
        "description": "Quantos eventos aconteceram por mês ou por ano.",
        "icon": "📅",
    },
    "eventos_setor": {
        "label": "Eventos e gastos por setor",
        "description": "Comparativo de volume e custo entre as áreas solicitantes.",
        "icon": "🏛",
    },
    "custos_tipo": {
        "label": "Custos por tipo de evento",
        "description": "Previsto x realizado, agrupado por categoria de evento no ano.",
        "icon": "📊",
    },
    "publico": {
        "label": "Público atendido",
        "description": "Público previsto x real, mês a mês, com taxa de ocupação.",
        "icon": "👥",
    },
    "avaliacoes": {
        "label": "Avaliação dos solicitantes",
        "description": "Médias de satisfação e taxa de resposta das pesquisas pós-evento.",
        "icon": "⭐",
    },
    "ocorrencias": {
        "label": "Ocorrências registradas",
        "description": "Quantidade e situação dos imprevistos registrados nos eventos.",
        "icon": "⚠",
    },
}


def _parse_year(raw, default=None):
    default = default or date.today().year
    try:
        year = int((raw or "").strip())
        if year < 2000 or year > 2100:
            raise ValueError
        return year
    except (TypeError, ValueError):
        return default


def _money_br(value):
    return "R$ " + ("%.2f" % float(value or 0)).replace(".", ",")


def _report_filters(args):
    year = _parse_year(args.get("ano"))
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


def _event_type_filter_clause(event_type):
    if not event_type:
        return "", []
    if event_type == "Outro":
        return " AND e.event_type = ?", [event_type]
    return " AND (e.event_type = ? OR e.event_type_other = ?)", [event_type, event_type]


# --- Modelos da central de relatórios personalizados -----------------------------

def _model_gastos(db, year, event_id, department, event_type):
    if event_id:
        event = db.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
        if not event:
            return None
        items = db.execute(
            "SELECT COALESCE(NULLIF(category,''),'Outros') category, "
            "COALESCE(SUM(estimated_amount),0) est, COALESCE(SUM(contracted_amount),0) con, COALESCE(SUM(actual_amount),0) act "
            "FROM event_budget_items WHERE event_id = ? AND status <> 'cancelado' GROUP BY category ORDER BY category",
            (event_id,),
        ).fetchall()
        est_total = sum(float(r["est"] or 0) for r in items)
        con_total = sum(float(r["con"] or 0) for r in items)
        act_total = sum(float(r["act"] or 0) for r in items)
        kpis = [
            {"label": "Previsto", "value": _money_br(est_total)},
            {"label": "Contratado", "value": _money_br(con_total)},
            {"label": "Realizado", "value": _money_br(act_total)},
            {"label": "Diferença (realizado - previsto)", "value": _money_br(act_total - est_total)},
        ]
        table_headers = ["Categoria de despesa", "Previsto", "Contratado", "Realizado"]
        table_rows = [[r["category"], _money_br(r["est"]), _money_br(r["con"]), _money_br(r["act"])] for r in items]
        csv_rows = [[r["category"], r["est"] or 0, r["con"] or 0, r["act"] or 0] for r in items]
        chart = [{"label": r["category"], "value": float(r["act"] or r["est"] or 0)} for r in items]
        return {
            "title": f"Gastos — {event['title']}",
            "subtitle": f"{event['protocol']} · {event['start_date'][8:10]}/{event['start_date'][5:7]}/{event['start_date'][:4]}",
            "kpis": kpis, "chart": chart, "chart_unit": "R$",
            "table_headers": table_headers, "table_rows": table_rows,
            "csv_headers": table_headers, "csv_rows": csv_rows,
            "empty": not items,
            "empty_message": "Nenhum item de orçamento cadastrado para este evento.",
        }

    start = f"{year:04d}-01-01"
    end = f"{year + 1:04d}-01-01"
    clause, clause_params = _event_type_filter_clause(event_type)
    params = [start, end]
    if department:
        clause += " AND e.department = ?"
        clause_params.append(department)
    sql = f"""SELECT substr(e.start_date,6,2) mes, COUNT(DISTINCT e.id) eventos,
        COALESCE(SUM(bi.estimated_amount),0) est, COALESCE(SUM(bi.contracted_amount),0) con, COALESCE(SUM(bi.actual_amount),0) act
        FROM events e LEFT JOIN event_budget_items bi ON bi.event_id = e.id AND bi.status <> 'cancelado'
        WHERE e.start_date >= ? AND e.start_date < ?{clause}
        GROUP BY mes ORDER BY mes"""
    rows = db.execute(sql, params + clause_params).fetchall()
    by_month = {r["mes"]: r for r in rows}
    est_total = sum(float(r["est"] or 0) for r in rows)
    con_total = sum(float(r["con"] or 0) for r in rows)
    act_total = sum(float(r["act"] or 0) for r in rows)
    event_total = sum(int(r["eventos"] or 0) for r in rows)
    table_headers = ["Mês", "Eventos", "Previsto", "Contratado", "Realizado"]
    table_rows, chart = [], []
    for m in range(1, 13):
        key = f"{m:02d}"
        r = by_month.get(key)
        act = float(r["act"] or 0) if r else 0.0
        table_rows.append([
            MONTH_NAMES_PT[m - 1], int(r["eventos"]) if r else 0,
            _money_br(r["est"] if r else 0), _money_br(r["con"] if r else 0), _money_br(act),
        ])
        chart.append({"label": MONTH_NAMES_PT[m - 1][:3], "value": act})
    csv_rows = [[row[0], row[1], row[2], row[3], row[4]] for row in table_rows]
    subtitle = f"Ano de {year}"
    if department:
        subtitle += f" · Setor: {department}"
    if event_type:
        subtitle += f" · Categoria: {event_type}"
    return {
        "title": f"Gastos no ano de {year}", "subtitle": subtitle,
        "kpis": [
            {"label": "Previsto no ano", "value": _money_br(est_total)},
            {"label": "Contratado no ano", "value": _money_br(con_total)},
            {"label": "Realizado no ano", "value": _money_br(act_total)},
            {"label": "Eventos com movimento no ano", "value": str(event_total)},
        ],
        "chart": chart, "chart_unit": "R$",
        "table_headers": table_headers, "table_rows": table_rows,
        "csv_headers": table_headers, "csv_rows": csv_rows,
        "empty": event_total == 0,
        "empty_message": "Nenhum evento encontrado para este período e filtros.",
    }


def _model_eventos_periodo(db, year, granularidade, department, event_type, status_filter):
    clause, clause_params = _event_type_filter_clause(event_type)
    if department:
        clause += " AND e.department = ?"
        clause_params.append(department)
    status_clause = ""
    status_params = []
    if status_filter == "realizados":
        status_clause = " AND e.status IN ('realizado','encerrado')"
    elif status_filter == "encerrados":
        status_clause = " AND e.status = 'encerrado'"
    elif status_filter not in ("todos", ""):
        status_clause = " AND e.status = ?"
        status_params = [status_filter]

    if granularidade == "ano":
        sql = f"SELECT substr(e.start_date,1,4) periodo, COUNT(*) total FROM events e WHERE e.start_date IS NOT NULL{clause}{status_clause} GROUP BY periodo ORDER BY periodo"
        rows = db.execute(sql, clause_params + status_params).fetchall()
        table_headers = ["Ano", "Eventos"]
        table_rows = [[r["periodo"], r["total"]] for r in rows]
        chart = [{"label": r["periodo"], "value": r["total"]} for r in rows]
        total = sum(r["total"] for r in rows)
        best = max(rows, key=lambda r: r["total"]) if rows else None
        subtitle = "Todos os anos com eventos registrados"
        kpis = [
            {"label": "Total de eventos", "value": str(total)},
            {"label": "Ano com mais eventos", "value": (f"{best['periodo']} ({best['total']})" if best else "—")},
            {"label": "Média por ano", "value": (f"{total / len(rows):.1f}" if rows else "0")},
        ]
    else:
        start = f"{year:04d}-01-01"
        end = f"{year + 1:04d}-01-01"
        sql = f"SELECT substr(e.start_date,6,2) mes, COUNT(*) total FROM events e WHERE e.start_date >= ? AND e.start_date < ?{clause}{status_clause} GROUP BY mes ORDER BY mes"
        rows = db.execute(sql, [start, end] + clause_params + status_params).fetchall()
        by_month = {r["mes"]: r["total"] for r in rows}
        table_headers = ["Mês", "Eventos"]
        table_rows, chart = [], []
        for m in range(1, 13):
            total_m = by_month.get(f"{m:02d}", 0)
            table_rows.append([MONTH_NAMES_PT[m - 1], total_m])
            chart.append({"label": MONTH_NAMES_PT[m - 1][:3], "value": total_m})
        total = sum(by_month.values())
        best_month = max(by_month.items(), key=lambda kv: kv[1]) if by_month else None
        subtitle = f"Ano de {year}"
        kpis = [
            {"label": "Total de eventos no ano", "value": str(total)},
            {"label": "Mês com mais eventos", "value": (f"{MONTH_NAMES_PT[int(best_month[0]) - 1]} ({best_month[1]})" if best_month and best_month[1] else "—")},
            {"label": "Média mensal", "value": f"{total / 12:.1f}"},
        ]
    if department:
        subtitle += f" · Setor: {department}"
    if event_type:
        subtitle += f" · Categoria: {event_type}"
    return {
        "title": "Eventos realizados por período", "subtitle": subtitle,
        "kpis": kpis, "chart": chart, "chart_unit": "eventos",
        "table_headers": table_headers, "table_rows": table_rows,
        "csv_headers": table_headers, "csv_rows": table_rows,
        "empty": sum(r[1] for r in table_rows) == 0,
        "empty_message": "Nenhum evento encontrado para este período e filtros.",
    }


def _model_eventos_setor(db, year):
    start = f"{year:04d}-01-01"
    end = f"{year + 1:04d}-01-01"
    sql = """SELECT COALESCE(NULLIF(e.department,''), 'Não informado') setor, COUNT(*) total,
        COALESCE(SUM((SELECT SUM(bi.actual_amount) FROM event_budget_items bi WHERE bi.event_id = e.id AND bi.status <> 'cancelado')),0) gasto
        FROM events e WHERE e.start_date >= ? AND e.start_date < ? GROUP BY setor ORDER BY total DESC, setor"""
    rows = db.execute(sql, [start, end]).fetchall()
    table_headers = ["Setor solicitante", "Eventos", "Gasto realizado"]
    table_rows = [[r["setor"], r["total"], _money_br(r["gasto"])] for r in rows]
    csv_rows = [[r["setor"], r["total"], r["gasto"] or 0] for r in rows]
    chart = [{"label": r["setor"], "value": r["total"]} for r in rows]
    total_eventos = sum(r["total"] for r in rows)
    top = rows[0] if rows else None
    return {
        "title": "Eventos e gastos por setor", "subtitle": f"Ano de {year}",
        "kpis": [
            {"label": "Setores com eventos no ano", "value": str(len(rows))},
            {"label": "Setor com mais eventos", "value": (f"{top['setor']} ({top['total']})" if top else "—")},
            {"label": "Total de eventos no ano", "value": str(total_eventos)},
        ],
        "chart": chart, "chart_unit": "eventos",
        "table_headers": table_headers, "table_rows": table_rows,
        "csv_headers": table_headers, "csv_rows": csv_rows,
        "empty": not rows,
        "empty_message": "Nenhum evento encontrado neste ano.",
    }


def _model_custos_tipo(db, year):
    start = f"{year:04d}-01-01"
    end = f"{year + 1:04d}-01-01"
    sql = """SELECT COALESCE(NULLIF(e.event_type_other,''), e.event_type, 'Não informado') tipo, COUNT(*) eventos,
        COALESCE(SUM((SELECT SUM(bi.estimated_amount) FROM event_budget_items bi WHERE bi.event_id = e.id AND bi.status <> 'cancelado')),0) est,
        COALESCE(SUM((SELECT SUM(bi.actual_amount) FROM event_budget_items bi WHERE bi.event_id = e.id AND bi.status <> 'cancelado')),0) act
        FROM events e WHERE e.start_date >= ? AND e.start_date < ? GROUP BY tipo ORDER BY act DESC, tipo"""
    rows = db.execute(sql, [start, end]).fetchall()
    table_headers = ["Tipo de evento", "Eventos", "Previsto", "Realizado"]
    table_rows = [[r["tipo"], r["eventos"], _money_br(r["est"]), _money_br(r["act"])] for r in rows]
    csv_rows = [[r["tipo"], r["eventos"], r["est"] or 0, r["act"] or 0] for r in rows]
    chart = [{"label": r["tipo"], "value": float(r["act"] or 0)} for r in rows]
    est_total = sum(float(r["est"] or 0) for r in rows)
    act_total = sum(float(r["act"] or 0) for r in rows)
    return {
        "title": "Custos por tipo de evento", "subtitle": f"Ano de {year}",
        "kpis": [
            {"label": "Previsto no ano", "value": _money_br(est_total)},
            {"label": "Realizado no ano", "value": _money_br(act_total)},
            {"label": "Categorias com eventos", "value": str(len(rows))},
        ],
        "chart": chart, "chart_unit": "R$",
        "table_headers": table_headers, "table_rows": table_rows,
        "csv_headers": table_headers, "csv_rows": csv_rows,
        "empty": not rows,
        "empty_message": "Nenhum evento encontrado neste ano.",
    }


def _model_publico(db, year, department, event_type):
    clause, clause_params = _event_type_filter_clause(event_type)
    if department:
        clause += " AND e.department = ?"
        clause_params.append(department)
    start = f"{year:04d}-01-01"
    end = f"{year + 1:04d}-01-01"
    sql = f"""SELECT substr(e.start_date,6,2) mes, COUNT(*) eventos,
        COALESCE(SUM(e.expected_attendees),0) previsto, COALESCE(SUM(c.actual_attendees),0) real
        FROM events e LEFT JOIN event_closures c ON c.event_id = e.id
        WHERE e.start_date >= ? AND e.start_date < ?{clause}
        GROUP BY mes ORDER BY mes"""
    rows = db.execute(sql, [start, end] + clause_params).fetchall()
    by_month = {r["mes"]: r for r in rows}
    table_headers = ["Mês", "Eventos", "Público previsto", "Público real", "Ocupação"]
    table_rows, chart = [], []
    for m in range(1, 13):
        r = by_month.get(f"{m:02d}")
        previsto = int(r["previsto"]) if r else 0
        real = int(r["real"]) if r else 0
        ocupacao = f"{(real / previsto * 100):.0f}%" if previsto else "—"
        table_rows.append([MONTH_NAMES_PT[m - 1], int(r["eventos"]) if r else 0, previsto, real, ocupacao])
        chart.append({"label": MONTH_NAMES_PT[m - 1][:3], "value": real})
    previsto_total = sum(int(r["previsto"] or 0) for r in rows)
    real_total = sum(int(r["real"] or 0) for r in rows)
    ocupacao_geral = f"{(real_total / previsto_total * 100):.0f}%" if previsto_total else "—"
    subtitle = f"Ano de {year}"
    if department:
        subtitle += f" · Setor: {department}"
    if event_type:
        subtitle += f" · Categoria: {event_type}"
    return {
        "title": "Público atendido", "subtitle": subtitle,
        "kpis": [
            {"label": "Público previsto no ano", "value": str(previsto_total)},
            {"label": "Público real informado", "value": str(real_total)},
            {"label": "Taxa de ocupação geral", "value": ocupacao_geral},
        ],
        "chart": chart, "chart_unit": "pessoas",
        "table_headers": table_headers, "table_rows": table_rows,
        "csv_headers": table_headers, "csv_rows": table_rows,
        "empty": previsto_total == 0 and real_total == 0,
        "empty_message": "Nenhum evento com público registrado neste período.",
    }


def _model_avaliacoes(db, year):
    start = f"{year:04d}-01-01"
    end = f"{year + 1:04d}-01-01"
    rows = db.execute(
        """SELECT e.id, e.protocol, e.title, e.start_date, ev.rating_overall, ev.rating_sector,
            ev.rating_communication, ev.rating_responsiveness, ev.rating_needs_met, ev.responded_at
        FROM events e LEFT JOIN event_evaluations ev ON ev.event_id = e.id
        WHERE e.start_date >= ? AND e.start_date < ? AND e.status IN ('realizado','encerrado')
        ORDER BY e.start_date""",
        [start, end],
    ).fetchall()
    answered = [r for r in rows if r["responded_at"]]
    response_rate = f"{(len(answered) / len(rows) * 100):.0f}%" if rows else "—"
    criteria = [
        ("Geral", "rating_overall"), ("Setor de Eventos", "rating_sector"), ("Comunicação", "rating_communication"),
        ("Agilidade", "rating_responsiveness"), ("Necessidades atendidas", "rating_needs_met"),
    ]
    chart = []
    for label, field in criteria:
        avg = _rating_average(rows, field)
        chart.append({"label": label, "value": avg or 0})
    low_rated = sum(1 for r in answered if r["rating_overall"] is not None and int(r["rating_overall"]) <= 2)
    table_headers = ["Evento", "Data", "Geral", "Setor", "Comunicação", "Agilidade", "Necessidades atendidas"]
    table_rows = [
        [r["title"], f"{r['start_date'][8:10]}/{r['start_date'][5:7]}/{r['start_date'][:4]}",
         r["rating_overall"] or "—", r["rating_sector"] or "—", r["rating_communication"] or "—",
         r["rating_responsiveness"] or "—", r["rating_needs_met"] or "—"]
        for r in answered
    ]
    return {
        "title": "Avaliação dos solicitantes", "subtitle": f"Eventos realizados ou encerrados em {year}",
        "kpis": [
            {"label": "Eventos realizados no ano", "value": str(len(rows))},
            {"label": "Avaliações recebidas", "value": f"{len(answered)} ({response_rate})"},
            {"label": "Média geral", "value": (f"{_rating_average(rows, 'rating_overall')}/5" if answered else "—")},
            {"label": "Avaliações com nota baixa (≤2)", "value": str(low_rated)},
        ],
        "chart": chart, "chart_unit": "nota média (0-5)", "chart_max": 5,
        "table_headers": table_headers, "table_rows": table_rows,
        "csv_headers": table_headers, "csv_rows": table_rows,
        "empty": not answered,
        "empty_message": "Nenhuma avaliação de solicitante recebida neste período.",
    }


def _model_ocorrencias(db, year, status_filter):
    start = f"{year:04d}-01-01"
    end = f"{year + 1:04d}-01-01"
    sql = """SELECT ei.*, e.title AS event_title, e.protocol FROM event_incidents ei
        JOIN events e ON e.id = ei.event_id
        WHERE e.start_date >= ? AND e.start_date < ?"""
    params = [start, end]
    if status_filter and status_filter != "todas":
        sql += " AND ei.status = ?"
        params.append(status_filter)
    sql += " ORDER BY e.start_date DESC, ei.id DESC"
    rows = db.execute(sql, params).fetchall()
    by_category = {}
    for r in rows:
        by_category[r["category"]] = by_category.get(r["category"], 0) + 1
    chart = [{"label": k, "value": v} for k, v in sorted(by_category.items(), key=lambda kv: -kv[1])]
    counts = {key: sum(1 for r in rows if r["status"] == key) for key in INCIDENT_STATUS_LABELS}
    table_headers = ["Evento", "Categoria", "Situação", "Data", "Responsável"]
    table_rows = [
        [r["event_title"], r["category"], INCIDENT_STATUS_LABELS.get(r["status"], r["status"]),
         (r["incident_date"][:10] if r["incident_date"] else "—"), r["responsible"] or "—"]
        for r in rows
    ]
    return {
        "title": "Ocorrências registradas", "subtitle": f"Eventos com data em {year}",
        "kpis": [
            {"label": "Total de ocorrências", "value": str(len(rows))},
            {"label": "Abertas", "value": str(counts.get("aberta", 0))},
            {"label": "Em tratamento", "value": str(counts.get("em_tratamento", 0))},
            {"label": "Resolvidas", "value": str(counts.get("resolvida", 0))},
        ],
        "chart": chart, "chart_unit": "ocorrências",
        "table_headers": table_headers, "table_rows": table_rows,
        "csv_headers": table_headers, "csv_rows": table_rows,
        "empty": not rows,
        "empty_message": "Nenhuma ocorrência registrada neste período.",
    }


def _build_report_result(db, modelo, args, status_filter=None):
    """Monta o resultado do modelo escolhido a partir dos parâmetros da querystring."""
    year = _parse_year(args.get("ano"))
    department = (args.get("setor") or "").strip()
    event_type = (args.get("categoria") or "").strip()
    event_id = args.get("evento_id", type=int)
    granularidade = (args.get("granularidade") or "mes").strip()
    if granularidade not in ("mes", "ano"):
        granularidade = "mes"
    if status_filter is None:
        status_filter = (args.get("status") or ("todas" if modelo == "ocorrencias" else "todos")).strip()

    if modelo == "gastos":
        return _model_gastos(db, year, event_id, department, event_type)
    if modelo == "eventos_periodo":
        return _model_eventos_periodo(db, year, granularidade, department, event_type, status_filter)
    if modelo == "eventos_setor":
        return _model_eventos_setor(db, year)
    if modelo == "custos_tipo":
        return _model_custos_tipo(db, year)
    if modelo == "publico":
        return _model_publico(db, year, department, event_type)
    if modelo == "avaliacoes":
        return _model_avaliacoes(db, year)
    if modelo == "ocorrencias":
        return _model_ocorrencias(db, year, status_filter)
    return None


@app.get("/relatorios")
@login_required
def event_reports():
    db = get_db()
    modelo = (request.args.get("modelo") or "detalhado").strip()
    if modelo not in REPORT_MODELS:
        modelo = "detalhado"
    if modelo == "detalhado":
        year, status_filter, event_type, department = _report_filters(request.args)
    else:
        year = _parse_year(request.args.get("ano"))
        department = (request.args.get("setor") or "").strip()
        event_type = (request.args.get("categoria") or "").strip()
        default_status = "todas" if modelo == "ocorrencias" else "todos"
        status_filter = (request.args.get("status") or default_status).strip()
    departments = [r["department"] for r in db.execute(
        "SELECT DISTINCT department FROM events WHERE department IS NOT NULL AND department <> '' ORDER BY department"
    ).fetchall()]

    context = dict(
        models=REPORT_MODELS, modelo=modelo, year=year, status_filter=status_filter,
        event_type_filter=event_type, department_filter=department, departments=departments,
        event_types=EVENT_TYPES, incident_statuses=INCIDENT_STATUS_LABELS,
        granularidade=(request.args.get("granularidade") or "mes"),
        selected_event_id=request.args.get("evento_id", type=int),
    )

    if modelo == "detalhado":
        rows = _annual_report_rows(year, status_filter, event_type, department)
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
        context.update(
            rows=rows, finished_count=len(finished), closed_count=len(closed),
            actual_attendance=actual_attendance, evaluated_count=evaluated,
            budget_estimated_total=budget_estimated_total, budget_actual_total=budget_actual_total,
            budget_estimated_count=budget_estimated_count, budget_actual_count=budget_actual_count,
            incident_total=incident_total, incident_open_total=incident_open_total,
            avg_overall=_rating_average(rows, "rating_overall"),
            avg_sector=_rating_average(rows, "rating_sector"),
        )
    else:
        if modelo == "gastos":
            context["report_events"] = db.execute(
                "SELECT id, protocol, title, start_date FROM events ORDER BY start_date DESC LIMIT 400"
            ).fetchall()
        context["result"] = _build_report_result(db, modelo, request.args, status_filter=status_filter)

    return render_template("reports.html", **context)


def _safe_csv_cell(value):
    """Avoid spreadsheet formula execution for exported user-entered text."""
    if isinstance(value, str) and value.startswith(("=", "+", "-", "@", "\t", "\r")):
        return "'" + value
    return value


@app.get("/relatorios/exportar.csv")
@login_required
def export_annual_report():
    modelo = (request.args.get("modelo") or "detalhado").strip()
    if modelo not in REPORT_MODELS:
        modelo = "detalhado"

    if modelo != "detalhado":
        db = get_db()
        result = _build_report_result(db, modelo, request.args)
        output = io.StringIO(newline="")
        output.write("﻿")
        writer = csv.writer(output, delimiter=";")
        if result:
            writer.writerow(result["csv_headers"])
            for row in result["csv_rows"]:
                writer.writerow([_safe_csv_cell(value) for value in row])
        filename = f"relatorio_{modelo}_fmabc.csv"
        return Response(
            output.getvalue(), content_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )

    year, status_filter, event_type, department = _report_filters(request.args)
    rows = _annual_report_rows(year, status_filter, event_type, department)
    output = io.StringIO(newline="")
    output.write("﻿")  # BOM makes Portuguese text display correctly in Excel.
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
