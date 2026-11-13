#!/usr/bin/env python3
"""Redefine the local FMABC Eventos admin password without deleting event data.

Place this file in the same folder as app.py and run it inside the project's
virtual environment: python redefinir_senha_admin.py
"""
from __future__ import annotations

import os
import re
import sqlite3
import sys
from datetime import datetime
from getpass import getpass
from pathlib import Path

try:
    from werkzeug.security import generate_password_hash
except ImportError:
    print("ERRO: dependências não encontradas. Ative o ambiente virtual e instale requirements.txt.")
    sys.exit(1)

BASE_DIR = Path(__file__).resolve().parent
ENV_FILE = BASE_DIR / ".env"


def read_dotenv(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def get_database_path() -> Path:
    env_values = read_dotenv(ENV_FILE)
    raw_path = os.environ.get("DATABASE_PATH")
    if raw_path is None:
        raw_path = env_values.get("DATABASE_PATH")
    if not raw_path:
        raw_path = str(BASE_DIR / "instance" / "fmabc_eventos.db")
    path = Path(raw_path)
    if not path.is_absolute():
        path = Path.cwd() / path
    return path.resolve()


def ask_email(prompt: str, default: str = "") -> str:
    while True:
        suffix = f" [{default}]" if default else ""
        value = input(f"{prompt}{suffix}: ").strip().lower() or default.lower()
        if len(value) <= 254 and re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
            return value
        print("Informe um endereço de e-mail válido.")


def ask_new_password() -> str:
    while True:
        password = getpass("Nova senha (mínimo de 6 caracteres; não será exibida): ")
        if len(password) < 6:
            print("A senha precisa ter pelo menos 6 caracteres.")
            continue
        confirmation = getpass("Digite a nova senha novamente: ")
        if password != confirmation:
            print("As senhas não coincidem. Tente novamente.")
            continue
        return password


def main() -> int:
    if not (BASE_DIR / "app.py").exists():
        print("ERRO: não encontrei app.py. Coloque este script na mesma pasta do projeto FMABC Eventos.")
        return 1

    db_path = get_database_path()
    print("\nRedefinição de senha — FMABC Eventos")
    print(f"Banco de dados selecionado: {db_path}")
    if not db_path.exists():
        print("ERRO: o banco não existe nesse caminho. Não foi criado nem alterado nenhum arquivo.")
        print("Confirme se o script está na mesma pasta do app.py e se DATABASE_PATH está correto no .env.")
        return 1

    try:
        with sqlite3.connect(str(db_path), timeout=10) as db:
            db.row_factory = sqlite3.Row
            table = db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'").fetchone()
            if not table:
                print("ERRO: o banco selecionado não contém a tabela de usuários. Nenhuma alteração feita.")
                return 1

            admins = db.execute(
                "SELECT id, email, role FROM users WHERE role='admin' ORDER BY email"
            ).fetchall()

            if admins:
                print("\nContas administrativas encontradas:")
                for index, row in enumerate(admins, start=1):
                    print(f"  {index}. {row['email']}")
                while True:
                    selection = input("Digite o número da conta para redefinir" + (" [1]" if len(admins) == 1 else "") + ": ").strip()
                    if not selection and len(admins) == 1:
                        selection = "1"
                    if selection.isdigit() and 1 <= int(selection) <= len(admins):
                        selected = admins[int(selection) - 1]
                        break
                    print("Seleção inválida.")
                old_email = selected["email"]
                new_email = ask_email("E-mail que será usado no login (Enter mantém o atual)", old_email)
                duplicate = db.execute("SELECT id FROM users WHERE email=? AND id<>?", (new_email, selected["id"])).fetchone()
                if duplicate:
                    print("ERRO: esse e-mail já pertence a outra conta. Nenhuma alteração feita.")
                    return 1
                password = ask_new_password()
                db.execute(
                    "UPDATE users SET email=?, password_hash=? WHERE id=?",
                    (new_email, generate_password_hash(password), selected["id"]),
                )
                db.commit()
                print("\nSenha redefinida com sucesso.")
                print(f"E-mail para login: {new_email}")
            else:
                print("\nNão encontrei contas com perfil administrador neste banco.")
                confirm = input("Deseja criar uma nova conta administrativa? Digite CRIAR para confirmar: ").strip()
                if confirm != "CRIAR":
                    print("Cancelado; nenhuma alteração feita.")
                    return 0
                email = ask_email("E-mail para a nova conta administrativa")
                if db.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone():
                    print("ERRO: esse e-mail já existe com outro perfil. Nenhuma alteração feita.")
                    return 1
                password = ask_new_password()
                created_at = datetime.now().replace(microsecond=0).isoformat(sep=" ")
                db.execute(
                    "INSERT INTO users(email, password_hash, role, created_at) VALUES (?, ?, 'admin', ?)",
                    (email, generate_password_hash(password), created_at),
                )
                db.commit()
                print("\nConta administrativa criada com sucesso.")
                print(f"E-mail para login: {email}")

    except sqlite3.Error as exc:
        print(f"ERRO no banco de dados: {exc}")
        return 1

    print("\nAgora volte a iniciar o servidor e entre em /login.")
    print("Por segurança, a senha não é mostrada na tela nem armazenada em texto puro.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
