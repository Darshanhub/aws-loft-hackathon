# app/gh_client.py
import os
import logging
from typing import List, Dict, Optional
from datetime import datetime, timezone
from github import Github, GithubException

log = logging.getLogger("gh_client")

# Modes:
#   review -> POST /pulls/{n}/reviews   (works even if Issues feature/permission is off)
#   issue  -> POST /issues/{n}/comments (PR conversation; needs Issues: write and repo setting enabled)
COMMENT_MODE = os.environ.get("GITHUB_COMMENT_MODE", "review").strip().lower()  # "review" | "issue"

def _client() -> Github:
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        raise RuntimeError("GITHUB_TOKEN is not set")
    return Github(token)

def comment_on_pr(owner: str, repo: str, pr_number: int, body: str) -> str:
    """
    Post a comment to a PR. Mode is controlled by GITHUB_COMMENT_MODE.
    - review: creates a top-level PR review (independent of Issues permission)
    - issue : creates a PR conversation (issue) comment
    Returns a URL you can open.
    """
    try:
        gh = _client()
        repository = gh.get_repo(f"{owner}/{repo}")
        pr = repository.get_pull(pr_number)

        mode = COMMENT_MODE if COMMENT_MODE in ("review", "issue") else "review"
        log.info("GitHub post: mode=%s owner=%s repo=%s pr=%s body_len=%s",
                 mode, owner, repo, pr_number, len(body or ""))

        if mode == "issue":
            # PR conversation comment (Issues API)
            c = pr.create_issue_comment(body)
            url = c.html_url
            log.info("GitHub post success (issue): url=%s", url)
            return url

        # Default: PR review comment
        rv = pr.create_review(body=body, event="COMMENT")
        url = f"https://github.com/{owner}/{repo}/pull/{pr_number}#pullrequestreview-{rv.id}"
        log.info("GitHub post success (review): id=%s url=%s", rv.id, url)
        return url

    except GithubException as ge:
        msg = getattr(ge, "data", None) or str(ge)
        log.error("GitHub API error (comment_on_pr): %s", msg)
        raise RuntimeError(f"GitHub API error (comment_on_pr): {msg}")
    except Exception as e:
        log.exception("GitHub client error (comment_on_pr)")
        raise RuntimeError(f"GitHub client error (comment_on_pr): {e}")

# ---------- (unchanged) sync helpers ----------

def _parse_since(since_iso: Optional[str]) -> Optional[datetime]:
    if not since_iso:
        return None
    s = since_iso.replace('Z', '+00:00')
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt

def _is_after(ts: Optional[datetime], since_dt: Optional[datetime]) -> bool:
    if not since_dt:
        return True
    if not ts:
        return False
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts >= since_dt

def fetch_pr_threads(owner: str, repo: str, pr_number: int, since_iso: Optional[str] = None) -> Dict[str, List[Dict]]:
    try:
        gh = _client()
        repository = gh.get_repo(f"{owner}/{repo}")
        pr = repository.get_pull(pr_number)

        since_dt = _parse_since(since_iso)

        issue_comments: List[Dict] = []
        for c in pr.as_issue().get_comments():
            if not _is_after(c.created_at, since_dt):
                continue
            issue_comments.append({
                "type": "issue_comment",
                "author": c.user.login if c.user else "unknown",
                "body": c.body or "",
                "created_at": c.created_at.isoformat(),
            })

        review_comments: List[Dict] = []
        for c in pr.get_comments():
            if not _is_after(c.created_at, since_dt):
                continue
            review_comments.append({
                "type": "review_comment",
                "author": c.user.login if c.user else "unknown",
                "body": c.body or "",
                "created_at": c.created_at.isoformat(),
                "path": getattr(c, "path", None),
                "position": getattr(c, "position", None),
            })

        reviews: List[Dict] = []
        for rv in pr.get_reviews():
            ts = rv.submitted_at
            if not _is_after(ts, since_dt):
                continue
            if rv.body:
                reviews.append({
                    "type": "review",
                    "author": rv.user.login if rv.user else "unknown",
                    "body": rv.body or "",
                    "state": rv.state,
                    "submitted_at": ts.isoformat() if ts else None,
                })

        return {"issue_comments": issue_comments, "review_comments": review_comments, "reviews": reviews}

    except GithubException as ge:
        msg = getattr(ge, "data", None) or str(ge)
        raise RuntimeError(f"GitHub API error (fetch_pr_threads): {msg}")
    except Exception as e:
        raise RuntimeError(f"GitHub client error (fetch_pr_threads): {e}")
