"""Camada de compatibilidade de banco de dados (SQLite local / PostgreSQL em produção).

O sistema foi escrito pensando em SQLite (um arquivo local). Isso funciona bem
na sua máquina, mas em um serviço como o Render, sem um disco persistente
pago, o arquivo do banco é apagado a cada novo deploy. Para hospedar de graça
e manter os dados, a opção é um PostgreSQL gerenciado gratuito (ex.: Neon).

Esta camada escolhe o backend pela variável de ambiente DATABASE_URL:
    - vazia/ausente            -> SQLite, no arquivo indicado por DATABASE_PATH
                                   (exatamente como o sistema sempre funcionou).
    - "postgres://..." ou
      "postgresql://..."       -> PostgreSQL, via psycopg2.

O resto do sistema (sistema/core.py, eventos.py, checklist.py, etc.) continua
escrevendo as consultas no "dialeto" do SQLite usado desde o início: `?` como
marcador de parâmetro, `INSERT OR IGNORE`, `PRAGMA table_info(tabela)`, `LIKE`
sempre tratado como "sem diferenciar maiúsculas/minúsculas". As funções deste
módulo traduzem automaticamente essas instruções para o equivalente em
PostgreSQL, para não ser necessário reescrever as consultas espalhadas pelos
módulos de rotas.

Se algo der errado na tradução de uma consulta nova no futuro, o primeiro
lugar a olhar é a função `_translate_for_postgres` abaixo.
"""
from __future__ import annotations

import os
import re
import sqlite3
from pathlib import Path

DATABASE_URL = (os.getenv("DATABASE_URL") or "").strip()
USE_POSTGRES = DATABASE_URL.startswith("postgres://") or DATABASE_URL.startswith("postgresql://")

if USE_POSTGRES:
    import psycopg2
    import psycopg2.extras

    # Algumas plataformas (Heroku, e por tabela o próprio Render) fornecem a URL
    # com o prefixo antigo "postgres://"; psycopg2 aceita os dois, mas normalizamos
    # para evitar qualquer surpresa com bibliotecas mais estritas no futuro.
    _PG_DSN = DATABASE_URL.replace("postgres://", "postgresql://", 1)


# Única tabela cuja chave primária não é um "id" numérico (não recebe
# "RETURNING id" automático em seus INSERTs — veja _translate_for_postgres).
_TABELAS_SEM_ID_SERIAL = {"app_settings"}

_PRAGMA_TABLE_INFO = re.compile(r"^\s*PRAGMA\s+table_info\(\s*(\w+)\s*\)\s*;?\s*$", re.IGNORECASE)
_INSERT_OR_IGNORE = re.compile(r"INSERT\s+OR\s+IGNORE\s+INTO", re.IGNORECASE)
_LIKE_WORD = re.compile(r"\bLIKE\b", re.IGNORECASE)
_INSERT_INTO_TABLE = re.compile(r"^\s*INSERT\s+INTO\s+(\w+)", re.IGNORECASE)


def _translate_for_postgres(sql: str, add_returning: bool = True) -> str:
    """Converte uma instrução no dialeto do SQLite usado neste sistema para PostgreSQL.

    `add_returning=False` é usado pelo executemany (carga inicial de dados em lote):
    não faz sentido pedir o id de volta quando são várias linhas de uma vez, e o
    psycopg2 não devolve isso em lote mesmo."""
    translated = sql

    # INSERT OR IGNORE -> INSERT ... ON CONFLICT DO NOTHING (mesmo efeito prático
    # nas 3 tabelas em que é usado: evita duplicar uma linha já existente).
    if _INSERT_OR_IGNORE.search(translated):
        translated = _INSERT_OR_IGNORE.sub("INSERT INTO", translated)
        if "ON CONFLICT" not in translated.upper():
            translated = translated.rstrip().rstrip(";") + " ON CONFLICT DO NOTHING"

    # O SQLite trata LIKE como "sem diferenciar maiúsculas/minúsculas" para ASCII;
    # a busca do sistema depende disso, então usamos ILIKE (equivalente no Postgres).
    translated = _LIKE_WORD.sub("ILIKE", translated)

    # Criação de tabela: SERIAL assume o papel do AUTOINCREMENT; COLLATE NOCASE não
    # existe no Postgres (o e-mail já é sempre gravado em minúsculas pela aplicação
    # antes de qualquer INSERT/UPDATE, então a comparação de login não depende disso).
    translated = translated.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "SERIAL PRIMARY KEY")
    translated = translated.replace(" COLLATE NOCASE", "")

    # cursor.lastrowid (usado após alguns INSERTs) não existe no psycopg2; simulamos
    # acrescentando "RETURNING id" nos INSERTs de tabelas que têm chave "id" serial.
    stripped = translated.strip()
    if add_returning and stripped[:6].upper() == "INSERT" and "RETURNING" not in translated.upper():
        match = _INSERT_INTO_TABLE.search(translated)
        table = match.group(1).lower() if match else None
        if table and table not in _TABELAS_SEM_ID_SERIAL:
            translated = translated.rstrip().rstrip(";") + " RETURNING id"

    # Marcadores de parâmetro posicionais: o sistema sempre usa "?" (nunca um "%"
    # literal dentro do texto da consulta — os valores com "%" de buscas vão como
    # parâmetro, não dentro da string SQL), então esta troca é sempre segura.
    translated = translated.replace("?", "%s")
    return translated


class _PGCursorWrapper:
    """Deixa um cursor do psycopg2 parecido com um cursor do sqlite3: acesso a
    linhas por índice ou por nome (via DictCursor) e `.lastrowid` após INSERT."""

    def __init__(self, cursor):
        self._cursor = cursor
        self.lastrowid = None

    def fetchone(self):
        return self._cursor.fetchone()

    def fetchall(self):
        return self._cursor.fetchall()

    def __iter__(self):
        return iter(self._cursor)

    @property
    def rowcount(self):
        return self._cursor.rowcount


class PostgresConnection:
    """Encapsula uma conexão psycopg2 para aceitar o mesmo uso que o sistema já
    faz com sqlite3.Connection: `.execute(sql, params)`, `.executescript(sql)`,
    `.commit()`, `.rollback()`, `.close()`."""

    def __init__(self, dsn: str):
        self._conn = psycopg2.connect(dsn)

    def execute(self, sql: str, params=()):
        pragma_match = _PRAGMA_TABLE_INFO.match(sql)
        cur = self._conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        if pragma_match:
            # PRAGMA table_info(tabela) -> lista de colunas via information_schema.
            # O sistema só usa a coluna "name" do resultado do PRAGMA, por isso é
            # só isso que precisamos fornecer aqui.
            cur.execute(
                "SELECT column_name AS name FROM information_schema.columns "
                "WHERE table_schema = 'public' AND table_name = %s "
                "ORDER BY ordinal_position",
                (pragma_match.group(1),),
            )
            return _PGCursorWrapper(cur)

        translated = _translate_for_postgres(sql)
        cur.execute(translated, tuple(params) if params else None)
        wrapper = _PGCursorWrapper(cur)
        if "RETURNING" in translated.upper() and translated.strip().upper().startswith("INSERT"):
            row = cur.fetchone()
            wrapper.lastrowid = row[0] if row else None
        return wrapper

    def executemany(self, sql: str, seq_of_params) -> None:
        """Usado nas cargas iniciais (modelos de checklist, itens de apoio),
        que inserem várias linhas de uma vez. Sem RETURNING — não é usado
        para pegar o id de cada linha, só para popular o banco na primeira vez."""
        translated = _translate_for_postgres(sql, add_returning=False)
        cur = self._conn.cursor()
        cur.executemany(translated, [tuple(params) for params in seq_of_params])

    def executescript(self, script: str) -> None:
        # psycopg2 não tem um equivalente direto a sqlite3.executescript; como o
        # próprio sistema já garante que os blocos de schema não têm ";" dentro
        # de valores de texto, executar instrução por instrução é seguro aqui.
        for statement in script.split(";"):
            statement = statement.strip()
            if statement:
                self.execute(statement)

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()


def connect(sqlite_path: Path | None = None):
    """Abre uma conexão nova (fora do contexto do Flask), usando o backend
    configurado em DATABASE_URL. Usada tanto por get_db() (uma por requisição)
    quanto pelas rotinas que rodam em segundo plano (envio de e-mails, lembretes)."""
    if USE_POSTGRES:
        return PostgresConnection(_PG_DSN)
    conn = sqlite3.connect(sqlite_path, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn
