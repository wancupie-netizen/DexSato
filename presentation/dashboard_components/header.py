"""
DexSato Dashboard Header Component.

Responsibilities
----------------
- Render dashboard title
- Render token
- Render timestamp
- Render engine version

This component does NOT:
- calculate values
- access repositories
- mutate DashboardCard
"""

from __future__ import annotations

from html import escape


def render_dashboard_header(
    *,
    token: str,
    last_updated: str,
    engine_version: str,
) -> str:
    """
    Render Dashboard header.
    """

    return f"""
<div class="card">

<h1>DexSato</h1>

<p>

<strong>Token:</strong>
{escape(token)}

<br>

<strong>Updated:</strong>
{escape(last_updated)}

<br>

<strong>Engine:</strong>
{escape(engine_version)}

</p>

</div>
"""