import ast
from pathlib import Path


def _render_call(function_name: str) -> ast.Call:
    module = ast.parse(Path("app/main.py").read_text(encoding="utf-8"))
    function = next(
        node
        for node in module.body
        if isinstance(node, ast.FunctionDef) and node.name == function_name
    )
    return next(
        node
        for node in ast.walk(function)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "render_solana_discovery_page"
    )


def test_root_opens_trending_while_discovery_route_keeps_presenter_default():
    root_call = _render_call("app_home")
    discovery_call = _render_call("solana_discovery")

    root_defaults = {
        keyword.arg: ast.literal_eval(keyword.value)
        for keyword in root_call.keywords
        if keyword.arg == "initial_market_tab"
    }

    assert root_defaults == {"initial_market_tab": "trending"}
    assert all(
        keyword.arg != "initial_market_tab"
        for keyword in discovery_call.keywords
    )
