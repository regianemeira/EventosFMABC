"""Núcleo do sistema: configuração, banco de dados, constantes e funções compartilhadas.

Os módulos de rotas importam tudo daqui com `from .core import *`.
"""
from __future__ import annotations

import io

import csv

import calendar as pycalendar

import json

import re

import os

import secrets

import sqlite3

import smtplib

import threading

import time

import logging

import unicodedata

from logging.handlers import RotatingFileHandler

from email.message import EmailMessage

from datetime import date, datetime, timedelta

from functools import wraps

from pathlib import Path

from urllib.parse import urlparse

from flask import Flask, Response, abort, flash, g, has_app_context, has_request_context, jsonify, redirect, render_template, request, send_file, session, url_for

from werkzeug.security import check_password_hash, generate_password_hash

from manual_search import load_index as load_manual_index, search_manual

from . import db as _dbcompat

BASE_DIR = Path(__file__).resolve().parent.parent

INSTANCE_DIR = BASE_DIR / "instance"

INSTANCE_DIR.mkdir(exist_ok=True)

def load_dotenv(path: Path) -> None:
    """Small .env reader to keep local setup dependency-free."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value

load_dotenv(BASE_DIR / ".env")

DB_PATH = Path(os.getenv("DATABASE_PATH") or str(INSTANCE_DIR / "fmabc_eventos.db")).resolve()

DB_PATH.parent.mkdir(parents=True, exist_ok=True)

# DB_PATH só é usado quando DATABASE_URL não está definida (veja sistema/db.py).
# Com DATABASE_URL apontando para um PostgreSQL (ex.: Neon), o sistema ignora
# DB_PATH e passa a gravar tudo no banco remoto — essencial para hospedar no
# Render sem perder dados a cada novo deploy.

app = Flask(__name__, root_path=str(BASE_DIR))

app.config.update(
    SECRET_KEY=os.getenv("SECRET_KEY") or secrets.token_hex(32),
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.getenv("COOKIE_SECURE", "0").lower() in {"1", "true", "yes"},
    MAX_CONTENT_LENGTH=16 * 1024 * 1024,
)

# Registro de erros em arquivo (instance/erros.log), útil para diagnosticar problemas sem depender do terminal.
_error_handler = RotatingFileHandler(INSTANCE_DIR / "erros.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8")

_error_handler.setLevel(logging.ERROR)

_error_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))

app.logger.addHandler(_error_handler)

# Limite simples de tentativas (em memória) para login e consulta pública de protocolo.
_ATTEMPTS: dict[str, list[float]] = {}

_ATTEMPTS_LOCK = threading.Lock()


def _too_many_attempts(key: str, limit: int, window_seconds: int = 900) -> bool:
    now = time.time()
    with _ATTEMPTS_LOCK:
        recent = [t for t in _ATTEMPTS.get(key, []) if now - t < window_seconds]
        _ATTEMPTS[key] = recent
        return len(recent) >= limit


def _register_attempt(key: str) -> None:
    with _ATTEMPTS_LOCK:
        _ATTEMPTS.setdefault(key, []).append(time.time())


def _clear_attempts(key: str) -> None:
    with _ATTEMPTS_LOCK:
        _ATTEMPTS.pop(key, None)


def _cleanup_import_previews(max_age_hours: int = 24) -> None:
    """Apaga prévias de importação antigas (contêm nomes e contatos da planilha)."""
    folder = INSTANCE_DIR / "import_previews"
    if not folder.exists():
        return
    limit = time.time() - max_age_hours * 3600
    for item in folder.glob("*.json"):
        try:
            if item.stat().st_mtime < limit:
                item.unlink()
        except OSError:
            pass

STATUS_LABELS = {
    "recebido": "Solicitação recebida",
    "em_triagem": "Em triagem",
    "aguardando_informacoes": "Aguardando informações",
    "aprovado": "Aprovado",
    "em_planejamento": "Em planejamento",
    "realizado": "Realizado (pós-evento pendente)",
    "encerrado": "Encerrado",
    "cancelado": "Cancelado",
}

STATUS_CLASSES = {
    "recebido": "status-blue",
    "em_triagem": "status-purple",
    "aguardando_informacoes": "status-amber",
    "aprovado": "status-green",
    "em_planejamento": "status-teal",
    "realizado": "status-gray",
    "encerrado": "status-green",
    "cancelado": "status-red",
}

EVENT_TYPES = [
    "Congresso / Simpósio", "Aula / Atividade acadêmica", "Cerimônia / Colação de grau",
    "Evento institucional", "Palestra / Mesa-redonda", "Curso / Oficina", "Visita institucional",
    "Reunião", "Inauguração / Lançamento", "Premiação / Homenagem", "Outro",
]

TASK_STATUSES = {
    "pendente": "Não iniciada",
    "em_andamento": "Em andamento",
    "aguardando_terceiro": "Aguardando terceiro",
    "concluida": "Concluída",
    "nao_se_aplica": "Não se aplica",
}

TASK_DONE_STATUSES = {"concluida", "nao_se_aplica"}

SUPPORT_CATALOG_STATUSES = ["Disponível", "Parcial", "Em solicitação", "Não disponível", "Precisa confirmar", "Inativo"]

COMMUNICATION_ROLES = {"acao": "Ação necessária", "conhecimento": "Para conhecimento", "excluir": "Não incluir no comunicado"}

DEPARTMENT_RESPONSE_LABELS = {"aguardando": "Aguardando resposta", "recebido": "Recebido — em análise", "confirmado": "Confirmado pela área", "nao_podera_atender": "Não poderá atender", "precisa_alinhar": "Precisa alinhar", "ciente": "Ciente"}

DEPARTMENT_TASK_STATUSES = {
    "nao_iniciada": "Não iniciada",
    "em_andamento": "Em andamento",
    "aguardando_terceiro": "Aguardando terceiro",
    "bloqueada": "Bloqueada",
    "concluida": "Concluída",
}

DEPARTMENT_TASK_STATUS_LABELS = DEPARTMENT_TASK_STATUSES.copy()

DEPARTMENT_TASK_HISTORY_FIELDS = (
    ("involvement", "Participação da área"),
    ("details", "Providências solicitadas"),
    ("notes", "Observação interna"),
    ("area_responsible", "Responsável da área"),
    ("due_date", "Prazo da providência"),
    ("response_status", "Resposta da área"),
    ("receipt_confirmed_at", "Confirmação de recebimento"),
    ("task_status", "Status da providência"),
    ("pending_reason", "Justificativa da pendência"),
    ("response_notes", "Observações da área"),
)

DEFAULT_DEPARTMENTS = ["TI", "Inspetoria", "Limpeza", "Manutenção", "Imprensa"]

# Opções preservadas do Google Forms original da FMABC (PDF recebido em 20/10/2026).
FORMATS = ["Presencial", "On-line", "Híbrido"]

SUPPORT_OPTIONS = ["Manutenção", "Limpeza", "TI", "Inspetoria", "Outro"]

VENUE_OPTIONS = [
    "Administrativo - salas 5/7 e 6/8 - 60 lugares cada",
    "Auditório da Cardiologia - 40 lugares",
    "Auditório da Dermatologia - 78 lugares",
    "Auditório da Estética - 80 lugares",
    "Auditório da Morfologia - 130 lugares",
    "Auditório da Pós–Graduação - 316 lugares",
    "Auditório da Urologia - 45 lugares",
    "Auditório David Uip - 280 lugares",
    "Sala de videoconferência - 73 lugares",
    "Salão Nobre - 81 lugares",
    "Externo (Fora da FMABC)",
    "Outro",
]

REQUESTED_ITEM_OPTIONS = [
    "Brindes", "Certificado", "Coffee break", "Credencial", "Divulgação prévia",
    "Divulgação posterior", "Equipamentos de áudio visual para apresentação", "Gravação",
    "Inscrição prévia", "Mestre de Cerimônias", "Registro fotográfico",
    "Reserva de Estacionamento", "Transmissão Simultânea", "Outro",
]

AUTHORIZATION_OPTIONS = [
    "Reitoria", "Pró-Reitoria de Extensão", "Pró-Reitoria de Graduação",
    "Pró-Reitoria de Pós-Graduação",
]

# Slots fixos de 30 em 30 minutos para o formulário público de reserva.
# O valor armazenado permanece parseável pelos verificadores legados de horário.
TIME_OPTIONS = [
    (f"{hour:02d}h{minute:02d}", f"{hour:02d}h" if minute == 0 else f"{hour:02d}h30")
    for hour in range(24) for minute in (0, 30)
]

TIME_OPTION_VALUES = {value for value, _label in TIME_OPTIONS}

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL UNIQUE COLLATE NOCASE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'staff',
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    protocol TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    department TEXT NOT NULL,
    organizer_name TEXT NOT NULL,
    organizer_email TEXT NOT NULL,
    organizer_phone TEXT NOT NULL,
    event_type TEXT NOT NULL,
    event_format TEXT NOT NULL,
    start_date TEXT NOT NULL,
    end_date TEXT,
    start_time TEXT,
    end_time TEXT,
    expected_attendees INTEGER NOT NULL DEFAULT 0,
    venue TEXT,
    audience TEXT,
    description TEXT NOT NULL,
    support_json TEXT NOT NULL DEFAULT '[]',
    event_modes_json TEXT NOT NULL DEFAULT '[]',
    venues_json TEXT NOT NULL DEFAULT '[]',
    requested_items_json TEXT NOT NULL DEFAULT '[]',
    support_other TEXT,
    venue_other TEXT,
    items_other TEXT,
    contact_email TEXT,
    legacy_contact_reference TEXT,
    authorized_by TEXT,
    cost_center TEXT,
    additional_info TEXT,
    event_type_other TEXT,
    external_guests TEXT NOT NULL DEFAULT 'Não informado',
    accessibility TEXT NOT NULL DEFAULT 'Não informado',
    budget_source TEXT,
    partner TEXT,
    status TEXT NOT NULL DEFAULT 'recebido',
    priority TEXT NOT NULL DEFAULT 'Normal',
    internal_owner TEXT,
    internal_notes TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'Organização',
    due_date TEXT,
    status TEXT NOT NULL DEFAULT 'pendente',
    assigned_to TEXT,
    description TEXT,
    notes TEXT,
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    completed_at TEXT
);
CREATE TABLE IF NOT EXISTS task_templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'Planejamento',
    description TEXT,
    trigger_type TEXT NOT NULL DEFAULT 'always',
    trigger_value TEXT,
    due_offset INTEGER NOT NULL DEFAULT -7,
    assigned_to TEXT,
    active INTEGER NOT NULL DEFAULT 1,
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_task_templates_active ON task_templates(active, sort_order);
CREATE TABLE IF NOT EXISTS support_catalog (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'Material',
    quantity INTEGER,
    location TEXT,
    status TEXT NOT NULL DEFAULT 'Precisa confirmar',
    notes TEXT,
    active INTEGER NOT NULL DEFAULT 1,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_support_catalog_active ON support_catalog(active, category, name);
CREATE INDEX IF NOT EXISTS idx_events_status ON events(status);
CREATE INDEX IF NOT EXISTS idx_events_start_date ON events(start_date);
CREATE INDEX IF NOT EXISTS idx_tasks_event_id ON tasks(event_id);
CREATE TABLE IF NOT EXISTS departments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE COLLATE NOCASE,
    recipient_email TEXT,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_departments_active ON departments(active, name);
CREATE TABLE IF NOT EXISTS event_department_updates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    department_id INTEGER NOT NULL REFERENCES departments(id),
    involvement TEXT NOT NULL DEFAULT 'conhecimento',
    details TEXT,
    notes TEXT,
    updated_by TEXT,
    updated_at TEXT NOT NULL,
    response_status TEXT NOT NULL DEFAULT 'aguardando',
    response_notes TEXT,
    response_by TEXT,
    response_token TEXT,
    responded_at TEXT,
    receipt_confirmed_at TEXT,
    receipt_confirmed_by TEXT,
    area_responsible TEXT,
    due_date TEXT,
    task_status TEXT NOT NULL DEFAULT 'nao_iniciada',
    task_updated_at TEXT,
    task_updated_by TEXT,
    pending_reason TEXT,
    UNIQUE(event_id, department_id)
);
CREATE INDEX IF NOT EXISTS idx_event_department_updates_event ON event_department_updates(event_id);
CREATE TABLE IF NOT EXISTS department_task_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    update_id INTEGER NOT NULL REFERENCES event_department_updates(id) ON DELETE CASCADE,
    event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    department_id INTEGER NOT NULL REFERENCES departments(id),
    changed_at TEXT NOT NULL,
    changed_by TEXT,
    source TEXT NOT NULL DEFAULT 'interno',
    action TEXT NOT NULL,
    change_summary TEXT NOT NULL,
    before_json TEXT,
    after_json TEXT
);
CREATE INDEX IF NOT EXISTS idx_department_task_history_update ON department_task_history(update_id, changed_at DESC);
CREATE INDEX IF NOT EXISTS idx_department_task_history_event_department ON department_task_history(event_id, department_id, changed_at DESC);
CREATE TABLE IF NOT EXISTS communication_batches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    department_id INTEGER NOT NULL REFERENCES departments(id),
    period_year INTEGER NOT NULL,
    period_month INTEGER NOT NULL,
    subject TEXT NOT NULL,
    body TEXT NOT NULL,
    recipient_email TEXT,
    status TEXT NOT NULL DEFAULT 'rascunho',
    created_by TEXT,
    created_at TEXT NOT NULL,
    sent_at TEXT,
    sent_by TEXT,
    send_method TEXT,
    error_message TEXT
);
CREATE INDEX IF NOT EXISTS idx_communication_batches_period ON communication_batches(period_year, period_month, department_id, created_at);
CREATE TABLE IF NOT EXISTS communication_batch_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id INTEGER NOT NULL REFERENCES communication_batches(id) ON DELETE CASCADE,
    event_id INTEGER NOT NULL REFERENCES events(id),
    event_title TEXT NOT NULL,
    event_date TEXT NOT NULL,
    event_time TEXT,
    event_venue TEXT,
    involvement TEXT NOT NULL,
    details TEXT,
    UNIQUE(batch_id, event_id)
);
CREATE INDEX IF NOT EXISTS idx_communication_batch_events_batch ON communication_batch_events(batch_id);
CREATE TABLE IF NOT EXISTS event_closures (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id INTEGER NOT NULL UNIQUE REFERENCES events(id) ON DELETE CASCADE,
    actual_attendees INTEGER,
    summary TEXT NOT NULL,
    positives TEXT,
    issues TEXT,
    improvements TEXT,
    follow_up_actions TEXT,
    final_observations TEXT,
    closed_by TEXT,
    closed_at TEXT NOT NULL,
    updated_by TEXT,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_event_closures_closed_at ON event_closures(closed_at);
CREATE TABLE IF NOT EXISTS event_evaluations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id INTEGER NOT NULL UNIQUE REFERENCES events(id) ON DELETE CASCADE,
    token TEXT NOT NULL UNIQUE,
    requester_email TEXT NOT NULL,
    rating_overall INTEGER,
    rating_sector INTEGER,
    rating_communication INTEGER,
    rating_responsiveness INTEGER,
    rating_needs_met INTEGER,
    positive_feedback TEXT,
    improvement_suggestions TEXT,
    additional_comments TEXT,
    created_at TEXT NOT NULL,
    invitation_sent_at TEXT,
    invitation_method TEXT,
    responded_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_event_evaluations_responded_at ON event_evaluations(responded_at);
CREATE TABLE IF NOT EXISTS event_program_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    start_time TEXT NOT NULL,
    end_time TEXT,
    activity TEXT NOT NULL,
    location TEXT,
    responsible TEXT,
    notes TEXT,
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_event_program_items_event ON event_program_items(event_id, start_time, sort_order);
CREATE TABLE IF NOT EXISTS event_budget_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    item_name TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'Outros',
    supplier TEXT,
    estimated_amount REAL,
    actual_amount REAL,
    status TEXT NOT NULL DEFAULT 'previsto',
    notes TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_event_budget_items_event ON event_budget_items(event_id, category, item_name);
CREATE TABLE IF NOT EXISTS event_incidents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    incident_date TEXT,
    category TEXT NOT NULL DEFAULT 'Outro',
    title TEXT NOT NULL,
    impact TEXT,
    resolution TEXT,
    preventive_action TEXT,
    responsible TEXT,
    status TEXT NOT NULL DEFAULT 'aberta',
    recorded_by TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_event_incidents_event ON event_incidents(event_id, status, incident_date);
CREATE TABLE IF NOT EXISTS task_template_fields (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    template_id INTEGER NOT NULL REFERENCES task_templates(id) ON DELETE CASCADE,
    label TEXT NOT NULL,
    field_type TEXT NOT NULL DEFAULT 'text',
    options TEXT,
    required INTEGER NOT NULL DEFAULT 0,
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_task_template_fields ON task_template_fields(template_id, sort_order, id);
CREATE TABLE IF NOT EXISTS task_field_values (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    field_id INTEGER NOT NULL REFERENCES task_template_fields(id) ON DELETE CASCADE,
    value TEXT,
    updated_at TEXT NOT NULL,
    UNIQUE(task_id, field_id)
);
CREATE INDEX IF NOT EXISTS idx_task_field_values_task ON task_field_values(task_id);
CREATE TABLE IF NOT EXISTS event_budget_quotes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    budget_item_id INTEGER NOT NULL REFERENCES event_budget_items(id) ON DELETE CASCADE,
    supplier TEXT NOT NULL,
    quote_amount REAL NOT NULL,
    quote_date TEXT,
    valid_until TEXT,
    selected INTEGER NOT NULL DEFAULT 0,
    notes TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_event_budget_quotes_item ON event_budget_quotes(event_id, budget_item_id, quote_amount);
CREATE TABLE IF NOT EXISTS event_change_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    changed_at TEXT NOT NULL,
    changed_by TEXT,
    summary TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_event_change_log_event ON event_change_log(event_id, changed_at DESC);
CREATE TABLE IF NOT EXISTS venues (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE COLLATE NOCASE,
    capacity INTEGER,
    building TEXT,
    resources TEXT,
    accessibility TEXT,
    aliases TEXT,
    managed INTEGER NOT NULL DEFAULT 1,
    active INTEGER NOT NULL DEFAULT 1,
    sort_order INTEGER NOT NULL DEFAULT 0,
    notes TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_venues_active ON venues(active, sort_order, name);
CREATE TABLE IF NOT EXISTS venue_blocks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    venue_id INTEGER NOT NULL REFERENCES venues(id) ON DELETE CASCADE,
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    start_time TEXT,
    end_time TEXT,
    reason TEXT NOT NULL,
    created_by TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_venue_blocks_dates ON venue_blocks(start_date, end_date);
CREATE TABLE IF NOT EXISTS event_attachments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    original_name TEXT NOT NULL,
    stored_name TEXT NOT NULL UNIQUE,
    size_bytes INTEGER NOT NULL,
    category TEXT NOT NULL DEFAULT 'Outro',
    description TEXT,
    uploaded_by TEXT,
    uploaded_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_event_attachments_event ON event_attachments(event_id, uploaded_at DESC);
"""

BUDGET_CATEGORIES = ["Alimentação", "Estrutura", "Audiovisual", "Materiais", "Comunicação", "Transporte",
                     "Hospedagem", "Serviços", "Equipe / mão de obra", "Tecnologia", "Taxas", "Outros"]

BUDGET_STATUSES = {"previsto", "em_cotacao", "aprovado", "contratado", "realizado", "cancelado"}

BUDGET_APPROVAL_STATUSES = {"nao_solicitada", "pendente", "aprovada", "reprovada"}

TASK_FIELD_TYPES = {
    "text": "Texto curto", "textarea": "Texto longo", "select": "Lista de opções",
    "date": "Data", "number": "Número", "boolean": "Sim/Não",
}

def get_db():
    # Usa PostgreSQL se DATABASE_URL estiver definida (produção/Render), senão
    # SQLite no arquivo local de sempre. Veja sistema/db.py para os detalhes.
    if "db" not in g:
        g.db = _dbcompat.connect(DB_PATH)
    return g.db

@app.teardown_appcontext
def close_db(_error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()

def now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat(sep=" ")

def init_db() -> None:
    db = get_db()
    db.executescript(SCHEMA)
    # Atualiza bancos locais já criados em versões anteriores, sem apagar registros.
    existing_columns = {row["name"] for row in db.execute("PRAGMA table_info(events)").fetchall()}
    migrations = {
        "event_modes_json": "TEXT NOT NULL DEFAULT '[]'",
        "venues_json": "TEXT NOT NULL DEFAULT '[]'",
        "requested_items_json": "TEXT NOT NULL DEFAULT '[]'",
        "support_other": "TEXT",
        "venue_other": "TEXT",
        "items_other": "TEXT",
        "contact_email": "TEXT",
        "legacy_contact_reference": "TEXT",
        "authorized_by": "TEXT",
        "cost_center": "TEXT",
        "additional_info": "TEXT",
        "event_type_other": "TEXT",
    }
    for column, sql_type in migrations.items():
        if column not in existing_columns:
            db.execute(f"ALTER TABLE events ADD COLUMN {column} {sql_type}")
    user_columns = {row["name"] for row in db.execute("PRAGMA table_info(users)").fetchall()}
    if "is_active" not in user_columns:
        db.execute("ALTER TABLE users ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1")
    task_columns = {row["name"] for row in db.execute("PRAGMA table_info(tasks)").fetchall()}
    task_migrations = {"description": "TEXT", "notes": "TEXT", "template_id": "INTEGER"}
    for column, sql_type in task_migrations.items():
        if column not in task_columns:
            db.execute(f"ALTER TABLE tasks ADD COLUMN {column} {sql_type}")
    department_update_columns = {row["name"] for row in db.execute("PRAGMA table_info(event_department_updates)").fetchall()}
    department_update_migrations = {
        "response_status": "TEXT NOT NULL DEFAULT 'aguardando'", "response_notes": "TEXT",
        "response_by": "TEXT", "response_token": "TEXT", "responded_at": "TEXT",
        "receipt_confirmed_at": "TEXT", "receipt_confirmed_by": "TEXT",
        "area_responsible": "TEXT", "due_date": "TEXT",
        "task_status": "TEXT NOT NULL DEFAULT 'nao_iniciada'", "task_updated_at": "TEXT",
        "task_updated_by": "TEXT", "pending_reason": "TEXT",
    }
    for column, sql_type in department_update_migrations.items():
        if column not in department_update_columns:
            db.execute(f"ALTER TABLE event_department_updates ADD COLUMN {column} {sql_type}")
    # Fase 3 — campos financeiros adicionais (migração aditiva, não apaga despesas antigas).
    budget_columns = {row["name"] for row in db.execute("PRAGMA table_info(event_budget_items)").fetchall()}
    budget_migrations = {
        "contracted_amount": "REAL", "approval_status": "TEXT NOT NULL DEFAULT 'nao_solicitada'",
        "approved_by": "TEXT", "approved_at": "TEXT", "cost_center": "TEXT",
        "purchase_order": "TEXT", "invoice_reference": "TEXT",
    }
    for column, sql_type in budget_migrations.items():
        if column not in budget_columns:
            db.execute(f"ALTER TABLE event_budget_items ADD COLUMN {column} {sql_type}")
    db.execute("CREATE INDEX IF NOT EXISTS idx_tasks_template ON tasks(template_id)")
    # Fase 2 — associa tarefas antigas ao modelo de mesmo título e categoria.
    db.execute("""UPDATE tasks SET template_id = (
            SELECT tt.id FROM task_templates tt
            WHERE lower(trim(tt.title)) = lower(trim(tasks.title))
              AND lower(trim(tt.category)) = lower(trim(tasks.category))
            ORDER BY tt.id LIMIT 1)
        WHERE template_id IS NULL""")
    db.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_event_department_response_token ON event_department_updates(response_token)")
    # Vínculos de providência antigos também recebem um token individual para retorno seguro.
    legacy_area_rows = db.execute("SELECT id FROM event_department_updates WHERE involvement='acao' AND (response_token IS NULL OR response_token='')").fetchall()
    for legacy_row in legacy_area_rows:
        db.execute("UPDATE event_department_updates SET response_token=? WHERE id=?", (secrets.token_urlsafe(32), legacy_row["id"]))
    db.commit()
    seed_task_templates(db)
    seed_support_catalog(db)
    seed_departments(db)
    seed_venues(db)
    init_comunicacao_schema(db)
    init_checklist_schema(db)
    log_columns = {row["name"] for row in db.execute("PRAGMA table_info(event_change_log)").fetchall()}
    if "kind" not in log_columns:
        db.execute("ALTER TABLE event_change_log ADD COLUMN kind TEXT NOT NULL DEFAULT 'edicao'")
        db.commit()
    current = db.execute("SELECT id FROM users LIMIT 1").fetchone()
    if not current:
        email = os.getenv("ADMIN_EMAIL", "eventos@fmabc.br").strip().lower()
        password = os.getenv("ADMIN_PASSWORD")
        generated = not password
        if generated:
            password = secrets.token_urlsafe(14)
        elif len(password) < 6:
            raise RuntimeError("ADMIN_PASSWORD deve ter pelo menos 6 caracteres para criar a conta administrativa inicial.")
        db.execute(
            "INSERT INTO users(email, password_hash, role, created_at) VALUES (?, ?, 'admin', ?)",
            (email, generate_password_hash(password), now_iso()),
        )
        db.commit()
        print("\n[FMABC Eventos] Usuário administrativo inicial criado.")
        print(f"E-mail: {email}")
        print(f"Senha inicial: {password}")
        print("Defina ADMIN_PASSWORD e SECRET_KEY no .env antes de usar em ambiente institucional.\n")

EXTERNAL_VENUE = "Externo (Fora da FMABC)"

ATTACHMENT_DIR = Path(os.getenv("FMABC_ANEXOS_DIR") or (INSTANCE_DIR / "anexos"))

ATTACHMENT_MAX_BYTES = 15 * 1024 * 1024

ATTACHMENT_EXTENSIONS = {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".csv", ".ppt", ".pptx", ".odt", ".ods",
                         ".txt", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".zip"}

ATTACHMENT_CATEGORIES = ["Autorização / ofício", "Contrato / proposta", "Nota fiscal / recibo", "Arte / divulgação",
                         "Programação / roteiro", "Lista de presença", "Fotos", "Enviado pelo solicitante", "Outro"]

TIMELINE_KINDS = {"criacao": "Solicitação", "status": "Status", "edicao": "Edição", "comentario": "Comentário",
                  "anexo": "Anexo", "encerramento": "Encerramento"}

def seed_venues(db: sqlite3.Connection) -> None:
    """Primeira carga do cadastro de espaços a partir da lista fixa usada até a versão anterior."""
    if db.execute("SELECT 1 FROM venues LIMIT 1").fetchone():
        return
    order = 0
    for label in VENUE_OPTIONS:
        if label in {EXTERNAL_VENUE, "Outro"}:
            continue
        match = re.match(r"^(.*?)\s*-\s*(\d+)\s*lugares(\s+cada)?$", label)
        name, capacity, each = (match.group(1).strip(), int(match.group(2)), bool(match.group(3))) if match else (label, None, False)
        order += 1
        db.execute("""INSERT INTO venues(name, capacity, notes, managed, active, sort_order, created_at, updated_at)
                      VALUES (?, ?, ?, 1, 1, ?, ?, ?)""",
                   (name, capacity, "Capacidade por sala." if each else None, order, now_iso(), now_iso()))
    db.commit()

def venue_label(row) -> str:
    """Rótulo exibido nos formulários; mantém o padrão anterior "Nome - N lugares"."""
    return f"{row['name']} - {row['capacity']} lugares" if row["capacity"] else row["name"]

def _venue_rows(active_only: bool = True):
    cache_key = "_venue_rows_active" if active_only else "_venue_rows_all"
    if has_app_context() and cache_key in g:
        return g.get(cache_key)
    sql = "SELECT * FROM venues" + (" WHERE active = 1" if active_only else "") + " ORDER BY sort_order, lower(name)"
    rows = get_db().execute(sql).fetchall()
    if has_app_context():
        setattr(g, cache_key, rows)
    return rows

def venue_options() -> list[str]:
    """Espaços ativos do cadastro + opções fixas de local externo e "Outro"."""
    return [venue_label(row) for row in _venue_rows()] + [EXTERNAL_VENUE, "Outro"]

def _venue_by_key() -> dict:
    return {_normalize_venue_key(row["name"]): row for row in _venue_rows(active_only=False)}

def _venue_capacity_warning(selected_venues, attendees) -> str | None:
    """Aviso (não bloqueia) quando o público previsto supera a capacidade dos espaços selecionados."""
    try:
        attendees = int(attendees or 0)
    except (TypeError, ValueError):
        return None
    if attendees <= 0:
        return None
    by_key = _venue_by_key()
    capacities = []
    for label in selected_venues or []:
        row = by_key.get(_normalize_venue_key(label))
        if row is None or not row["capacity"]:
            return None  # local sem capacidade conhecida: não é possível comparar
        capacities.append(row["capacity"])
    total = sum(capacities)
    if capacities and attendees > total:
        return f"Atenção: o público previsto ({attendees} pessoas) é maior que a capacidade do(s) espaço(s) selecionado(s) ({total} lugares)."
    return None

def seed_departments(db: sqlite3.Connection) -> None:
    """Create initial area list; recipient addresses remain blank until confirmed by FMABC."""
    for name in DEFAULT_DEPARTMENTS:
        db.execute(
            "INSERT OR IGNORE INTO departments(name, recipient_email, active, created_at, updated_at) VALUES (?, NULL, 1, ?, ?)",
            (name, now_iso(), now_iso()),
        )
    db.commit()

def smtp_settings() -> dict:
    return {
        "host": os.getenv("SMTP_HOST", "").strip(),
        "port": int(os.getenv("SMTP_PORT", "587") or 587),
        "user": os.getenv("SMTP_USER", "").strip(),
        "password": os.getenv("SMTP_PASSWORD", ""),
        "from_email": os.getenv("SMTP_FROM", "").strip(),
        "use_tls": os.getenv("SMTP_USE_TLS", "1").lower() in {"1", "true", "yes"},
    }

def smtp_is_configured() -> bool:
    cfg = smtp_settings()
    return bool(cfg["host"] and cfg["from_email"])

@app.before_request
def csrf_protection():
    if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        supplied = request.form.get("_csrf", "")
        expected = session.get("_csrf", "")
        if not supplied or not expected or not secrets.compare_digest(supplied, expected):
            abort(400, description="A sessão do formulário expirou. Atualize a página e tente novamente.")

@app.context_processor
def inject_template_globals():
    if "_csrf" not in session:
        session["_csrf"] = secrets.token_urlsafe(32)
    return {
        "csrf_token": session["_csrf"],
        "status_labels": STATUS_LABELS,
        "status_classes": STATUS_CLASSES,
        "event_types": EVENT_TYPES,
        "task_statuses": TASK_STATUSES,
        "support_catalog_statuses": SUPPORT_CATALOG_STATUSES,
        "formats": FORMATS,
        "support_options": SUPPORT_OPTIONS,
        "venue_options": venue_options(),
        "requested_item_options": REQUESTED_ITEM_OPTIONS,
        "authorization_options": AUTHORIZATION_OPTIONS,
        "time_options": TIME_OPTIONS,
        "communication_roles": COMMUNICATION_ROLES,
        "department_response_labels": DEPARTMENT_RESPONSE_LABELS,
        "department_task_statuses": DEPARTMENT_TASK_STATUSES,
        "department_task_status_labels": DEPARTMENT_TASK_STATUS_LABELS,
        "today": date.today().isoformat(),
    }

def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        user_id = session.get("user_id")
        if not user_id:
            return redirect(url_for("login", next=request.path))
        # Re-check the account on every protected request so blocked/deleted accounts
        # lose access immediately on their next navigation, even with an old session.
        user = get_db().execute(
            "SELECT id, email, role, is_active FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        if not user or not user["is_active"]:
            session.clear()
            flash("Esta conta está bloqueada ou não está mais cadastrada. Entre em contato com um administrador.", "error")
            return redirect(url_for("login"))
        # Apply role/email changes immediately to sessions that are already open.
        session["user_email"] = user["email"]
        session["user_role"] = user["role"]
        return view(*args, **kwargs)
    return wrapped

def get_event_or_404(event_id: int):
    event = get_db().execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
    if not event:
        abort(404)
    return event

def json_list(event, field: str) -> list[str]:
    try:
        data = json.loads(event[field] or "[]")
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, TypeError, KeyError):
        return []

def event_support(event) -> list[str]:
    return json_list(event, "support_json")

def event_modes(event) -> list[str]:
    values = json_list(event, "event_modes_json")
    return values or [x.strip() for x in (event["event_format"] or "").split(",") if x.strip()]

def event_venues(event) -> list[str]:
    values = json_list(event, "venues_json")
    return values or [x.strip() for x in (event["venue"] or "").split("; ") if x.strip()]

def event_requested_items(event) -> list[str]:
    return json_list(event, "requested_items_json")

def seed_task_templates(db: sqlite3.Connection) -> None:
    """Seed a first editable checklist model based on the FMABC manual checklist."""
    if db.execute("SELECT 1 FROM task_templates LIMIT 1").fetchone():
        return
    templates = []
    def t(title, category, description, trigger_type="always", trigger_value=None, offset=-7, owner=None):
        templates.append((title, category, description, trigger_type, trigger_value, offset, owner, len(templates) + 1))

    # General tasks — always created for approved events.
    t("Conferir formulário de solicitação e dados do evento", "Planejamento", "Validar data, horário, objetivo, setor solicitante, público e contatos.", offset=-45)
    t("Conferir autorização do evento e assinaturas necessárias", "Administrativo", "Verificar a documentação institucional e registrar pendências.", offset=-40)
    t("Confirmar reserva do local e capacidade", "Infraestrutura", "Conferir espaços selecionados, capacidade, acessibilidade e disponibilidade.", offset=-40)
    t("Consolidar programação do evento", "Planejamento", "Reunir horários, atividades e responsáveis pela programação.", offset=-30)
    t("Avaliar necessidade de reunião inicial com a área demandante", "Planejamento", "Registrar se a reunião será necessária e, se aplicável, agendar com o solicitante.", offset=-30)
    t("Confirmar programação e consolidar informações para o roteiro", "Planejamento", "Reunir horários, participantes, responsáveis e informações que dependem da área solicitante.", offset=-20)
    t("Montar cronograma operacional e designar responsáveis", "Planejamento", "Definir as etapas, os prazos e os responsáveis internos/externos.", offset=-25)
    t("Confirmar equipamentos e suporte técnico necessários", "Infraestrutura", "Relacionar audiovisual, internet, computador, microfones e apoio necessário.", offset=-14)
    t("Conferir materiais institucionais e sinalização", "Materiais", "Verificar totem, banners, kits e materiais que serão utilizados no espaço.", offset=-7)
    t("Realizar alinhamento final com as áreas envolvidas", "Operação", "Confirmar que solicitações e dependências estão atendidas.", offset=-3)
    t("Conferir montagem e preparação do espaço", "Infraestrutura", "Verificar mesas, cadeiras, púlpito, banners, credenciamento e organização do ambiente.", offset=-1)
    t("Organizar recepção dos convidados e equipe de apoio", "Recepção", "Definir ponto de recepção, responsáveis, fluxo de chegada e apoio aos convidados.", offset=-3)
    t("Executar o evento e registrar ocorrências", "Dia do evento", "Acompanhar a operação, registrar intercorrências e providências tomadas.", offset=0)
    t("Organizar fotos e materiais de cobertura após o evento", "Pós-evento", "Reunir registros e encaminhar materiais aos responsáveis pela publicação.", offset=1)
    t("Avaliar pendências e registrar feedback do evento", "Pós-evento", "Realizar reunião de feedback quando necessária e registrar aprendizados.", offset=7)

    # Tasks triggered by the original form's support selections.
    t("Confirmar solicitação de manutenção e vistoria do espaço", "Manutenção", "Verificar necessidades de manutenção e registrar confirmação do atendimento.", "support", "Manutenção", -7)
    t("Alinhar limpeza antes, durante e após o evento", "Limpeza", "Confirmar horários, escopo e responsável pelo atendimento.", "support", "Limpeza", -3)
    t("Alinhar apoio da inspetoria, acessos e circulação", "Operação", "Confirmar acessos, circulação, apoio durante o evento e horários da equipe.", "support", "Inspetoria", -3)
    t("Testar computador, projeção, som, microfones e internet", "TI / Audiovisual", "Realizar teste integrado e confirmar disponibilidade de apoio técnico.", "support", "TI", -2)
    t("Planejar e aprovar artes e divulgação prévia", "Comunicação", "Alinhar conteúdo, canais, público e aprovação da área solicitante.", "item", "Divulgação prévia", -20)
    t("Organizar divulgação posterior do evento", "Comunicação", "Selecionar registros e definir texto/canais para a cobertura posterior.", "item", "Divulgação posterior", 1)
    t("Configurar inscrições prévias e validar lista de participantes", "Inscrições", "Definir plataforma, período de inscrição, confirmação e exportação da lista.", "item", "Inscrição prévia", -14)
    t("Preparar lista de presença ou QR Code", "Credenciamento", "Definir método, campos e processo para controlar a presença.", "item", "Inscrição prévia", -3)
    t("Definir modelo e critérios para emissão de certificados", "Certificados", "Validar critérios de presença e fluxo de emissão para público e palestrantes.", "item", "Certificado", -7)
    t("Confirmar cardápio, quantidade, horário e serviço de coffee break", "Fornecedores", "Validar público previsto, local de montagem, toalhas/apoios e fornecedor.", "item", "Coffee break", -5)
    t("Preparar arte, dados e quantidade de credenciais/crachás", "Credenciamento", "Confirmar nome, identificação, arte e prazo para produção.", "item", "Credencial", -7)
    t("Preparar etiquetas de identificação e conferir nomes", "Credenciamento", "Confirmar quem receberá etiquetas, grafia dos nomes e quantidade necessária.", "item", "Credencial", -3)
    t("Confirmar toalhas de TNT e mesas de apoio para o coffee break", "Materiais", "Conferir quantidade de toalhas e local de montagem do serviço.", "item", "Coffee break", -3)
    t("Definir quantidade, personalização e entrega dos brindes", "Materiais", "Verificar estoque, personalização, prazo e disponibilidade antes de confirmar.", "item", "Brindes", -10)
    t("Confirmar mestre de cerimônias e revisar roteiro", "Cerimonial", "Validar roteiro, ordem das falas e se haverá mesa solene.", "item", "Mestre de Cerimônias", -7)
    t("Confirmar registro fotográfico e momentos prioritários", "Comunicação", "Alinhar responsável, cobertura e autorização para registros.", "item", "Registro fotográfico", -3)
    t("Confirmar gravação, permissões e entrega do material", "Audiovisual", "Definir formato de gravação, autorizações e destino dos arquivos.", "item", "Gravação", -5)
    t("Testar plataforma, conexão e transmissão simultânea", "Transmissão", "Realizar ensaio com participantes remotos e testar áudio, vídeo e internet.", "item", "Transmissão Simultânea", -2)
    t("Realizar teste técnico do ambiente remoto e do acesso dos participantes", "Transmissão", "Testar link, acesso de convidados, áudio, vídeo, conexão e apoio a participantes remotos.", "mode", "On-line", -2)
    t("Realizar teste técnico do ambiente remoto e do acesso dos participantes", "Transmissão", "Testar link, acesso de convidados, áudio, vídeo, conexão e apoio a participantes remotos.", "mode", "Híbrido", -2)
    t("Confirmar quantidade, nomes e logística do estacionamento", "Logística", "Validar vagas necessárias, convidados autorizados, local e liberação.", "item", "Reserva de Estacionamento", -3)
    t("Confirmar mesas, cadeiras, púlpito, banners e montagem especial", "Infraestrutura", "Alinhar layout do espaço, materiais de montagem e horário de preparação.", "item", "Equipamentos de áudio visual para apresentação", -3)

    # Additional tasks from the manual checklist, triggered by event category.
    t("Confirmar palestrantes/convidados e receber minibiografias e fotos", "Convidados", "Acompanhar confirmações, biografias, fotos e necessidades dos participantes.", "category", "Congresso / Simpósio", -14)
    t("Confirmar palestrantes/convidados e receber minibiografias e fotos", "Convidados", "Acompanhar confirmações, biografias, fotos e necessidades dos participantes.", "category", "Palestra / Mesa-redonda", -14)
    t("Validar roteiro cerimonial, mesa solene e ordem das falas", "Cerimonial", "Confirmar autoridades, precedência, roteiro, mestre de cerimônias e tempo de cada fala.", "category", "Cerimônia / Colação de grau", -14)
    t("Organizar recepção institucional e sequência de falas", "Cerimonial", "Confirmar equipe de recepção, convidados institucionais e roteiro de abertura.", "category", "Inauguração / Lançamento", -7)
    t("Preparar premiação, homenagens e sequência de entrega", "Cerimonial", "Validar nomes, ordem, materiais, certificados/prêmios e responsáveis pela entrega.", "category", "Premiação / Homenagem", -7)
    t("Alinhar recepção de convidados e equipe de apoio", "Recepção", "Confirmar ponto de recepção, responsáveis e fluxo de chegada.", "category", "Visita institucional", -3)

    db.executemany(
        "INSERT INTO task_templates(title, category, description, trigger_type, trigger_value, due_offset, assigned_to, active, sort_order, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?)",
        [(title, category, desc, trigger, value, offset, owner, order, now_iso(), now_iso())
         for title, category, desc, trigger, value, offset, owner, order in templates],
    )

def seed_support_catalog(db: sqlite3.Connection) -> None:
    """Seed editable support inventory notes from the manual checklist; ambiguous stock is flagged."""
    if db.execute("SELECT 1 FROM support_catalog LIMIT 1").fetchone():
        return
    records = [
        ("Faixas", "Comunicação", None, None, "Precisa confirmar", "Item citado no checklist manual; confirmar existência, quantidade e responsável."),
        ("Banners", "Comunicação", None, None, "Precisa confirmar", "Confirmar modelos disponíveis, quantidade e localização."),
        ("Crachás", "Credenciamento", None, None, "Em solicitação", "Checklist manual contém a anotação 'Pedido no compras'. Confirmar situação atual."),
        ("Tendas", "Infraestrutura", None, None, "Precisa confirmar", "Confirmar disponibilidade, quantidade, local de armazenamento e manutenção."),
        ("Porta-banners", "Materiais", None, "IC / Inspetoria / Fisiologia — confirmar", "Precisa confirmar", "O checklist manual menciona 50 IC, 32 Inspetoria e 20 Fisiologia, além de '102 disponível' e '110 unidades'. Valores divergentes: fazer inventário antes de informar quantidade disponível."),
        ("Brindes", "Materiais", None, None, "Precisa confirmar", "Checklist manual inclui a observação 'Não temos disponível'; confirmar estoque atual antes de prometer entrega."),
        ("Mesas extras", "Infraestrutura", None, None, "Precisa confirmar", "Confirmar quantidade disponível e reserva com a área responsável."),
        ("Toalhas de TNT para coffee break", "Materiais", None, None, "Precisa confirmar", "Verificar quantidade, cor e local de armazenamento; estimar pelo público e formato do serviço."),
        ("Totem / material institucional", "Comunicação", None, None, "Precisa confirmar", "Confirmar materiais que podem ser utilizados no evento e quem fará o transporte."),
        ("Estacionamento para convidados", "Logística", None, None, "Precisa confirmar", "Confirmar quantidade de vagas, local, nomes autorizados e fluxo de liberação."),
        ("Coffee break — mesas/apoios", "Infraestrutura", None, None, "Precisa confirmar", "Definir local de montagem, horário de acesso e materiais necessários."),
        ("Restaurante FSA", "Fornecedores", None, None, "Precisa confirmar", "O checklist manual cita este restaurante; confirmar contato, disponibilidade, condições e prazo antes de indicar ao solicitante."),
        ("Restaurante Quintal do ABC", "Fornecedores", None, None, "Precisa confirmar", "O checklist manual cita este restaurante e sugere aviso prévio; confirmar contato, disponibilidade, condições e prazo."),
    ]
    db.executemany(
        "INSERT INTO support_catalog(name, category, quantity, location, status, notes, active, updated_at) VALUES (?, ?, ?, ?, ?, ?, 1, ?)",
        [(*record, now_iso()) for record in records],
    )

def _split_field_options(raw) -> list[str]:
    parts = re.split(r"[\n,;]+", raw or "")
    return list(dict.fromkeys(p.strip()[:120] for p in parts if p.strip()))

def _task_fields_by_template(db, template_ids=None) -> dict:
    """Custom fields grouped by checklist template, with select options as a list."""
    sql = "SELECT * FROM task_template_fields"
    params = []
    ids = [i for i in (template_ids or []) if i]
    if template_ids is not None:
        if not ids:
            return {}
        sql += f" WHERE template_id IN ({','.join('?' for _ in ids)})"
        params = ids
    grouped = {}
    for row in db.execute(sql + " ORDER BY template_id, sort_order, id", params).fetchall():
        field = dict(row)
        field["options_list"] = _split_field_options(field.get("options"))
        grouped.setdefault(field["template_id"], []).append(field)
    return grouped

def add_checklist(event, commit: bool = True) -> int:
    """Create an initial checklist from configurable templates and the event form selections."""
    db = get_db()
    if db.execute("SELECT 1 FROM tasks WHERE event_id = ? LIMIT 1", (event["id"],)).fetchone():
        return 0
    try:
        event_day = date.fromisoformat(event["start_date"])
    except (TypeError, ValueError):
        event_day = date.today()

    services = event_support(event)
    requested = event_requested_items(event)
    modes = event_modes(event)
    category = event["event_type"] or ""
    selected_support = set(services)
    selected_items = set(requested)
    selected_modes = set(modes)

    templates = db.execute(
        "SELECT * FROM task_templates WHERE active = 1 ORDER BY sort_order, id"
    ).fetchall()
    inserted = 0
    added_keys = set()
    for order, template in enumerate(templates, start=1):
        trigger = template["trigger_type"]
        value = (template["trigger_value"] or "").strip()
        include = (
            trigger == "always"
            or (trigger == "support" and value in selected_support)
            or (trigger == "item" and value in selected_items)
            or (trigger == "mode" and value in selected_modes)
            or (trigger == "category" and value == category)
        )
        if not include:
            continue
        duplicate_key = (template["title"].strip().casefold(), template["category"].strip().casefold())
        if duplicate_key in added_keys:
            continue
        added_keys.add(duplicate_key)
        due_date = (event_day + timedelta(days=int(template["due_offset"] or 0))).isoformat()
        db.execute(
            """INSERT INTO tasks(event_id, title, category, due_date, status, assigned_to, description, notes, sort_order, created_at, template_id)
               VALUES (?, ?, ?, ?, 'pendente', ?, ?, NULL, ?, ?, ?)""",
            (event["id"], template["title"], template["category"], due_date,
             template["assigned_to"], template["description"], inserted + 1, now_iso(), template["id"]),
        )
        inserted += 1
    if commit:
        db.commit()
    return inserted

def normalize_date(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError:
        return None

def _event_venue_keys(event) -> set[str]:
    values = []
    try:
        values.extend(event_venues(event))
    except Exception:
        pass
    try:
        scalar = event["venue"] or ""
    except (KeyError, TypeError, IndexError):
        scalar = ""
    if scalar:
        values.extend([part.strip() for part in re.split(r"[;|]", scalar) if part.strip()])
    try:
        venue_other = event["venue_other"] or ""
    except (KeyError, TypeError, IndexError):
        venue_other = ""
    if venue_other:
        values.append(venue_other)
    keys = set()
    unmanaged = _unmanaged_venue_keys()
    for value in values:
        clean = _normalize_venue_key(value)
        if clean and clean not in unmanaged:
            keys.add(clean)
    return keys

def _venue_label_for_key(event, key):
    """Readable venue name for a normalized key (falls back to the key itself)."""
    candidates = []
    try:
        candidates.extend(event_venues(event))
    except Exception:
        pass
    for field in ("venue", "venue_other"):
        try:
            candidates.extend(part.strip() for part in re.split(r"[;|]", event[field] or "") if part.strip())
        except (KeyError, TypeError, IndexError):
            pass
    for label in candidates:
        if _normalize_venue_key(label) == key:
            return label
    return key

def _time_values_to_minutes(value):
    """Return all valid times in a free-text field: 09:00, 09h00, 9h, 18h30, "7h às 17h"."""
    if not value:
        return []
    results = []
    pattern = r"(?<!\d)(\d{1,2})\s*(?::\s*(\d{2})|[hH]\s*(\d{2})?)(?!\d)"
    for match in re.finditer(pattern, str(value).strip()):
        hour = int(match.group(1))
        minute = int(match.group(2) or match.group(3) or 0)
        if hour <= 23 and minute <= 59:
            results.append(hour * 60 + minute)
    return results

def _time_to_minutes(value):
    values = _time_values_to_minutes(value)
    return values[0] if values else None

def _time_interval_from_values(start_time, end_time=None):
    parsed_values = _time_values_to_minutes(start_time)
    if not parsed_values:
        return None, None
    start = parsed_values[0]
    end = _time_to_minutes(end_time)
    if end is None and len(parsed_values) > 1:
        end = parsed_values[1]
    if end is not None and end <= start:
        end = None
    return start, end

def _venue_alias_map() -> dict:
    """Mapa de chaves normalizadas (nome antigo, rótulo, apelidos) para a chave do espaço cadastrado."""
    if not has_app_context():
        return {}
    if "_venue_alias_map" in g:
        return g.get("_venue_alias_map")
    mapping = {}
    try:
        rows = _venue_rows(active_only=False)
    except sqlite3.Error:
        rows = []
    for row in rows:
        key = _basic_venue_key(row["name"])
        if not key:
            continue
        for alias in [venue_label(row)] + [a for a in re.split(r"[\n;]+", row["aliases"] or "") if a.strip()]:
            alias_key = _basic_venue_key(alias)
            if alias_key:
                mapping.setdefault(alias_key, key)
    g._venue_alias_map = mapping
    return mapping

def _unmanaged_venue_keys() -> set:
    """Espaços cadastrados que não são controlados pela agenda (não geram conflito)."""
    if not has_app_context():
        return set()
    if "_venue_unmanaged" not in g:
        try:
            g._venue_unmanaged = {_normalize_venue_key(r["name"]) for r in _venue_rows(active_only=False) if not r["managed"]}
        except sqlite3.Error:
            g._venue_unmanaged = set()
    return g._venue_unmanaged

def _normalize_venue_key(value):
    key = _basic_venue_key(value)
    if not key:
        return None
    return _venue_alias_map().get(key, key)

def _basic_venue_key(value):
    raw = unicodedata.normalize("NFKD", str(value or ""))
    clean = "".join(char for char in raw if not unicodedata.combining(char))
    clean = clean.casefold().replace("–", "-").replace("—", "-")
    clean = re.sub(r"\s+", " ", clean).strip()
    clean = re.sub(r"\s*-\s*\d+\s*lugares(?:\s+cada)?$", "", clean)
    clean = re.sub(r"^administrativo\s*-\s*", "", clean)
    if clean in {"outro", "externo (fora da fmabc)", "externo", "a confirmar", "nao informado"}:
        return None
    # Remove palavras genéricas para que "Auditório David Uip - 280 lugares", "Anfiteatro Dr. David Uip",
    # "Anf. David Uip" e "David Uip" sejam reconhecidos como o mesmo espaço.
    clean = re.sub(r"\s*\(.*?\)", "", clean)
    clean = clean.replace("pos-graduacao", "pos graduacao").replace("pós-graduação", "pos graduacao")
    words = [w for w in re.split(r"[\s.]+", clean) if w]
    generic = {"auditorio", "anfiteatro", "anf", "sala", "dr", "dra", "prof", "da", "do", "de", "das", "dos"}
    meaningful = [w for w in words if w not in generic]
    clean = " ".join(meaningful).strip(" -")
    return clean or None

def _selected_venue_labels(selected_venues, venue_other=None):
    labels = []
    for value in selected_venues or []:
        if value == "Outro":
            if venue_other:
                labels.append(venue_other.strip())
        elif value != "Externo (Fora da FMABC)":
            labels.append(value)
    # Deduplicate labels without changing display order.
    result, seen = [], set()
    unmanaged = _unmanaged_venue_keys()
    for label in labels:
        key = _normalize_venue_key(label)
        if key and key not in seen and key not in unmanaged:
            seen.add(key)
            result.append((key, label.strip()))
    return result

def _booking_intervals_overlap(request_start, request_end, existing_start, existing_end):
    if existing_start is None:
        # Existing booking has no parseable time. Caller treats it as an unresolved conflict.
        return False
    if request_end is not None and existing_end is not None:
        return request_start < existing_end and existing_start < request_end
    if request_end is not None:
        return request_start <= existing_start < request_end
    if existing_end is not None:
        return existing_start <= request_start < existing_end
    # When neither duration is known, block identical start times only.
    return request_start == existing_start

def _reservation_conflict_details(start_date, start_time, selected_venues, venue_other=None, db=None, end_time=None, exclude_event_id=None):
    """Find same-date room conflicts before requests are recorded; canceled events are ignored."""
    db = db or get_db()
    venue_pairs = _selected_venue_labels(selected_venues, venue_other)
    if not venue_pairs:
        return []  # External venues or unknown locations are not managed as FMABC rooms.
    request_start, request_end = _time_interval_from_values(start_time, end_time)
    if request_start is None:
        return []
    if request_end is not None and request_end <= request_start:
        return []
    selected_map = dict(venue_pairs)
    selected_keys = set(selected_map)

    rows = db.execute(
        """SELECT * FROM events
           WHERE lower(COALESCE(status, '')) <> 'cancelado'
             AND start_date <= ?
             AND COALESCE(NULLIF(end_date, ''), start_date) >= ?
             AND id <> ?
           ORDER BY start_date, start_time""",
        (start_date, start_date, exclude_event_id or 0),
    ).fetchall()
    blockers = []
    seen = set()
    requested_day = date.fromisoformat(start_date)
    for row in rows:
        event = dict(row)
        existing_keys = _event_venue_keys(row)
        shared = selected_keys & existing_keys
        if not shared:
            continue
        try:
            event_start = date.fromisoformat(event.get("start_date") or "")
            event_end = date.fromisoformat(event.get("end_date") or event.get("start_date") or "")
        except ValueError:
            continue

        # A multi-day booking occupies the room throughout intermediate days; block conservatively.
        all_day_overlap = event_start <= requested_day <= event_end and event_start != event_end
        existing_start, existing_end = _time_interval_from_values(event.get("start_time"), event.get("end_time"))
        unknown_time = existing_start is None
        unknown_duration = existing_start is not None and existing_end is None
        overlaps = all_day_overlap
        unresolved = False
        if not all_day_overlap:
            if unknown_time:
                # Sem horário inicial: a agenda não consegue descartar uma sobreposição.
                unresolved = True
            elif unknown_duration:
                # Há horário inicial, mas não há término. Se o evento começou antes
                # do fim do intervalo solicitado, a reserva pode continuar ocupando o espaço.
                unresolved = (existing_start == request_start) if request_end is None else (existing_start < request_end)
            else:
                overlaps = _booking_intervals_overlap(
                    request_start, request_end, existing_start, existing_end
                )
        if not overlaps and not unresolved:
            continue
        for key in shared:
            venue_label = selected_map.get(key, key)
            marker = (event.get("id"), key, "horario_indefinido" if unresolved else "conflito")
            if marker in seen:
                continue
            seen.add(marker)
            blockers.append({
                "venue": venue_label,
                "kind": "horario_indefinido" if unresolved else "conflito",
                "event_id": event.get("id"),
            })
    # Bloqueios cadastrados pelo Setor de Eventos (manutenção, obra, uso institucional).
    for block in _venue_blocks_on(start_date, db):
        key = _normalize_venue_key(block["venue_name"])
        if key not in selected_keys:
            continue
        block_start, block_end = _time_interval_from_values(block["start_time"], block["end_time"])
        if block_start is None:
            overlaps_block = True  # bloqueio do dia inteiro
        else:
            overlaps_block = _booking_intervals_overlap(request_start, request_end, block_start, block_end or 24 * 60)
        if overlaps_block:
            blockers.append({"venue": selected_map.get(key, key), "kind": "bloqueio", "event_id": None,
                             "reason": block["reason"], "block_id": block["id"]})
    return blockers

MAX_EVENT_DAYS = 31

def _conflicts_for_range(start_date, end_date, start_time, end_time, selected_venues, venue_other=None, db=None, exclude_event_id=None):
    """Checa cada dia do período (eventos de vários dias usam o mesmo horário em todos os dias)."""
    db = db or get_db()
    found = []
    day, last = date.fromisoformat(start_date), date.fromisoformat(end_date or start_date)
    while day <= last:
        for blocker in _reservation_conflict_details(start_date=day.isoformat(), start_time=start_time, end_time=end_time,
                                                     selected_venues=selected_venues, venue_other=venue_other, db=db,
                                                     exclude_event_id=exclude_event_id):
            found.append({**blocker, "date": day.isoformat()})
        day += timedelta(days=1)
    return found

def _validate_end_date(start_date: str, raw_end: str | None):
    """Retorna (end_date, erro)."""
    if not (raw_end or "").strip():
        return start_date, None
    end_date = normalize_date(raw_end)
    if not end_date:
        return None, "Informe uma data de término válida."
    if end_date < start_date:
        return None, "A data de término não pode ser anterior à data de início."
    if (date.fromisoformat(end_date) - date.fromisoformat(start_date)).days > MAX_EVENT_DAYS:
        return None, f"Um evento pode ocupar no máximo {MAX_EVENT_DAYS} dias seguidos. Para períodos maiores, cadastre etapas separadas."
    return end_date, None

def _venue_blocks_on(day: str, db=None):
    db = db or get_db()
    return db.execute("""SELECT b.*, v.name AS venue_name FROM venue_blocks b JOIN venues v ON v.id = b.venue_id
                         WHERE b.start_date <= ? AND b.end_date >= ? ORDER BY b.start_date, b.start_time""",
                      (day, day)).fetchall()

def _event_date_bounds(event):
    try:
        start = date.fromisoformat(event["start_date"])
        end_raw = event["end_date"] or event["start_date"]
        end = date.fromisoformat(end_raw)
        return start, end
    except (TypeError, ValueError, KeyError, IndexError):
        return None, None

def _find_schedule_conflicts(events):
    """Detect overlapping bookings of the same known venue; uncertain times are flagged for review."""
    records = [dict(e) for e in events]
    found, seen = [], set()
    for i, first in enumerate(records):
        if first.get("status") == "cancelado":
            continue
        a_start, a_end = _event_date_bounds(first)
        a_venues = _event_venue_keys(first)
        if not a_start or not a_end or not a_venues:
            continue
        for second in records[i + 1:]:
            if second.get("status") == "cancelado" or first.get("id") == second.get("id"):
                continue
            b_start, b_end = _event_date_bounds(second)
            if not b_start or not b_end:
                continue
            overlap_start, overlap_end = max(a_start, b_start), min(a_end, b_end)
            if overlap_start > overlap_end:
                continue
            venues = a_venues & _event_venue_keys(second)
            if not venues:
                continue
            a_st, a_en = _time_interval_from_values(first.get("start_time"), first.get("end_time"))
            b_st, b_en = _time_interval_from_values(second.get("start_time"), second.get("end_time"))
            single_day = a_start == a_end == b_start == b_end
            if single_day and None not in (a_st, a_en, b_st, b_en):
                if not (a_st < b_en and b_st < a_en):
                    continue
                reason = "Conflito de horário confirmado"
            elif single_day:
                reason = "Possível conflito: duração ou horário final não informado"
            else:
                reason = "Possível conflito: datas sobrepostas no mesmo espaço"
            venue_key = sorted(venues)[0]
            venue = _venue_label_for_key(first, venue_key)
            key = tuple(sorted((first.get("id"), second.get("id")))) + (overlap_start.isoformat(), venue)
            if key in seen:
                continue
            seen.add(key)
            found.append({"event_a_id": first.get("id"), "event_a_title": first.get("title"), "event_b_id": second.get("id"), "event_b_title": second.get("title"), "date": overlap_start.isoformat(), "venue": venue, "reason": reason})
    return sorted(found, key=lambda x: (x["date"], x["venue"], x["event_a_title"] or ""))

def _department_task_snapshot(row):
    if row is None:
        return {}
    keys = {"involvement", "details", "notes", "area_responsible", "due_date", "response_status",
            "receipt_confirmed_at", "receipt_confirmed_by", "task_status", "task_updated_at",
            "task_updated_by", "pending_reason", "response_notes", "response_by", "responded_at"}
    available = set(row.keys()) if hasattr(row, "keys") else set(row)
    return {key: row[key] for key in keys if key in available}

def _record_department_task_history(db, update_id, event_id, department_id, before, after,
                                    changed_by, source, action):
    before = before or {}
    after = after or {}
    display_changes = []
    for key, label in DEPARTMENT_TASK_HISTORY_FIELDS:
        old, new = before.get(key), after.get(key)
        if old != new:
            old_text = "vazio" if old in (None, "") else str(old)
            new_text = "vazio" if new in (None, "") else str(new)
            if key == "involvement":
                old_text = COMMUNICATION_ROLES.get(old, old_text)
                new_text = COMMUNICATION_ROLES.get(new, new_text)
            elif key == "response_status":
                old_text = DEPARTMENT_RESPONSE_LABELS.get(old, old_text)
                new_text = DEPARTMENT_RESPONSE_LABELS.get(new, new_text)
            elif key == "task_status":
                old_text = DEPARTMENT_TASK_STATUS_LABELS.get(old, old_text)
                new_text = DEPARTMENT_TASK_STATUS_LABELS.get(new, new_text)
            display_changes.append(f"{label}: {old_text} → {new_text}")
    if not display_changes and before:
        return
    summary = "; ".join(display_changes) if display_changes else "Providência criada."
    db.execute("""INSERT INTO department_task_history
        (update_id,event_id,department_id,changed_at,changed_by,source,action,change_summary,before_json,after_json)
        VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (update_id,event_id,department_id,now_iso(),(changed_by or "")[:160] or None,source,action,summary,
         json.dumps(before,ensure_ascii=False,default=str),json.dumps(after,ensure_ascii=False,default=str)))

@app.errorhandler(413)
def file_too_large(_error):
    flash("O arquivo enviado é grande demais (limite de 15 MB por anexo).", "error")
    referrer = request.referrer or ""
    if referrer.startswith(request.host_url):
        return redirect(referrer)
    return redirect(url_for("dashboard"))

EVENT_EDIT_LABELS = {
    "title": "Nome do evento", "department": "Setor organizador", "organizer_name": "Responsável",
    "organizer_email": "E-mail do solicitante", "organizer_phone": "Telefone", "contact_email": "E-mail de contato",
    "event_type": "Categoria", "event_type_other": "Outra categoria", "event_format": "Tipo do evento",
    "start_date": "Data de início", "end_date": "Data de término", "start_time": "Horário de início",
    "end_time": "Horário de término", "venue": "Local", "expected_attendees": "Público previsto",
    "audience": "Público-alvo", "description": "Objetivo", "authorized_by": "Autorizado por",
    "cost_center": "Centro de custo", "additional_info": "Informações adicionais",
}

def _public_app_base_url():
    configured = os.getenv("APP_BASE_URL", "").strip().rstrip("/")
    if configured:
        parsed = urlparse(configured)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.hostname in {"127.0.0.1", "localhost", "0.0.0.0"}:
            return ""
        return configured
    host = (request.host or "").split(":", 1)[0].lower()
    if host in {"127.0.0.1", "localhost", "0.0.0.0"}:
        return ""
    return request.url_root.rstrip("/")

@app.errorhandler(400)
def bad_request(error):
    return render_template("error.html", code=400, message=getattr(error, "description", "Não foi possível processar a solicitação.")), 400

@app.errorhandler(404)
def not_found(_error):
    return render_template("error.html", code=404, message="A página ou evento solicitado não foi encontrado."), 404

@app.errorhandler(500)
def internal_error(error):
    original = getattr(error, "original_exception", None) or error
    app.logger.error("Erro interno em %s %s", request.method, request.path, exc_info=original)
    return render_template("error.html", code=500, message="Ocorreu um erro inesperado. O problema foi registrado em instance/erros.log; tente novamente ou avise o responsável pelo sistema."), 500



def log_event(db, event_id: int, kind: str, summary: str) -> None:
    """Registra um item na linha do tempo do evento (não faz commit)."""
    db.execute("INSERT INTO event_change_log(event_id, changed_at, changed_by, summary, kind) VALUES (?,?,?,?,?)",
               (event_id, now_iso(), session.get("user_email") if has_app_context() else None, summary[:8000], kind))


# ---------------------------------------------------------------------------
# Fase 3 — Comunicação: caixa de saída, avisos ao solicitante, pedidos de
# informação e lembretes automáticos.
# ---------------------------------------------------------------------------

SCHEMA_COMUNICACAO = """
CREATE TABLE IF NOT EXISTS email_outbox (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL,
    event_id INTEGER REFERENCES events(id) ON DELETE SET NULL,
    recipient TEXT NOT NULL,
    subject TEXT NOT NULL,
    body TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pendente',
    attempts INTEGER NOT NULL DEFAULT 0,
    last_error TEXT,
    created_by TEXT,
    created_at TEXT NOT NULL,
    sent_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_email_outbox_status ON email_outbox(status, created_at);
CREATE TABLE IF NOT EXISTS info_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    token TEXT NOT NULL UNIQUE,
    question TEXT NOT NULL,
    requested_by TEXT,
    requested_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'aberta',
    answer TEXT,
    answered_by TEXT,
    answered_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_info_requests_event ON info_requests(event_id, status);
CREATE TABLE IF NOT EXISTS reminder_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL,
    ref_key TEXT NOT NULL,
    sent_on TEXT NOT NULL,
    UNIQUE(kind, ref_key, sent_on)
);
CREATE TABLE IF NOT EXISTS app_settings (
    key TEXT PRIMARY KEY,
    value TEXT
);
"""

EMAIL_STATUS_LABELS = {"pendente": "Aguardando envio", "enviado": "Enviado", "manual": "Enviado manualmente",
                       "erro": "Falhou", "cancelado": "Cancelado"}
EMAIL_KIND_LABELS = {"status": "Aviso de status", "confirmacao": "Confirmação de recebimento",
                     "pedido_info": "Pedido de informações", "resposta_info": "Resposta do solicitante",
                     "lembrete_tarefas": "Lembrete de tarefas", "lembrete_area": "Lembrete às áreas",
                     "lembrete_info": "Lembrete ao solicitante"}
NOTIFY_STATUSES = {"em_triagem", "aguardando_informacoes", "aprovado", "em_planejamento", "cancelado"}
_OUTBOX_LOCK = threading.Lock()


def init_comunicacao_schema(db) -> None:
    db.executescript(SCHEMA_COMUNICACAO)
    user_columns = {row["name"] for row in db.execute("PRAGMA table_info(users)").fetchall()}
    if "ics_token" not in user_columns:
        db.execute("ALTER TABLE users ADD COLUMN ics_token TEXT")
    db.commit()


def _valid_email(value) -> bool:
    return bool(re.fullmatch(r"[^@\s,;<>]+@[^@\s,;<>]+\.[^@\s,;<>]+", (value or "").strip()))


def link_base_url() -> str:
    """Endereço público para links em e-mails. Fora de uma requisição, só APP_BASE_URL vale."""
    if has_request_context():
        return _public_app_base_url()
    configured = (os.getenv("APP_BASE_URL") or "").strip().rstrip("/")
    parsed = urlparse(configured) if configured else None
    if not parsed or parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.hostname in {"127.0.0.1", "localhost", "0.0.0.0"}:
        return ""
    return configured


def public_link(endpoint: str, **values) -> str:
    base = link_base_url()
    if not base:
        return ""
    if has_request_context():
        return base + url_for(endpoint, **values)
    with app.test_request_context():
        return base + url_for(endpoint, **values)


def queue_email(db, recipient: str, subject: str, body: str, kind: str, event_id=None) -> int | None:
    """Coloca um e-mail na caixa de saída (não faz commit). Retorna o id ou None se o destinatário for inválido."""
    recipient = (recipient or "").strip().lower()
    if not _valid_email(recipient):
        return None
    subject = re.sub(r"[\r\n]+", " ", subject).strip()[:250]
    created_by = session.get("user_email") if has_request_context() else "sistema"
    cursor = db.execute("""INSERT INTO email_outbox(kind, event_id, recipient, subject, body, status, created_by, created_at)
                           VALUES (?,?,?,?,?, 'pendente', ?, ?)""",
                        (kind, event_id, recipient, subject, body[:30000], created_by, now_iso()))
    return cursor.lastrowid


def send_pending_emails(limit: int = 25) -> dict:
    """Envia e-mails pendentes usando uma conexão própria (pode rodar em segundo plano)."""
    summary = {"enviados": 0, "falhas": 0}
    if not smtp_is_configured():
        return summary
    if not _OUTBOX_LOCK.acquire(blocking=False):
        return summary  # outro envio já está em andamento
    try:
        conn = _dbcompat.connect(DB_PATH)
        cfg = smtp_settings()
        rows = conn.execute("SELECT * FROM email_outbox WHERE status='pendente' AND attempts < 3 ORDER BY id LIMIT ?", (limit,)).fetchall()
        if rows:
            try:
                server = smtplib.SMTP(cfg["host"], cfg["port"], timeout=20)
                if cfg["use_tls"]:
                    server.starttls()
                if cfg["user"]:
                    server.login(cfg["user"], cfg["password"])
            except Exception as exc:
                detail = f"Conexão SMTP: {type(exc).__name__}: {exc}"[:500]
                for row in rows:
                    conn.execute("UPDATE email_outbox SET attempts=attempts+1, last_error=?, status=CASE WHEN attempts+1>=3 THEN 'erro' ELSE 'pendente' END WHERE id=?",
                                 (detail, row["id"]))
                conn.commit()
                summary["falhas"] = len(rows)
                return summary
            with server:
                for row in rows:
                    msg = EmailMessage()
                    msg["Subject"] = row["subject"]
                    msg["From"] = cfg["from_email"]
                    msg["To"] = row["recipient"]
                    # quoted-printable chega íntegro mesmo em servidores sem suporte a 8 bits (acentos e aspas).
                    msg.set_content(row["body"], cte="quoted-printable")
                    try:
                        server.send_message(msg)
                        conn.execute("UPDATE email_outbox SET status='enviado', sent_at=?, attempts=attempts+1, last_error=NULL WHERE id=?", (now_iso(), row["id"]))
                        summary["enviados"] += 1
                    except Exception as exc:
                        detail = f"{type(exc).__name__}: {exc}"[:500]
                        conn.execute("UPDATE email_outbox SET attempts=attempts+1, last_error=?, status=CASE WHEN attempts+1>=3 THEN 'erro' ELSE 'pendente' END WHERE id=?",
                                     (detail, row["id"]))
                        summary["falhas"] += 1
                    conn.commit()
        conn.close()
    finally:
        _OUTBOX_LOCK.release()
    return summary


def dispatch_emails_async() -> None:
    """Dispara o envio em segundo plano para a tela não esperar o servidor de e-mail."""
    if smtp_is_configured() and os.getenv("FMABC_ENVIO_SINCRONO") != "1":
        threading.Thread(target=send_pending_emails, daemon=True).start()
    elif smtp_is_configured():
        send_pending_emails()


def _br_date(value) -> str:
    try:
        return date.fromisoformat((value or "")[:10]).strftime("%d/%m/%Y")
    except ValueError:
        return value or "data a confirmar"


def _event_when(event) -> str:
    when = _br_date(event["start_date"])
    if event["end_date"] and event["end_date"] != event["start_date"]:
        when += f" a {_br_date(event['end_date'])}"
    if event["start_time"]:
        when += f", {event['start_time']}" + (f" às {event['end_time']}" if event["end_time"] else "")
    return when


EMAIL_SIGNATURE = "\n\nAtenciosamente,\nSetor de Eventos — Centro Universitário FMABC"


def _requester_email_body(event, intro: str, message: str | None = None, extra: str = "") -> str:
    tracking = public_link("track_request")
    lines = [f"Olá, {event['organizer_name']}.", "", intro, "",
             f"Evento: {event['title']}", f"Protocolo: {event['protocol']}", f"Data: {_event_when(event)}"]
    if event["venue"]:
        lines.append(f"Local: {event['venue']}")
    if message:
        lines += ["", "Mensagem do Setor de Eventos:", message]
    if extra:
        lines += ["", extra]
    if tracking:
        lines += ["", f"Acompanhe pelo protocolo em: {tracking}"]
    return "\n".join(lines) + EMAIL_SIGNATURE


def queue_submission_confirmation(db, event) -> int | None:
    body = _requester_email_body(event, "Recebemos sua solicitação de evento. Ela será analisada pelo Setor de Eventos e você será avisado(a) por e-mail sobre o andamento.",
                                 extra="Este envio não representa aprovação do evento. Guarde o número do protocolo.")
    return queue_email(db, event["organizer_email"], f"Solicitação recebida — {event['title']} ({event['protocol']})", body, "confirmacao", event["id"])


def create_info_request(db, event, question: str) -> str:
    """Abre um pedido de informações (cancela pedidos abertos anteriores) e devolve o token."""
    db.execute("UPDATE info_requests SET status='cancelada' WHERE event_id=? AND status='aberta'", (event["id"],))
    token = secrets.token_urlsafe(32)
    db.execute("INSERT INTO info_requests(event_id, token, question, requested_by, requested_at, status) VALUES (?,?,?,?,?, 'aberta')",
               (event["id"], token, question[:4000], session.get("user_email") if has_request_context() else None, now_iso()))
    return token


def _info_request_email(event, question: str, token: str, reminder: bool = False) -> tuple[str, str]:
    link = public_link("answer_info_request", token=token)
    how = (f"Responda (e, se precisar, anexe arquivos) neste link: {link}" if link else
           "Responda a este e-mail ou consulte o protocolo na página de acompanhamento do Setor de Eventos.")
    intro = ("Lembrete: ainda precisamos das informações abaixo para continuar a análise da sua solicitação."
             if reminder else "Para continuar a análise da sua solicitação, precisamos de algumas informações.")
    body = _requester_email_body(event, intro, extra=f"O que precisamos:\n{question}\n\n{how}")
    subject = ("Lembrete — " if reminder else "") + f"Informações necessárias — {event['title']} ({event['protocol']})"
    return subject, body


def handle_status_change(db, event_before, new_status: str, notify: bool, message: str | None) -> list[str]:
    """Efeitos da mudança de status: pedido de informações e aviso por e-mail ao solicitante.

    Não faz commit. Retorna avisos para mostrar à equipe.
    """
    notes = []
    message = (message or "").strip()[:4000] or None
    changed = event_before["status"] != new_status
    event = db.execute("SELECT * FROM events WHERE id=?", (event_before["id"],)).fetchone()
    if new_status == "aguardando_informacoes" and (changed or message):
        if not message:
            return ["Para pedir informações, escreva no campo “Mensagem ao solicitante” o que está faltando."]
        token = create_info_request(db, event, message)
        log_event(db, event["id"], "comentario", f"Pedido de informações ao solicitante: {message}")
        if notify:
            subject, body = _info_request_email(event, message, token)
            if queue_email(db, event["organizer_email"], subject, body, "pedido_info", event["id"]):
                notes.append("Pedido de informações enviado para a caixa de saída de e-mails.")
            else:
                notes.append("O e-mail do solicitante é inválido; o pedido ficou registrado e aparece na consulta de protocolo.")
        return notes
    if not notify or not (changed or message) or new_status not in NOTIFY_STATUSES:
        return notes
    if new_status in {"aprovado", "em_planejamento"} and event_before["status"] in {"aprovado", "em_planejamento"} and not message:
        return notes  # passagem interna de aprovado para planejamento: não incomoda o solicitante
    texts = {
        "em_triagem": ("Sua solicitação está em análise pelo Setor de Eventos.", "Solicitação em análise"),
        "aprovado": ("Sua solicitação foi aprovada. O Setor de Eventos iniciará o planejamento e poderá entrar em contato para alinhar detalhes.", "Solicitação aprovada"),
        "em_planejamento": ("Sua solicitação foi aprovada e está em planejamento pelo Setor de Eventos.", "Evento em planejamento"),
        "cancelado": ("Sua solicitação de evento foi cancelada ou não pôde ser atendida.", "Solicitação cancelada"),
    }
    intro, title = texts[new_status]
    body = _requester_email_body(event, intro, message)
    if queue_email(db, event["organizer_email"], f"{title} — {event['title']} ({event['protocol']})", body, "status", event["id"]):
        log_event(db, event["id"], "status", f"Aviso por e-mail ao solicitante: {title.lower()}." + (f"\nMensagem: {message}" if message else ""))
        notes.append("Aviso ao solicitante enviado para a caixa de saída de e-mails.")
    else:
        notes.append("Não foi possível avisar o solicitante: o e-mail cadastrado é inválido.")
    return notes


def _setting(db, key, default=None):
    row = db.execute("SELECT value FROM app_settings WHERE key=?", (key,)).fetchone()
    return row["value"] if row else default


def _set_setting(db, key, value) -> None:
    db.execute("INSERT INTO app_settings(key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))


def _reminder_sent(db, kind, ref_key, since: date) -> bool:
    return bool(db.execute("SELECT 1 FROM reminder_log WHERE kind=? AND ref_key=? AND sent_on>=? LIMIT 1",
                           (kind, str(ref_key), since.isoformat())).fetchone())


def _mark_reminder(db, kind, ref_key, day: date) -> None:
    db.execute("INSERT OR IGNORE INTO reminder_log(kind, ref_key, sent_on) VALUES (?,?,?)", (kind, str(ref_key), day.isoformat()))


def run_daily_reminders(db, today: date | None = None, force: bool = False) -> dict | None:
    """Gera os lembretes do dia (idempotente: cada lembrete sai no máximo uma vez no período definido)."""
    today = today or date.today()
    if not force and _setting(db, "lembretes_ultima_execucao") == today.isoformat():
        return None
    summary = {"tarefas": 0, "areas": 0, "solicitantes": 0}
    soon = (today + timedelta(days=3)).isoformat()

    # 1) Resumo diário de tarefas vencidas ou vencendo em até 3 dias, por responsável interno.
    admins = [r["email"] for r in db.execute("SELECT email FROM users WHERE role='admin' AND is_active=1").fetchall()]
    active = {r["email"].lower() for r in db.execute("SELECT email FROM users WHERE is_active=1").fetchall()}
    rows = db.execute("""SELECT t.title, t.due_date, t.assigned_to, e.id event_id, e.title event_title, e.internal_owner
        FROM tasks t JOIN events e ON e.id=t.event_id
        WHERE t.status NOT IN ('concluida','nao_se_aplica') AND t.due_date IS NOT NULL AND t.due_date<>'' AND t.due_date<=?
          AND e.status IN ('aprovado','em_planejamento') ORDER BY t.due_date, e.start_date""", (soon,)).fetchall()
    by_person = {}
    for row in rows:
        owner = (row["internal_owner"] or "").lower()
        recipients = {owner} if owner in active else set(a.lower() for a in admins)
        assigned = (row["assigned_to"] or "").strip().lower()
        if _valid_email(assigned):
            recipients.add(assigned)
        for person in recipients:
            by_person.setdefault(person, []).append(row)
    for person, items in by_person.items():
        if _reminder_sent(db, "tarefas", person, today):
            continue
        lines = [f"Bom dia. Estas são as tarefas de eventos vencidas ou com prazo até {_br_date(soon)}:", ""]
        for row in items[:60]:
            flag = "ATRASADA — " if row["due_date"] < today.isoformat() else ""
            link = public_link("event_checklist", event_id=row["event_id"])
            lines.append(f"• {flag}{_br_date(row['due_date'])} · {row['event_title']}: {row['title']}" + (f"\n  {link}" if link else ""))
        if len(items) > 60:
            lines.append(f"… e mais {len(items) - 60} tarefa(s). Veja o Checklist consolidado.")
        if queue_email(db, person, f"Tarefas de eventos com prazo próximo — {today.strftime('%d/%m/%Y')}",
                       "\n".join(lines) + EMAIL_SIGNATURE, "lembrete_tarefas"):
            _mark_reminder(db, "tarefas", person, today)
            summary["tarefas"] += 1

    # 2) Áreas de apoio com providência pendente para os próximos 7 dias (no máximo a cada 3 dias).
    week = (today + timedelta(days=7)).isoformat()
    pending = db.execute("""SELECT u.*, e.title event_title, e.start_date, e.start_time, e.end_time, e.venue, d.name department_name, d.recipient_email
        FROM event_department_updates u JOIN events e ON e.id=u.event_id JOIN departments d ON d.id=u.department_id
        WHERE u.involvement='acao' AND u.task_status<>'concluida' AND u.response_token IS NOT NULL AND d.active=1
          AND d.recipient_email IS NOT NULL AND d.recipient_email<>'' AND e.status IN ('aprovado','em_planejamento')
          AND e.start_date>=? AND COALESCE(NULLIF(u.due_date,''), e.start_date)<=?
        ORDER BY d.name, COALESCE(NULLIF(u.due_date,''), e.start_date)""", (today.isoformat(), week)).fetchall()
    by_area = {}
    for row in pending:
        if not _reminder_sent(db, "area", row["id"], today - timedelta(days=2)):
            by_area.setdefault((row["department_name"], row["recipient_email"]), []).append(row)
    for (area, email), items in by_area.items():
        lines = ["Prezados,", "", f"Há providências da área {area} para eventos da FMABC nos próximos dias que ainda não foram concluídas:", ""]
        for row in items:
            link = public_link("department_response", token=row["response_token"])
            prazo = _br_date(row["due_date"] or row["start_date"])
            lines.append(f"• {row['event_title']} — evento em {_br_date(row['start_date'])}, prazo {prazo}"
                         + (f"\n  Providência: {row['details']}" if row["details"] else "")
                         + (f"\n  Atualize a situação: {link}" if link else ""))
        lines += ["", "Se já estiver resolvido, basta atualizar pelo link. Em caso de impedimento, avise o Setor de Eventos."]
        if queue_email(db, email, f"Lembrete — providências de eventos ({area})", "\n".join(lines) + EMAIL_SIGNATURE, "lembrete_area"):
            for row in items:
                _mark_reminder(db, "area", row["id"], today)
            summary["areas"] += 1

    # 3) Solicitantes que não responderam a um pedido de informações há 3 dias ou mais (até 3 lembretes).
    open_requests = db.execute("""SELECT r.*, e.* , r.id request_id, r.token request_token FROM info_requests r JOIN events e ON e.id=r.event_id
        WHERE r.status='aberta' AND e.status='aguardando_informacoes' AND r.requested_at<=?""",
                               ((today - timedelta(days=3)).isoformat() + " 23:59:59",)).fetchall()
    for row in open_requests:
        sent_before = db.execute("SELECT COUNT(*) FROM reminder_log WHERE kind='info' AND ref_key=?", (str(row["request_id"]),)).fetchone()[0]
        if sent_before >= 3 or _reminder_sent(db, "info", row["request_id"], today - timedelta(days=2)):
            continue
        subject, body = _info_request_email(row, row["question"], row["request_token"], reminder=True)
        if queue_email(db, row["organizer_email"], subject, body, "lembrete_info", row["event_id"]):
            _mark_reminder(db, "info", row["request_id"], today)
            summary["solicitantes"] += 1

    _set_setting(db, "lembretes_ultima_execucao", today.isoformat())
    _set_setting(db, "lembretes_ultimo_resumo", json.dumps(summary))
    db.commit()
    return summary


def start_reminder_scheduler() -> None:
    """Gera os lembretes uma vez por dia (a partir das 7h) enquanto o sistema estiver ligado."""
    if os.getenv("LEMBRETES_AUTOMATICOS", "1") == "0":
        return

    def loop():
        while True:
            try:
                if datetime.now().hour >= 7:
                    with app.app_context():
                        if run_daily_reminders(get_db()) is not None:
                            send_pending_emails(limit=200)
                        else:
                            send_pending_emails()
            except Exception:
                app.logger.exception("Falha ao gerar lembretes automáticos")
            time.sleep(1800)

    threading.Thread(target=loop, daemon=True, name="lembretes-fmabc").start()


def store_attachment(db, event_id: int, upload, category: str, description: str | None, uploaded_by: str | None) -> tuple[bool, str]:
    """Valida e grava um anexo do evento (não faz commit). Retorna (ok, mensagem)."""
    original = Path(upload.filename or "").name.replace("\\", "_")[:200] or "arquivo"
    extension = Path(original).suffix.lower()
    if extension not in ATTACHMENT_EXTENSIONS:
        return False, f"“{original}”: tipo de arquivo não permitido. Envie PDF, Word, Excel, PowerPoint, imagem, texto, CSV ou ZIP."
    content = upload.read(ATTACHMENT_MAX_BYTES + 1)
    if len(content) > ATTACHMENT_MAX_BYTES:
        return False, f"“{original}” passa de 15 MB. Reduza o tamanho ou compacte antes de anexar."
    if not content:
        return False, f"“{original}” está vazio."
    category = category if category in ATTACHMENT_CATEGORIES else "Outro"
    folder = ATTACHMENT_DIR / str(event_id)
    folder.mkdir(parents=True, exist_ok=True)
    stored = f"{secrets.token_hex(16)}{extension}"
    (folder / stored).write_bytes(content)
    db.execute("""INSERT INTO event_attachments(event_id, original_name, stored_name, size_bytes, category, description, uploaded_by, uploaded_at)
                  VALUES (?,?,?,?,?,?,?,?)""",
               (event_id, original, stored, len(content), category, (description or "").strip()[:300] or None, uploaded_by, now_iso()))
    return True, original


# ---------------------------------------------------------------------------
# Checklist do evento: grupos por prazo, textos de prazo, iniciais e contadores.
# ---------------------------------------------------------------------------

def init_checklist_schema(db) -> None:
    db.executescript("""
    CREATE TABLE IF NOT EXISTS task_notes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        task_id INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
        author TEXT,
        text TEXT NOT NULL,
        created_at TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_task_notes_task ON task_notes(task_id, created_at);
    """)
    db.commit()


_SMALL_WORDS = {"de", "da", "do", "das", "dos", "e", "a", "o"}


def person_initials(name: str | None) -> str:
    text = (name or "").strip()
    if not text:
        return ""
    if "@" in text:
        text = re.sub(r"[._\-]+", " ", text.split("@", 1)[0])
    if text.upper() == "TI":
        return "TI"
    words = [w for w in re.split(r"[\s/]+", text) if w and w.lower() not in _SMALL_WORDS]
    if not words:
        return text[:2].upper()
    if len(words) == 1:
        return words[0][:2].upper()
    return (words[0][0] + words[1][0]).upper()


def checklist_periods(event, today: date | None = None) -> dict:
    """Datas que separam os grupos por prazo: esta semana, próximas, semana do evento e pós-evento."""
    today = today or date.today()
    start, end = _event_date_bounds(event)
    start = start or today
    end = end or start
    sunday = today + timedelta(days=6 - today.weekday())
    event_week = max(start - timedelta(days=start.weekday()), sunday + timedelta(days=1))
    return {"today": today, "sunday": sunday, "event_week": event_week, "event_start": start, "event_end": end}


CHECKLIST_GROUPS = [
    ("atrasadas", "Atrasadas", "late"),
    ("semana", "Esta semana", "soon"),
    ("proximas", "Próximas semanas", "next"),
    ("evento", "Semana do evento", "event"),
    ("pos", "Pós-evento", "after"),
    ("sem_prazo", "Sem prazo definido", "none"),
    ("concluidas", "Concluídas e dispensadas", "done"),
]


def task_bucket(task, periods) -> str:
    if task["status"] in TASK_DONE_STATUSES:
        return "concluidas"
    due = normalize_date(task["due_date"])
    if not due:
        return "sem_prazo"
    day = date.fromisoformat(due)
    if day < periods["today"]:
        return "atrasadas"
    if day <= periods["sunday"]:
        return "semana"
    if day > periods["event_end"]:
        return "pos"
    if day >= periods["event_week"]:
        return "evento"
    return "proximas"


def task_view(task, periods, me: str | None = None) -> dict:
    """Dados de exibição de uma tarefa no checklist (texto e tom do prazo, responsável, grupo)."""
    status = task["status"]
    done = status in TASK_DONE_STATUSES
    due = normalize_date(task["due_date"])
    today = periods["today"]
    if done:
        due_text, tone = TASK_STATUSES.get(status, status), "done"
    elif not due:
        due_text, tone = "Sem prazo", "none"
    else:
        diff = (date.fromisoformat(due) - today).days
        short = f"{due[8:10]}/{due[5:7]}"
        if diff < 0:
            due_text, tone = f"Atrasada {-diff} dia" + ("" if diff == -1 else "s"), "late"
        elif diff == 0:
            due_text, tone = "Vence hoje", "soon"
        elif diff <= 6:
            due_text, tone = f"Em {diff} dia" + ("" if diff == 1 else "s") + f" · {short}", "soon"
        else:
            due_text, tone = short, "normal"
    who = (task["assigned_to"] or "").strip()
    relative = ""
    if due:
        delta = (periods["event_start"] - date.fromisoformat(due)).days
        if delta > 0:
            relative = f"{delta} dia{'s' if delta != 1 else ''} antes do evento"
        elif delta == 0:
            relative = "no dia do evento"
        else:
            relative = f"{-delta} dia{'s' if delta != -1 else ''} depois do evento"
    return {
        "done": done, "due_text": due_text, "tone": tone, "bucket": task_bucket(task, periods),
        "who": who, "initials": person_initials(who), "mine": bool(me and who and who.lower() == me.lower()),
        "status_label": TASK_STATUSES.get(status, status), "show_status": status in {"em_andamento", "aguardando_terceiro"},
        "relative": relative, "late": tone == "late",
    }


def checklist_counts(db, event, me: str | None = None, today: date | None = None) -> dict:
    periods = checklist_periods(event, today)
    tasks = db.execute("SELECT * FROM tasks WHERE event_id=?", (event["id"],)).fetchall()
    counts = {"total": len(tasks), "done": 0, "atrasadas": 0, "semana": 0, "sem_resp": 0, "minhas": 0}
    for task in tasks:
        view = task_view(task, periods, me)
        if view["done"]:
            counts["done"] += 1
            continue
        counts["atrasadas"] += view["bucket"] == "atrasadas"
        counts["semana"] += view["bucket"] == "semana"
        counts["sem_resp"] += not view["who"]
        counts["minhas"] += view["mine"]
    counts["pct"] = round(counts["done"] / counts["total"] * 100) if counts["total"] else 0
    return counts


def event_tab_info(event_id: int) -> dict:
    """Números exibidos nas abas do evento."""
    db = get_db()
    row = db.execute("""SELECT COUNT(*) total, SUM(CASE WHEN status IN ('concluida','nao_se_aplica') THEN 1 ELSE 0 END) done
                        FROM tasks WHERE event_id=?""", (event_id,)).fetchone()
    attachments = db.execute("SELECT COUNT(*) FROM event_attachments WHERE event_id=?", (event_id,)).fetchone()[0]
    return {"tasks_total": row["total"] or 0, "tasks_done": row["done"] or 0, "attachments": attachments}


app.jinja_env.globals["event_tab_info"] = event_tab_info

# Exporta também os nomes iniciados por "_" para os módulos de rotas.
__all__ = [name for name in dict(globals()) if not name.startswith("__")]
