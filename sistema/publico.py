"""Páginas públicas: formulário de solicitação, verificação de disponibilidade, acompanhamento, login, manual, resposta das áreas e avaliação."""
from __future__ import annotations

from .core import *  # noqa: F401,F403








def create_event_from_form(form):
    required = [
        "organizer_email", "start_date", "title", "start_time", "end_time", "department", "organizer_name",
        "audience", "expected_attendees", "description", "organizer_phone", "contact_email",
        "authorized_by", "cost_center", "event_category",
    ]
    missing = [field for field in required if not (form.get(field) or "").strip()]
    if missing:
        return None, "Preencha todos os campos obrigatórios."

    start_date = normalize_date(form.get("start_date"))
    if not start_date:
        return None, "Informe uma data válida para o evento."
    end_date, end_error = _validate_end_date(start_date, form.get("end_date"))
    if end_error:
        return None, end_error
    try:
        attendees = int(form.get("expected_attendees") or "")
        if attendees < 0:
            raise ValueError
    except ValueError:
        return None, "Informe um número válido de participantes."

    email = form.get("organizer_email", "").strip().lower()
    contact_email = form.get("contact_email", "").strip().lower()
    for value in (email, contact_email):
        if "@" not in value or "." not in value.split("@")[-1]:
            return None, "Informe um e-mail válido nos campos de contato."

    modes = [item for item in form.getlist("event_modes") if item in FORMATS]
    services = [item for item in form.getlist("support") if item in SUPPORT_OPTIONS]
    allowed_venues = set(venue_options())
    venues = [item for item in form.getlist("venues") if item in allowed_venues]
    requested_items = [item for item in form.getlist("requested_items") if item in REQUESTED_ITEM_OPTIONS]
    authorization = form.get("authorized_by", "").strip()
    event_type = form.get("event_category", "").strip()
    event_type_other = form.get("event_category_other", "").strip() or None
    if event_type not in EVENT_TYPES:
        return None, "Selecione a categoria do evento."
    if event_type == "Outro" and not event_type_other:
        return None, "Especifique a categoria do evento selecionando 'Outro'."
    if not modes:
        return None, "Selecione pelo menos uma opção na pergunta 7: tipo do evento."
    if not services:
        return None, "Selecione pelo menos uma opção na pergunta 8: serviços de apoio."
    if not venues:
        return None, "Selecione pelo menos uma opção na pergunta 9: local do evento."
    if not requested_items:
        return None, "Selecione pelo menos uma opção na pergunta 13: itens necessários."
    if authorization not in AUTHORIZATION_OPTIONS:
        return None, "Selecione quem autorizou o evento."

    support_other = form.get("support_other", "").strip() or None
    venue_other = form.get("venue_other", "").strip() or None
    items_other = form.get("items_other", "").strip() or None
    if "Outro" in services and not support_other:
        return None, "Especifique o outro serviço de apoio selecionado."
    if "Outro" in venues and not venue_other:
        return None, "Especifique o outro local selecionado."
    if "Outro" in requested_items and not items_other:
        return None, "Especifique o outro item selecionado."

    # Os horários do formulário são opções fixas de 30 em 30 minutos.
    start_time = form.get("start_time", "").strip()
    end_time = form.get("end_time", "").strip()
    if start_time not in TIME_OPTION_VALUES or end_time not in TIME_OPTION_VALUES:
        return None, "Selecione os horários de início e término nas opções disponíveis."
    start_minutes = _time_to_minutes(start_time)
    end_minutes = _time_to_minutes(end_time)
    if start_minutes is None or end_minutes is None or end_minutes <= start_minutes:
        return None, "O horário de término precisa ser posterior ao horário de início."

    # A disponibilidade é verificada no servidor imediatamente antes do cadastro.
    # Isso impede envio mesmo se a verificação dinâmica do navegador não for executada.
    db = get_db()
    # Reserva o lock de escrita antes da verificação para evitar dois envios concorrentes
    # aceitarem o mesmo espaço/horário ao mesmo tempo.
    db.execute("BEGIN IMMEDIATE")
    blockers = _conflicts_for_range(start_date, end_date, start_time, end_time, venues, venue_other, db=db)
    if blockers:
        db.rollback()
        return None, _reservation_conflict_message(blockers, multi_day=end_date != start_date)

    # Campos legados mantidos para compatibilidade com os registros anteriores do MVP.
    formatted_modes = ", ".join(modes)
    formatted_venues = "; ".join([v for v in venues if v != "Outro"] + ([venue_other] if "Outro" in venues and venue_other else []))
    protocol = f"FMABC-{date.today().year}-{secrets.token_hex(3).upper()}"
    created = now_iso()
    cursor = db.execute(
        """INSERT INTO events(
        protocol, title, department, organizer_name, organizer_email, organizer_phone,
        event_type, event_format, start_date, end_date, start_time, end_time,
        expected_attendees, venue, audience, description, support_json, event_modes_json,
        venues_json, requested_items_json, support_other, venue_other, items_other,
        contact_email, authorized_by, cost_center, additional_info, event_type_other,
        external_guests, accessibility, budget_source, partner, status, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'recebido', ?, ?)""",
        (protocol, form.get("title", "").strip(), form.get("department", "").strip(),
         form.get("organizer_name", "").strip(), email, form.get("organizer_phone", "").strip(),
         event_type, formatted_modes, start_date, end_date, start_time, end_time,
         attendees, formatted_venues or None, form.get("audience", "").strip(), form.get("description", "").strip(),
         json.dumps(services, ensure_ascii=False), json.dumps(modes, ensure_ascii=False),
         json.dumps(venues, ensure_ascii=False), json.dumps(requested_items, ensure_ascii=False),
         support_other, venue_other, items_other, contact_email, authorization,
         form.get("cost_center", "").strip(), form.get("additional_info", "").strip() or None,
         event_type_other, "Não informado", "Não informado", None, None, created, created),
    )
    db.commit()
    return {"id": cursor.lastrowid, "protocol": protocol}, None


@app.get("/solicitar")
def request_event():
    return render_template("request_form.html", submitted=False)


@app.post("/solicitar")
def submit_event_request():
    result, error = create_event_from_form(request.form)
    if error:
        flash(error, "error")
        return render_template("request_form.html", submitted=False, form=request.form), 400
    db = get_db()
    created = db.execute("SELECT * FROM events WHERE id=?", (result["id"],)).fetchone()
    queue_submission_confirmation(db, created)
    db.commit()
    dispatch_emails_async()
    return render_template("request_form.html", submitted=True, protocol=result["protocol"])


@app.get("/api/agenda/verificar-reserva")
def api_check_reservation_availability():
    """Read-only availability check used by the public request form."""
    start_date = normalize_date(request.args.get("start_date"))
    start_time = (request.args.get("start_time") or "").strip()
    end_time = (request.args.get("end_time") or "").strip()
    attendees = (request.args.get("expected_attendees") or "").strip()
    allowed_venues = set(venue_options())
    selected_venues = [v for v in request.args.getlist("venues") if v in allowed_venues]
    venue_other = (request.args.get("venue_other") or "").strip() or None

    if not start_date or not start_time or not end_time or not selected_venues:
        return jsonify({"ready": False, "conflict": False, "message": "Informe a data, o horário de início, o horário de término e pelo menos um local para verificar a disponibilidade."})
    if start_time not in TIME_OPTION_VALUES or end_time not in TIME_OPTION_VALUES:
        return jsonify({"ready": True, "valid_time": False, "conflict": False,
                        "message": "Selecione os horários de início e término nas opções disponíveis, em intervalos de 30 minutos."})
    start_minutes = _time_to_minutes(start_time)
    end_minutes = _time_to_minutes(end_time)
    if start_minutes is None or end_minutes is None or end_minutes <= start_minutes:
        return jsonify({"ready": True, "valid_time": False, "conflict": False,
                        "message": "O horário de término precisa ser posterior ao horário de início."})
    if "Outro" in selected_venues and not venue_other:
        return jsonify({"ready": False, "conflict": False, "message": "Informe o nome do local selecionando 'Outro' para verificar a disponibilidade."})

    end_date, end_error = _validate_end_date(start_date, request.args.get("end_date"))
    if end_error:
        return jsonify({"ready": True, "valid_time": False, "conflict": False, "message": end_error})
    blockers = _conflicts_for_range(start_date, end_date, start_time, end_time, selected_venues, venue_other, db=get_db())
    if blockers:
        return jsonify({"ready": True, "valid_time": True, "conflict": True,
                        "message": _reservation_conflict_message(blockers, multi_day=end_date != start_date),
                        "venues": sorted({item["venue"] for item in blockers})})
    capacity_warning = _venue_capacity_warning(selected_venues, attendees)
    if not _selected_venue_labels(selected_venues, venue_other):
        return jsonify({"ready": True, "valid_time": True, "conflict": False,
                        "message": "O local informado é externo ou não é gerenciado na agenda de espaços da FMABC. Confirme a disponibilidade diretamente com o responsável."})
    message = "Não foi encontrada outra reserva no mesmo local, data e horário. O evento ainda dependerá de análise e aprovação do Setor de Eventos."
    if capacity_warning:
        return jsonify({"ready": True, "valid_time": True, "conflict": False, "level": "warning",
                        "message": capacity_warning + " " + message})
    return jsonify({"ready": True, "valid_time": True, "conflict": False, "message": message})


@app.route("/acompanhar", methods=["GET", "POST"])
def track_request():
    result = None
    attempted = False
    if request.method == "POST":
        attempted = True
        limit_key = f"track:{request.remote_addr}"
        if _too_many_attempts(limit_key, 15):
            flash("Muitas consultas em pouco tempo. Aguarde 15 minutos e tente novamente.", "error")
            return render_template("tracking.html", result=None, attempted=False), 429
        protocol = request.form.get("protocol", "").strip().upper()
        email = request.form.get("email", "").strip().lower()
        result = get_db().execute(
            "SELECT id, protocol, title, start_date, end_date, status, created_at, updated_at FROM events WHERE protocol = ? AND lower(organizer_email) = ?",
            (protocol, email),
        ).fetchone()
        if not result:
            _register_attempt(limit_key)
    info_request = None
    if result and result["status"] == "aguardando_informacoes":
        info_request = get_db().execute("SELECT * FROM info_requests WHERE event_id=? AND status='aberta' ORDER BY id DESC LIMIT 1",
                                        (result["id"],)).fetchone()
    return render_template("tracking.html", result=result, attempted=attempted, info_request=info_request)


def _default_login_destination(role: str | None) -> str:
    """Staff users start in triage; administrators start at the executive dashboard."""
    return url_for("events_list", aba="triar") if role == "staff" else url_for("dashboard")


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        existing = get_db().execute(
            "SELECT id, email, role, is_active FROM users WHERE id = ?", (session.get("user_id"),)
        ).fetchone()
        if existing and existing["is_active"]:
            session["user_email"] = existing["email"]
            session["user_role"] = existing["role"]
            return redirect(_default_login_destination(existing["role"]))
        session.clear()
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        limit_keys = [f"login-ip:{request.remote_addr}", f"login-email:{email}"]
        if _too_many_attempts(limit_keys[0], 20) or _too_many_attempts(limit_keys[1], 5):
            flash("Muitas tentativas de acesso sem sucesso. Aguarde 15 minutos e tente novamente.", "error")
            return render_template("login.html"), 429
        user = get_db().execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if user and check_password_hash(user["password_hash"], password):
            for key in limit_keys:
                _clear_attempts(key)
            if not user["is_active"]:
                flash("Esta conta está bloqueada. Entre em contato com o administrador.", "error")
                return render_template("login.html"), 403
            session.clear()
            session["user_id"] = user["id"]
            session["user_email"] = user["email"]
            session["user_role"] = user["role"]
            session["_csrf"] = secrets.token_urlsafe(32)
            # Staff accounts always start in triage, including when a stale `next`
            # parameter points to another page. Administrators may continue to the
            # requested internal page when the URL is local and safe.
            if user["role"] == "staff":
                return redirect(url_for("events_list", aba="triar"))
            next_url = request.args.get("next", "")
            if next_url.startswith("/") and not next_url.startswith("//") and "\\" not in next_url:
                return redirect(next_url)
            return redirect(_default_login_destination(user["role"]))
        for key in limit_keys:
            _register_attempt(key)
        flash("E-mail ou senha inválidos.", "error")
    return render_template("login.html")


@app.post("/logout")
@login_required
def logout():
    session.clear()
    flash("Você saiu do sistema.", "success")
    return redirect(url_for("login"))


@app.get("/manual")
def manual_center():
    """Consulta pública do manual: recupera somente trechos do documento institucional."""
    question = (request.args.get("q") or "").strip()[:350]
    results = search_manual(question) if question else []
    if not question:
        answer_message = "Faça uma pergunta para localizar as orientações correspondentes no manual."
    elif results:
        answer_message = "Encontrei os seguintes trechos no Manual de Cerimonial e Eventos da FMABC. As citações abaixo são passagens do documento original; consulte a página indicada para ler o contexto completo."
    else:
        answer_message = "Não encontrei trechos suficientes no manual para responder com segurança a essa pergunta. Tente usar termos mais próximos dos utilizados no documento ou consulte o manual completo."
    index_info = load_manual_index()
    return render_template(
        "manual.html",
        question=question,
        manual_results=results,
        answer_message=answer_message,
        manual_title=index_info.get("title", "Manual de Cerimonial e Eventos FMABC"),
        manual_year=index_info.get("version_year", 2023),
        manual_pages=index_info.get("pdf_pages", 67),
        manual_pdf_url=url_for("static", filename="docs/manual_cerimonial_eventos_fmabc_2023.pdf"),
    )


def _reservation_conflict_message(blockers, multi_day=False):
    if multi_day:
        days = sorted({item["date"] for item in blockers if item.get("date")})
        if days:
            dates = ", ".join(f"{d[8:10]}/{d[5:7]}" for d in days[:6]) + ("…" if len(days) > 6 else "")
            seen, unique = set(), []
            for item in blockers:
                marker = (item["venue"], item["kind"], item.get("reason"))
                if marker not in seen:
                    seen.add(marker)
                    unique.append(item)
            return f"Conflito em {len(days)} dia(s) do período ({dates}). " + _reservation_conflict_message(unique)
    confirmed = sorted({item["venue"] for item in blockers if item["kind"] == "conflito"})
    unresolved = sorted({item["venue"] for item in blockers if item["kind"] == "horario_indefinido"})
    parts = []
    if confirmed:
        spaces = ", ".join(f'“{name}”' for name in confirmed)
        noun = "O espaço" if len(confirmed) == 1 else "Os espaços"
        verb = "já está reservado" if len(confirmed) == 1 else "já estão reservados"
        parts.append(f"{noun} {spaces} {verb} nesta data e horário para outro evento. Escolha outra data, horário ou local antes de enviar o formulário.")
    for item in blockers:
        if item["kind"] == "bloqueio":
            parts.append(f'O espaço “{item["venue"]}” está indisponível nesta data/horário ({item.get("reason") or "bloqueio do Setor de Eventos"}). Escolha outro local ou data.')
    if unresolved:
        spaces = ", ".join(f'“{name}”' for name in unresolved)
        parts.append(f"Já existe uma reserva ou solicitação para {spaces} nesta data, mas o horário de início ou término está ausente/incompleto. Para evitar sobreposição, confirme a disponibilidade com o Setor de Eventos ou escolha outro local/data antes de enviar.")
    return " ".join(parts) or "Existe um possível conflito de reserva. Escolha outro local, data ou horário."


@app.route("/confirmar-area/<token>", methods=["GET", "POST"])
def department_response(token):
    if not re.fullmatch(r"[A-Za-z0-9_-]{24,80}", token or ""):
        abort(404)
    db = get_db()
    row = db.execute("""SELECT u.*,e.title event_title,e.protocol,e.start_date,e.start_time,e.end_time,e.venue,
        d.name department_name FROM event_department_updates u
        JOIN events e ON e.id=u.event_id JOIN departments d ON d.id=u.department_id
        WHERE u.response_token=?""", (token,)).fetchone()
    if not row:
        abort(404)

    if request.method == "POST":
        response = (request.form.get("response_status") or "").strip()
        task_status = (request.form.get("task_status") or "nao_iniciada").strip()
        response_by = (request.form.get("response_by") or "").strip()[:120]
        area_responsible = (request.form.get("area_responsible") or "").strip()[:120] or None
        response_notes = (request.form.get("response_notes") or "").strip()[:1500] or None
        pending_reason = (request.form.get("pending_reason") or "").strip()[:1500] or None
        receipt_confirmed = request.form.get("receipt_confirmed") == "yes"

        if not receipt_confirmed:
            flash("Confirme o recebimento da solicitação para registrar a resposta.", "error")
            return redirect(url_for("department_response", token=token))
        if not response_by:
            flash("Informe o nome de quem está respondendo pela área.", "error")
            return redirect(url_for("department_response", token=token))
        if response not in {"recebido", "confirmado", "nao_podera_atender", "precisa_alinhar", "ciente"}:
            flash("Selecione uma resposta válida.", "error")
            return redirect(url_for("department_response", token=token))
        if task_status not in DEPARTMENT_TASK_STATUSES:
            flash("Selecione um status de providência válido.", "error")
            return redirect(url_for("department_response", token=token))
        needs_reason = task_status in {"aguardando_terceiro", "bloqueada"} or response in {"precisa_alinhar", "nao_podera_atender"}
        if needs_reason and not pending_reason:
            flash("Explique a pendência ou o impedimento para que o Setor de Eventos possa acompanhar.", "error")
            return redirect(url_for("department_response", token=token))

        old = _department_task_snapshot(row)
        stamp = now_iso()
        db.execute("""UPDATE event_department_updates SET response_status=?,response_notes=?,response_by=?,responded_at=?,
            receipt_confirmed_at=COALESCE(receipt_confirmed_at,?),receipt_confirmed_by=COALESCE(receipt_confirmed_by,?),
            area_responsible=?,task_status=?,task_updated_at=?,task_updated_by=?,pending_reason=? WHERE id=?""",
            (response,response_notes,response_by,stamp,stamp,response_by,area_responsible,task_status,stamp,response_by,pending_reason,row["id"]))
        updated = db.execute("SELECT * FROM event_department_updates WHERE id=?", (row["id"],)).fetchone()
        _record_department_task_history(db,row["id"],row["event_id"],row["department_id"],old,
            _department_task_snapshot(updated),response_by,"Área de apoio","Resposta/atualização da providência")
        db.commit()
        flash("Recebimento e situação da providência registrados. Obrigado por atualizar o Setor de Eventos.", "success")
        return redirect(url_for("department_response",token=token,saved="1"))

    return render_template("department_response.html", update=row, saved=request.args.get("saved")=="1",
        area_tasks=[], task_statuses=DEPARTMENT_TASK_STATUSES)


@app.route("/avaliacao-evento/<token>", methods=["GET", "POST"])
def public_event_evaluation(token):
    db = get_db()
    evaluation = db.execute(
        "SELECT ev.*, e.title AS event_title, e.protocol, e.start_date FROM event_evaluations ev JOIN events e ON e.id=ev.event_id WHERE ev.token=?",
        (token,),
    ).fetchone()
    if not evaluation:
        abort(404)
    submitted = False
    if request.method == "POST":
        if evaluation["responded_at"]:
            submitted = True
        else:
            rating_fields = ["rating_overall", "rating_sector", "rating_communication", "rating_responsiveness", "rating_needs_met"]
            ratings = {}
            try:
                for field in rating_fields:
                    value = int(request.form.get(field, ""))
                    if value not in {1, 2, 3, 4, 5}:
                        raise ValueError
                    ratings[field] = value
            except ValueError:
                flash("Selecione uma nota de 1 a 5 em todas as perguntas de avaliação.", "error")
                return render_template("evaluation_public.html", evaluation=evaluation, submitted=False), 400
            db.execute(
                """UPDATE event_evaluations SET rating_overall=?, rating_sector=?, rating_communication=?,
                   rating_responsiveness=?, rating_needs_met=?, positive_feedback=?, improvement_suggestions=?,
                   additional_comments=?, responded_at=? WHERE id=? AND responded_at IS NULL""",
                (ratings["rating_overall"], ratings["rating_sector"], ratings["rating_communication"],
                 ratings["rating_responsiveness"], ratings["rating_needs_met"],
                 request.form.get("positive_feedback", "").strip() or None,
                 request.form.get("improvement_suggestions", "").strip() or None,
                 request.form.get("additional_comments", "").strip() or None,
                 now_iso(), evaluation["id"]),
            )
            db.commit()
            submitted = True
    return render_template("evaluation_public.html", evaluation=evaluation, submitted=submitted)


__all__ = [name for name in dict(globals()) if not name.startswith("__")]
