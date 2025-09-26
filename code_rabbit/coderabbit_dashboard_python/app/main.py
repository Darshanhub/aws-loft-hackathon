import os
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from datetime import date, timedelta, datetime
from typing import Any, Dict, override
from pydantic import ValidationError
from .models import DashboardPayload
from . import cr_client
from fastapi import WebSocket, WebSocketDisconnect, Body
from fastapi.middleware.cors import CORSMiddleware
from .chat import init_db, append_message, list_messages
from . import gh_client
import aiosqlite

from dotenv import load_dotenv
load_dotenv(override=True)


app = FastAPI(title="CodeRabbit Review Dashboard (Python)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# static & templates
static_dir = os.path.join(os.path.dirname(__file__), "static")
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "templates"))
app.mount("/static", StaticFiles(directory=static_dir), name="static")

def date_input(d: date) -> str:
    return d.strftime("%Y-%m-%d")

def load_mock(from_date: str, to_date: str) -> Dict[str, Any]:
    import json, random
    from datetime import datetime, timedelta
    start = datetime.fromisoformat(from_date)
    end = datetime.fromisoformat(to_date)
    days = (end - start).days + 1
    trend = []
    for i in range(days):
        day = (start + timedelta(days=i)).date().isoformat()
        trend.append({
            "date": day,
            "issues": max(0, round(8 + 6 * __import__("math").sin(i/2) + (random.random()*2-1))),
            "prs": max(0, round(2 + 2 * __import__("math").cos(i/3) + (random.random()*2-1))),
            "mergeRate": max(0.0, min(1.0, 0.6 + 0.2 * __import__("math").sin(i/4))),
        })
    payload = {
        "window": {"from": from_date, "to": to_date},
        "totals": {
            "prsReviewed": 42,
            "issues": 128,
            "critical": 7,
            "reviewers": 9,
            "mergeRate": 0.71,
            "medianResponseHrs": 6.4,
        },
        "issuesBySeverity": [
            {"severity": "critical", "count": 7},
            {"severity": "high", "count": 22},
            {"severity": "medium", "count": 54},
            {"severity": "low", "count": 45},
        ],
        "suggestionsByType": [
            {"type": "security", "count": 16},
            {"type": "performance", "count": 21},
            {"type": "style", "count": 35},
            {"type": "maintainability", "count": 29},
            {"type": "tests", "count": 27},
        ],
        "developerActivity": [
            {"dev": "alice", "reviews": 11, "comments": 38, "avgResponseHrs": 3.1},
            {"dev": "bob", "reviews": 9, "comments": 22, "avgResponseHrs": 7.4},
            {"dev": "carol", "reviews": 7, "comments": 18, "avgResponseHrs": 4.9},
            {"dev": "dave", "reviews": 6, "comments": 14, "avgResponseHrs": 9.2},
        ],
        "trendDaily": trend,
        "prs": [
            {
                "id": 100 + i,
                "title": f"Improve API {i}",
                "author": ["alice","bob","carol","dave"][i % 4],
                "repo": "org/service",
                "openedAt": (start + timedelta(days=i)).date().isoformat(),
                "status": ["open","reviewed","merged"][i % 3],
                "issues": (i * 3) % 12,
                "critical": 1 if i % 7 == 0 else 0,
            } for i in range(min(12, days))
        ]
    }
    return payload

class ConnectionManager:
    def __init__(self):
        self.active: dict[tuple[str, str, int], set[WebSocket]] = {}

    async def connect(self, key, websocket: WebSocket):
        await websocket.accept()
        self.active.setdefault(key, set()).add(websocket)

    def disconnect(self, key, websocket: WebSocket):
        if key in self.active:
            self.active[key].discard(websocket)
            if not self.active[key]:
                del self.active[key]

    async def broadcast(self, key, message: dict):
        for ws in list(self.active.get(key, [])):
            try:
                await ws.send_json(message)
            except Exception:
                self.disconnect(key, ws)

manager = ConnectionManager()

@app.on_event("startup")
async def startup():
    await init_db()


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    today = date.today()
    return templates.TemplateResponse("index.html", {"request": request, "from": date_input(today - timedelta(days=14)), "to": date_input(today)})

@app.get("/api/report")
async def api_report(from_: str, to: str, mock: bool=False):
    # Validate dates format quickly
    try:
        datetime.fromisoformat(from_)
        datetime.fromisoformat(to)
    except Exception:
        raise HTTPException(400, detail="Invalid date format. Use YYYY-MM-DD")
    try:
        if mock or not os.environ.get("CODERABBIT_API_KEY"):
            payload = load_mock(from_, to)
        else:
            payload = cr_client.fetch_report(from_, to)
        # Validate/normalize into our schema
        model = DashboardPayload.model_validate(payload)
        return JSONResponse(model.model_dump(by_alias=True))
    except ValidationError as ve:
        raise HTTPException(502, detail=f"Schema validation error: {ve}")
    except Exception as e:
        raise HTTPException(502, detail=str(e))

@app.get("/chat/{owner}/{repo}/{pr}", response_class=HTMLResponse)
async def chat_ui(request: Request, owner: str, repo: str, pr: int):
    msgs = await list_messages(owner, repo, pr)
    return templates.TemplateResponse(
        "chat.html",
        {"request": request, "owner": owner, "repo": repo, "pr": pr, "messages": msgs},
    )

@app.websocket("/ws/{owner}/{repo}/{pr}")
async def ws_chat(websocket: WebSocket, owner: str, repo: str, pr: int):
    key = (owner, repo, pr)
    await manager.connect(key, websocket)
    try:
        while True:
            data = await websocket.receive_json()
            author = str(data.get("author", "anon"))
            role = str(data.get("role", "user"))
            content = str(data.get("content", "")).strip()
            if not content:
                continue
            msg_id = await append_message(owner, repo, pr, author, role, content)
            await manager.broadcast(
                key, {"id": msg_id, "author": author, "role": role, "content": content}
            )
    except WebSocketDisconnect:
        manager.disconnect(key, websocket)

@app.get("/api/chat/{owner}/{repo}/{pr}")
async def get_chat(owner: str, repo: str, pr: int, limit: int = 200):
    return await list_messages(owner, repo, pr, limit)

@app.post("/api/chat/{owner}/{repo}/{pr}")
async def post_chat(
    owner: str,
    repo: str,
    pr: int,
    author: str = Body(...),
    content: str = Body(...),
    role: str = Body("user"),
):
    msg_id = await append_message(owner, repo, pr, author, role, content)
    await manager.broadcast(
        (owner, repo, pr),
        {"id": msg_id, "author": author, "role": role, "content": content},
    )
    return {"id": msg_id}

@app.post("/api/github/comment/{owner}/{repo}/{pr}")
async def gh_comment(owner: str, repo: str, pr: int, body: str = Body(..., embed=True)):
    url = gh_client.comment_on_pr(owner, repo, pr, body)
    return {"url": url}

@app.delete("/api/chat/{owner}/{repo}/{pr}")
async def clear_chat(owner: str, repo: str, pr: int):
    async with aiosqlite.connect("chat.db") as db:
        await db.execute(
            "DELETE FROM messages WHERE owner=? AND repo=? AND pr=?",
            (owner, repo, pr)
        )
        await db.commit()
    return {"ok": True}

from fastapi import Body

@app.get("/api/coderabbit/report")
def coderabbit_report(from_: str, to: str):
    """
    Direct proxy to CodeRabbit metrics (no dashboard schema). Useful for debugging.
    """
    data = cr_client.fetch_report(from_, to)
    return JSONResponse(data)

@app.post("/api/coderabbit/sync/{owner}/{repo}")
async def coderabbit_sync(owner: str, repo: str, days: int = Body(7)):
    """
    Pull a recent window from CodeRabbit and post summarized insights into chat rooms
    (by PR if present; else a repo-level summary in PR #0).
    """
    from datetime import date, timedelta
    frm = (date.today() - timedelta(days=days)).strftime("%Y-%m-%d")
    to  = date.today().strftime("%Y-%m-%d")
    payload = cr_client.fetch_report(frm, to)

    # Try to map to PRs if present; otherwise drop a single summary into #0
    posted = 0
    prs = payload.get("prs") or []
    if prs:
        for p in prs:
            pr_num = p.get("number") or p.get("id") or 0
            summary = p.get("summary") or p.get("title") or "CodeRabbit: new review insights"
            await append_message(owner, repo, int(pr_num), "CodeRabbit", "coderabbit", summary)
            await manager.broadcast((owner, repo, int(pr_num)),
                                    {"author": "CodeRabbit", "role": "coderabbit", "content": summary})
            posted += 1
    else:
        # repo-level drop
        summary = f"[CodeRabbit] Insights {frm} → {to}"
        await append_message(owner, repo, 0, "CodeRabbit", "coderabbit", summary)
        await manager.broadcast((owner, repo, 0),
                                {"author": "CodeRabbit", "role": "coderabbit", "content": summary})
        posted = 1
    return {"ok": True, "posted": posted, "window": {"from": frm, "to": to}}

@app.post("/api/github/sync/{owner}/{repo}/{pr}")
async def gh_sync(owner: str, repo: str, pr: int, since: str = Body(None)):
    """
    Pull the latest PR comments/reviews from GitHub and mirror into chat.
    since: optional ISO8601 string to limit fetch window (e.g., "2025-09-25T00:00:00Z")
    """
    data = gh_client.fetch_pr_threads(owner, repo, pr, since_iso=since)
    posted = 0

    def role_for(author: str, body: str) -> str:
        a = (author or "").lower()
        if a in {"coderabbitai", "code-rabbit", "coderabbit"} or "coderabbit" in (body or "").lower():
            return "coderabbit"
        return "user"

    # Flatten & post
    for item in (data.get("issue_comments") or []):
        author, body = item["author"], item["body"]
        await append_message(owner, repo, pr, author, role_for(author, body), body)
        posted += 1

    for item in (data.get("review_comments") or []):
        author, body = item["author"], item["body"]
        # include file path context inline (optional)
        body2 = f"[{item.get('path','?')}]: {body}" if item.get('path') else body
        await append_message(owner, repo, pr, author, role_for(author, body2), body2)
        posted += 1

    for item in (data.get("reviews") or []):
        author, body = item["author"], item["body"]
        state = item.get("state")
        body2 = f"[{state}] {body}" if state else body
        await append_message(owner, repo, pr, author, role_for(author, body2), body2)
        posted += 1

    # Broadcast last few (optional: send none; they’ll be loaded on page open)
    await manager.broadcast((owner, repo, pr), {"author": "system", "role": "system",
                       "content": f"Synced {posted} GitHub messages"})
    return {"ok": True, "posted": posted}
