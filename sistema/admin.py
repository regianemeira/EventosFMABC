"""Administração: cadastros de apoio, equipe e acessos, espaços e bloqueios."""
from __future__ import annotations

from .core import *  # noqa: F401,F403


def _forget_venue_cache() -> None:
    for key in ("_venue_rows_active", "_venue_rows_all", "_venue_alias_map", "_venue_unmanaged"):
        g.pop(key, None)


@app.route("/cadastros-apoio", methods=["GET", "POST"])
@login_required
def support_catalog_management():
    if session.get("user_role") != "admin":
        abort(404)
    db = get_db()
    categories = ["Materiais", "Infraestrutura", "Comunicação", "Credenciamento", "Logística", "Fornecedores", "Outro"]
    if request.method == "POST":
        action = request.form.get("action", "create")
        if action == "toggle":
            catalog_id = request.form.get("catalog_id", type=int)
            row = db.execute("SELECT * FROM support_catalog WHERE id = ?", (catalog_id,)).fetchone()
            if row:
                db.execute("UPDATE support_catalog SET active = ?, updated_at = ? WHERE id = ?", (0 if row["active"] else 1, now_iso(), catalog_id))
                db.commit()
                flash("Cadastro ativado/inativado.", "success")
            return redirect(url_for("support_catalog_management"))
        name = request.form.get("name", "").strip()
        status = request.form.get("status", "Precisa confirmar")
        try:
            quantity = int(request.form.get("quantity")) if (request.form.get("quantity") or "").strip() else None
            if quantity is not None and quantity < 0:
                raise ValueError
        except ValueError:
            quantity = -1
        if not name:
            flash("Informe o nome do item ou recurso.", "error")
        elif status not in SUPPORT_CATALOG_STATUSES:
            flash("Status do cadastro inválido.", "error")
        elif quantity == -1:
            flash("A quantidade deve ser um número igual ou maior que zero.", "error")
        else:
            values = (name[:180], request.form.get("category", "Outro")[:80], quantity,
                      request.form.get("location", "").strip()[:240] or None, status,
                      request.form.get("notes", "").strip()[:2000] or None)
            if action == "update":
                catalog_id = request.form.get("catalog_id", type=int)
                db.execute("""UPDATE support_catalog SET name=?, category=?, quantity=?, location=?, status=?, notes=?, updated_at=? WHERE id=?""",
                           (*values, now_iso(), catalog_id))
                flash("Cadastro atualizado.", "success")
            else:
                db.execute("""INSERT INTO support_catalog(name, category, quantity, location, status, notes, active, updated_at)
                           VALUES (?, ?, ?, ?, ?, ?, 1, ?)""", (*values, now_iso()))
                flash("Item adicionado ao cadastro de apoio.", "success")
            db.commit()
            return redirect(url_for("support_catalog_management"))
    records = db.execute("SELECT * FROM support_catalog ORDER BY active DESC, category, name").fetchall()
    return render_template("support_catalog.html", records=records, categories=categories)


@app.route("/espacos", methods=["GET", "POST"])
@login_required
def venue_management():
    """Cadastro de espaços: capacidade, recursos, apelidos e bloqueios de agenda."""
    if session.get("user_role") != "admin":
        abort(404)
    db = get_db()
    if request.method == "POST":
        action = request.form.get("action", "create")
        venue_id = request.form.get("venue_id", type=int)
        venue = db.execute("SELECT * FROM venues WHERE id=?", (venue_id,)).fetchone() if venue_id else None
        anchor = f"#venue-{venue_id}" if venue_id else ""
        if action in {"update", "toggle", "add_block", "delete_block"} and not venue:
            flash("Espaço não encontrado.", "error")
            return redirect(url_for("venue_management"))

        if action == "toggle":
            db.execute("UPDATE venues SET active=?, updated_at=? WHERE id=?", (0 if venue["active"] else 1, now_iso(), venue_id))
            db.commit()
            flash("Espaço ativado." if not venue["active"] else "Espaço inativado: ele deixa de aparecer nos formulários, mas os eventos antigos são mantidos.", "success")
            return redirect(url_for("venue_management") + anchor)

        if action == "delete_block":
            db.execute("DELETE FROM venue_blocks WHERE id=? AND venue_id=?", (request.form.get("block_id", type=int), venue_id))
            db.commit()
            flash("Bloqueio removido.", "success")
            return redirect(url_for("venue_management") + anchor)

        if action == "add_block":
            start = normalize_date(request.form.get("block_start_date"))
            end = normalize_date(request.form.get("block_end_date") or request.form.get("block_start_date"))
            start_time = (request.form.get("block_start_time") or "").strip() or None
            end_time = (request.form.get("block_end_time") or "").strip() or None
            reason = (request.form.get("block_reason") or "").strip()[:240]
            if not start or not end or end < start:
                flash("Informe datas válidas para o bloqueio (o término não pode ser antes do início).", "error")
            elif not reason:
                flash("Informe o motivo do bloqueio (ex.: manutenção do ar-condicionado).", "error")
            elif (start_time or end_time) and not (start_time in TIME_OPTION_VALUES and end_time in TIME_OPTION_VALUES and _time_to_minutes(end_time) > _time_to_minutes(start_time)):
                flash("Para bloquear só parte do dia, informe início e término válidos; deixe ambos vazios para bloquear o dia inteiro.", "error")
            else:
                db.execute("""INSERT INTO venue_blocks(venue_id,start_date,end_date,start_time,end_time,reason,created_by,created_at)
                              VALUES (?,?,?,?,?,?,?,?)""", (venue_id, start, end, start_time, end_time, reason, session.get("user_email"), now_iso()))
                db.commit()
                in_period = db.execute("""SELECT * FROM events WHERE status<>'cancelado'
                                          AND start_date<=? AND COALESCE(NULLIF(end_date,''),start_date)>=? ORDER BY start_date""", (end, start)).fetchall()
                key = _normalize_venue_key(venue["name"])
                affected = [e for e in in_period if key in _event_venue_keys(e)]
                flash("Bloqueio registrado. Novas solicitações nesse período serão recusadas para este espaço.", "success")
                if affected:
                    flash(f"Atenção: {len(affected)} evento(s) já cadastrado(s) usam este espaço no período bloqueado: " + "; ".join(f"{e['title']} ({e['start_date'][8:10]}/{e['start_date'][5:7]})" for e in affected[:5]), "warning")
            return redirect(url_for("venue_management") + anchor)

        name = (request.form.get("name") or "").strip()[:160]
        try:
            capacity = int(request.form.get("capacity")) if (request.form.get("capacity") or "").strip() else None
            if capacity is not None and capacity < 0:
                raise ValueError
        except ValueError:
            flash("A capacidade deve ser um número inteiro.", "error")
            return redirect(url_for("venue_management") + anchor)
        if not name:
            flash("Informe o nome do espaço.", "error")
            return redirect(url_for("venue_management") + anchor)
        aliases = "\n".join(_split_field_options(request.form.get("aliases")))
        fields = (name, capacity, (request.form.get("building") or "").strip()[:160] or None,
                  (request.form.get("resources") or "").strip()[:1500] or None,
                  (request.form.get("accessibility") or "").strip()[:500] or None,
                  1 if request.form.get("managed") else 0, (request.form.get("notes") or "").strip()[:1500] or None)
        try:
            if action == "update":
                if venue["name"].strip().casefold() != name.casefold():
                    # Mantém o nome antigo como apelido para os eventos já registrados continuarem reconhecidos.
                    old_labels = [venue["name"], venue_label(venue)]
                    aliases = "\n".join(dict.fromkeys([a for a in aliases.split("\n") if a] + old_labels))
                db.execute("""UPDATE venues SET name=?, capacity=?, building=?, resources=?, accessibility=?, managed=?, notes=?,
                              aliases=?, updated_at=? WHERE id=?""", (*fields, aliases or None, now_iso(), venue_id))
                flash("Espaço atualizado.", "success")
            else:
                order = db.execute("SELECT COALESCE(MAX(sort_order),0)+1 FROM venues").fetchone()[0]
                db.execute("""INSERT INTO venues(name, capacity, building, resources, accessibility, managed, notes, aliases,
                              active, sort_order, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,1,?,?,?)""",
                           (*fields, aliases or None, order, now_iso(), now_iso()))
                flash("Espaço cadastrado. Ele já aparece no formulário de solicitação.", "success")
            db.commit()
        except sqlite3.IntegrityError:
            flash("Já existe um espaço com esse nome.", "error")
        _forget_venue_cache()
        return redirect(url_for("venue_management") + anchor)

    _forget_venue_cache()
    venues = _venue_rows(active_only=False)
    today = date.today().isoformat()
    blocks_by_venue = {}
    for block in db.execute("SELECT * FROM venue_blocks WHERE end_date>=? ORDER BY start_date, start_time", (today,)).fetchall():
        blocks_by_venue.setdefault(block["venue_id"], []).append(block)
    upcoming_by_key = {}
    horizon = (date.today() + timedelta(days=90)).isoformat()
    for event in db.execute("""SELECT * FROM events WHERE status NOT IN ('cancelado','encerrado','realizado')
                               AND COALESCE(NULLIF(end_date,''),start_date)>=? AND start_date<=? ORDER BY start_date, start_time""",
                            (today, horizon)).fetchall():
        for key in _event_venue_keys(event):
            upcoming_by_key.setdefault(key, []).append(event)
    unmatched = {}
    known_keys = {_normalize_venue_key(v["name"]) for v in venues}
    for event in db.execute("SELECT * FROM events WHERE status<>'cancelado'").fetchall():
        for key in _event_venue_keys(event):
            if key not in known_keys:
                unmatched.setdefault(_venue_label_for_key(event, key), 0)
                unmatched[_venue_label_for_key(event, key)] += 1
    return render_template("venues.html", venues=venues, blocks_by_venue=blocks_by_venue,
                           upcoming_by_venue={v["id"]: upcoming_by_key.get(_normalize_venue_key(v["name"]), []) for v in venues},
                           unmatched=sorted(unmatched.items(), key=lambda x: -x[1]))


@app.route("/equipe", methods=["GET", "POST"])
@login_required
def team_management():
    if session.get("user_role") != "admin":
        abort(404)
    db = get_db()
    if request.method == "POST":
        action = (request.form.get("action") or "create").strip()
        target_id = request.form.get("user_id", type=int)
        target = db.execute("SELECT * FROM users WHERE id = ?", (target_id,)).fetchone() if target_id else None

        if action == "create":
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")
            role = request.form.get("role", "staff")
            if "@" not in email or "." not in email.split("@")[-1]:
                flash("Informe um e-mail válido.", "error")
            elif len(password) < 6:
                flash("A senha deve ter pelo menos 6 caracteres.", "error")
            elif role not in {"staff", "admin"}:
                flash("Perfil de acesso inválido.", "error")
            else:
                try:
                    db.execute("INSERT INTO users(email, password_hash, role, is_active, created_at) VALUES (?, ?, ?, 1, ?)",
                               (email, generate_password_hash(password), role, now_iso()))
                    db.commit()
                    flash("Acesso criado. No primeiro login, o perfil Equipe abre diretamente Triagem e acompanhamento.", "success")
                    return redirect(url_for("team_management"))
                except sqlite3.IntegrityError:
                    flash("Já existe um usuário cadastrado com esse e-mail.", "error")

        elif action == "update":
            if not target:
                flash("Usuário não encontrado.", "error")
            else:
                email = (request.form.get("email") or "").strip().lower()
                role = request.form.get("role", "staff")
                if "@" not in email or "." not in email.split("@")[-1]:
                    flash("Informe um e-mail válido.", "error")
                elif role not in {"staff", "admin"}:
                    flash("Perfil de acesso inválido.", "error")
                elif target["id"] == session.get("user_id") and role != "admin":
                    flash("Você não pode remover seu próprio perfil de administrador. Outro administrador deve realizar essa alteração.", "error")
                elif target["role"] == "admin" and target["is_active"] and role != "admin" and db.execute("SELECT COUNT(*) FROM users WHERE role='admin' AND is_active=1").fetchone()[0] <= 1:
                    flash("Não é possível retirar o perfil do último administrador ativo.", "error")
                else:
                    try:
                        db.execute("UPDATE users SET email=?, role=? WHERE id=?", (email, role, target_id))
                        db.commit()
                        if target_id == session.get("user_id"):
                            session["user_email"] = email
                            session["user_role"] = role
                        flash("Cadastro do usuário atualizado.", "success")
                    except sqlite3.IntegrityError:
                        flash("Já existe outro usuário com esse e-mail.", "error")

        elif action == "change_password":
            password = request.form.get("new_password", "")
            confirmation = request.form.get("confirm_password", "")
            if not target:
                flash("Usuário não encontrado.", "error")
            elif len(password) < 6:
                flash("A senha deve ter pelo menos 6 caracteres.", "error")
            elif password != confirmation:
                flash("A confirmação da senha não corresponde.", "error")
            else:
                db.execute("UPDATE users SET password_hash=? WHERE id=?", (generate_password_hash(password), target_id))
                db.commit()
                flash("Senha redefinida. Compartilhe a nova senha por um canal seguro.", "success")

        elif action == "toggle_active":
            if not target:
                flash("Usuário não encontrado.", "error")
            elif target_id == session.get("user_id"):
                flash("Você não pode bloquear sua própria conta enquanto está usando o sistema.", "error")
            elif target["role"] == "admin" and target["is_active"] and db.execute("SELECT COUNT(*) FROM users WHERE role='admin' AND is_active=1").fetchone()[0] <= 1:
                flash("Não é possível bloquear o último administrador ativo.", "error")
            else:
                new_value = 0 if target["is_active"] else 1
                db.execute("UPDATE users SET is_active=? WHERE id=?", (new_value, target_id))
                db.commit()
                flash("Conta bloqueada." if not new_value else "Conta desbloqueada.", "success")

        elif action == "delete":
            if not target:
                flash("Usuário não encontrado.", "error")
            elif target_id == session.get("user_id"):
                flash("Você não pode excluir sua própria conta enquanto está usando o sistema.", "error")
            elif target["role"] == "admin" and target["is_active"] and db.execute("SELECT COUNT(*) FROM users WHERE role='admin' AND is_active=1").fetchone()[0] <= 1:
                flash("Não é possível excluir o último administrador ativo.", "error")
            else:
                db.execute("DELETE FROM users WHERE id=?", (target_id,))
                db.commit()
                flash("Conta excluída.", "success")
        else:
            flash("Ação de administração não reconhecida.", "error")
        return redirect(url_for("team_management"))

    users = db.execute("SELECT id, email, role, is_active, created_at FROM users ORDER BY is_active DESC, created_at, email").fetchall()
    active_admins = db.execute("SELECT COUNT(*) FROM users WHERE role='admin' AND is_active=1").fetchone()[0]
    return render_template("team.html", users=users, active_admins=active_admins)


__all__ = [name for name in dict(globals()) if not name.startswith("__")]
