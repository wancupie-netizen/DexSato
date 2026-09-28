"""Render legacy Discovery history using only read-only SQLite queries."""

from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from html import escape
from pathlib import Path
from urllib.parse import quote, urlencode

from application.discovery_storage import discovery_storage_dir


class ArchiveUnavailable(RuntimeError):
    pass


def _open(directory: Path | None):
    database = (directory or discovery_storage_dir()) / "discovery_archive.sqlite3"
    if not database.is_file():
        raise ArchiveUnavailable("Archive is missing.")
    try:
        db = sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True, timeout=1)
        db.execute("PRAGMA query_only=ON")
        return db
    except (OSError, sqlite3.Error) as error:
        raise ArchiveUnavailable("Archive cannot be opened.") from error


def _symbol(payload_json, fallback):
    try:
        payload = json.loads(payload_json)
    except (TypeError, ValueError):
        return fallback
    if isinstance(payload, dict):
        symbol = payload.get("symbol")
        if isinstance(symbol, str) and symbol.strip():
            return symbol.strip()[:80]
    return fallback


def _page(title, body):
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        "<title>" + escape(title) + " · DexSato</title></head><body>"
        '<main><a href="/">DexSato markets</a><h1>' + escape(title) + "</h1>"
        "<p>Historical observations only. These are not current signals "
        "or trading instructions.</p>" + body + "</main></body></html>"
    )


def render_history_index(*, page=1, query="", directory=None):
    page = max(1, min(page, 10000))
    query = query.strip()[:100]
    where = (
        "WHERE instr(lower(token_address), lower(?)) > 0 "
        "OR instr(lower(pair_address), lower(?)) > 0"
    ) if query else ""
    params = (query, query) if query else ()
    try:
        with closing(_open(directory)) as db:
            total = db.execute(
                "SELECT count(*) FROM discoveries " + where, params
            ).fetchone()[0]
            rows = db.execute(
                "SELECT token_address, payload_json, last_qualified_at "
                "FROM discoveries " + where +
                " ORDER BY last_qualified_at DESC, token_address ASC "
                "LIMIT 25 OFFSET ?",
                (*params, (page - 1) * 25),
            ).fetchall()
    except (OSError, sqlite3.Error) as error:
        raise ArchiveUnavailable("Archive query failed.") from error

    items = []
    for address, payload, qualified_at in rows:
        href = "/discovery/solana/" + quote(address, safe="")
        items.append(
            '<li><a href="' + escape(href, quote=True) + '">' +
            escape(_symbol(payload, address)) + "</a> · " +
            escape(address) + " · Last qualified: " +
            escape(str(qualified_at or "unknown")) + "</li>"
        )

    body = "<p>Archived records: " + str(total) + "</p><ul>" + "".join(items) + "</ul>"
    if not items:
        body += "<p>No matching historical records.</p>"
    if page > 1:
        href = "/discovery/solana?" + urlencode({"page": page - 1, "q": query})
        body += '<a href="' + escape(href, quote=True) + '">Previous</a> '
    if page * 25 < total:
        href = "/discovery/solana?" + urlencode({"page": page + 1, "q": query})
        body += '<a href="' + escape(href, quote=True) + '">Next</a>'
    return _page("Discovery history", body)


def render_history_token(address, *, directory=None):
    if not address or len(address) > 100:
        return None
    try:
        with closing(_open(directory)) as db:
            row = db.execute(
                "SELECT pair_address, payload_json, first_qualified_at, "
                "last_qualified_at FROM discoveries WHERE token_address = ?",
                (address,),
            ).fetchone()
    except (OSError, sqlite3.Error) as error:
        raise ArchiveUnavailable("Archive query failed.") from error

    if row is None:
        return None
    pair, payload, first, last = row
    body = (
        "<p>Token: " + escape(address) + "</p>"
        "<p>Pair: " + escape(str(pair)) + "</p>"
        "<p>First qualified: " + escape(str(first)) + "</p>"
        "<p>Last qualified: " + escape(str(last)) + "</p>"
        '<p><a href="/discovery/solana">Back to history</a></p>'
    )
    return _page(_symbol(payload, address), body)
