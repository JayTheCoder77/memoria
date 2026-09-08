from __future__ import annotations

import json
from typing import Annotated, Any

import typer
from memoria_cloud import DEFAULT_BASE_URL, Memoria
from memoria_cloud.errors import MemoriaAuthError, MemoriaError
from memoria_cloud.models import Memory
from rich.console import Console
from rich.table import Table

from memoria_cloud_cli import config as cfg

app = typer.Typer(no_args_is_help=True, add_completion=False)
console = Console()
err_console = Console(stderr=True)

ApiKeyOpt = Annotated[str | None, typer.Option("--api-key", help="mem_... key")]
UrlOpt = Annotated[str | None, typer.Option("--url", help="Memory API base URL")]
SessionOpt = Annotated[str | None, typer.Option("--session", help="session id")]


def make_client(*, api_key: str | None, url: str | None) -> Memoria:
    settings = cfg.load_file()
    return Memoria(
        api_key=cfg.resolve_key(flag=api_key, file=settings),
        base_url=cfg.resolve_url(flag=url, file=settings) or DEFAULT_BASE_URL,
    )


def _fail(exc: BaseException, *, code: int) -> None:
    err_console.print(f"[red]{exc}[/red]")
    raise typer.Exit(code) from exc


def _require_session(session_id: str | None) -> str:
    if session_id:
        return session_id
    err_console.print(
        "[red]session id required (--session, MEMORY_SESSION_ID, or config)[/red]"
    )
    raise typer.Exit(1)


def _run(action: Any) -> Any:
    try:
        return action()
    except MemoriaAuthError as exc:
        _fail(exc, code=2)
    except MemoriaError as exc:
        _fail(exc, code=1)


def _memory_table(memories: list[Memory], *, title: str) -> Table:
    table = Table(title=title)
    table.add_column("id", overflow="fold")
    table.add_column("type")
    table.add_column("session")
    table.add_column("score")
    table.add_column("content")
    for memory in memories:
        score = "" if memory.score is None else f"{memory.score:.3f}"
        table.add_row(
            str(memory.id),
            memory.memory_type,
            memory.session_id,
            score,
            memory.content,
        )
    return table


@app.callback()
def main(
    ctx: typer.Context,
    api_key: ApiKeyOpt = None,
    url: UrlOpt = None,
) -> None:
    ctx.ensure_object(dict)
    ctx.obj["api_key"] = api_key
    ctx.obj["url"] = url


@app.command()
def remember(
    ctx: typer.Context,
    text: Annotated[str, typer.Argument(help="Memory content")],
    memory_type: Annotated[str, typer.Option("--type")] = "semantic",
    importance: Annotated[float, typer.Option("--importance")] = 0.5,
    session: SessionOpt = None,
) -> None:
    settings = cfg.load_file()
    session_id = _require_session(cfg.resolve_session(flag=session, file=settings))
    client = make_client(api_key=ctx.obj["api_key"], url=ctx.obj["url"])
    memory = _run(
        lambda: client.remember(
            content=text,
            session_id=session_id,
            memory_type=memory_type,
            importance=importance,
        )
    )
    console.print(f"[green]remembered[/green] {memory.id}")


@app.command()
def recall(
    ctx: typer.Context,
    query: Annotated[str, typer.Argument()],
    limit: Annotated[int, typer.Option("--limit")] = 10,
    session: SessionOpt = None,
    as_of: Annotated[str | None, typer.Option("--as-of")] = None,
    explain: Annotated[bool, typer.Option("--explain")] = False,
) -> None:
    settings = cfg.load_file()
    client = make_client(api_key=ctx.obj["api_key"], url=ctx.obj["url"])
    result = _run(
        lambda: client.recall(
            q=query,
            session_id=cfg.resolve_session(flag=session, file=settings),
            limit=limit,
            as_of=as_of,
            explain=explain,
        )
    )
    console.print(_memory_table(result.memories, title="recall"))


@app.command("list")
def list_memories(
    ctx: typer.Context,
    session: SessionOpt = None,
    memory_type: Annotated[str | None, typer.Option("--type")] = None,
    q: Annotated[str | None, typer.Option("-q", "--query")] = None,
) -> None:
    settings = cfg.load_file()
    client = make_client(api_key=ctx.obj["api_key"], url=ctx.obj["url"])
    result = _run(
        lambda: client.list_memories(
            session_id=cfg.resolve_session(flag=session, file=settings),
            memory_type=memory_type,
            q=q,
        )
    )
    console.print(_memory_table(result.memories, title="memories"))


@app.command()
def facts(
    ctx: typer.Context,
    limit: Annotated[int, typer.Option("--limit")] = 50,
    offset: Annotated[int, typer.Option("--offset")] = 0,
) -> None:
    client = make_client(api_key=ctx.obj["api_key"], url=ctx.obj["url"])
    rows = _run(lambda: client.kv_facts(limit=limit, offset=offset))
    table = Table(title="kv facts")
    table.add_column("type")
    table.add_column("entity")
    table.add_column("value")
    table.add_column("memory_id")
    for row in rows:
        table.add_row(row.fact_type, row.entity, row.value or "", str(row.memory_id))
    console.print(table)


@app.command()
def graph(
    ctx: typer.Context,
    all_edges: Annotated[bool, typer.Option("--all", help="Include invalid edges")] = False,
    limit: Annotated[int, typer.Option("--limit")] = 50,
    offset: Annotated[int, typer.Option("--offset")] = 0,
) -> None:
    client = make_client(api_key=ctx.obj["api_key"], url=ctx.obj["url"])
    rows = _run(lambda: client.graph_edges(valid_only=not all_edges, limit=limit, offset=offset))
    table = Table(title="graph edges")
    table.add_column("subject")
    table.add_column("relation")
    table.add_column("object")
    table.add_column("valid")
    table.add_column("memory_id")
    for row in rows:
        table.add_row(
            row.subject,
            row.relation,
            row.object,
            "yes" if row.valid else "no",
            "" if row.memory_id is None else str(row.memory_id),
        )
    console.print(table)


@app.command()
def update(
    ctx: typer.Context,
    memory_id: Annotated[str, typer.Argument()],
    content: Annotated[str | None, typer.Option("--content")] = None,
    importance: Annotated[float | None, typer.Option("--importance")] = None,
    memory_type: Annotated[str | None, typer.Option("--type")] = None,
) -> None:
    client = make_client(api_key=ctx.obj["api_key"], url=ctx.obj["url"])
    memory = _run(
        lambda: client.update(
            memory_id,
            content=content,
            importance=importance,
            memory_type=memory_type,
        )
    )
    console.print(f"[green]updated[/green] {memory.id}")


@app.command()
def forget(
    ctx: typer.Context,
    memory_id: Annotated[str, typer.Argument()],
) -> None:
    client = make_client(api_key=ctx.obj["api_key"], url=ctx.obj["url"])
    _run(lambda: client.forget(memory_id))
    console.print(f"[green]forgotten[/green] {memory_id}")


@app.command()
def emit(
    ctx: typer.Context,
    event_type: Annotated[str, typer.Option("--type")] = "message",
    session: SessionOpt = None,
    payload: Annotated[str | None, typer.Option("--payload", help="JSON object")] = None,
) -> None:
    settings = cfg.load_file()
    session_id = _require_session(cfg.resolve_session(flag=session, file=settings))
    body: dict[str, Any] = {}
    if payload:
        try:
            parsed = json.loads(payload)
        except json.JSONDecodeError as exc:
            err_console.print(f"[red]invalid --payload JSON: {exc}[/red]")
            raise typer.Exit(1) from exc
        if not isinstance(parsed, dict):
            err_console.print("[red]--payload must be a JSON object[/red]")
            raise typer.Exit(1)
        body = parsed
    client = make_client(api_key=ctx.obj["api_key"], url=ctx.obj["url"])
    result = _run(
        lambda: client.emit(session_id=session_id, event_type=event_type, payload=body)
    )
    console.print(f"[green]{result.status}[/green]" + (f" {result.id}" if result.id else ""))


@app.command()
def health(ctx: typer.Context) -> None:
    client = make_client(api_key=ctx.obj["api_key"], url=ctx.obj["url"])
    result = _run(lambda: client.health())
    console.print(result.get("status", "ok"))


@app.command()
def config(
    api_key: Annotated[str | None, typer.Option("--api-key")] = None,
    url: Annotated[str | None, typer.Option("--url")] = None,
    session: Annotated[str | None, typer.Option("--session")] = None,
) -> None:
    current = cfg.load_file()
    if api_key is None and url is None and session is None:
        console.print(f"path: {cfg.CONFIG_PATH}")
        console.print(f"api_url: {current.api_url or '(not set)'}")
        console.print(f"api_key: {cfg.redact_key(current.api_key)}")
        console.print(f"session_id: {current.session_id or '(not set)'}")
        return
    updated = cfg.Settings(
        api_url=url if url is not None else current.api_url,
        api_key=api_key if api_key is not None else current.api_key,
        session_id=session if session is not None else current.session_id,
    )
    cfg.save_file(updated)
    console.print(f"[green]wrote[/green] {cfg.CONFIG_PATH}")
    console.print(f"api_key: {cfg.redact_key(updated.api_key)}")
