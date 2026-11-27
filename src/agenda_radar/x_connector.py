"""Optional, read-only X API adapter; no browser sessions or cookies."""

import httpx

from .network import FetchError
from .schemas import DocumentInput


def resolve_user(username: str, token: str):
    import re

    if not re.fullmatch(r"[A-Za-z0-9_]{1,15}", username):
        raise FetchError("invalid_x_username")
    with httpx.Client(timeout=20, follow_redirects=False) as client:
        response = client.get(f"https://api.x.com/2/users/by/username/{username}",
                              headers={"Authorization": f"Bearer {token}"})
    if response.status_code != 200:
        raise FetchError({401: "no_credentials", 403: "not_entitled", 429: "quota_exhausted"}
                         .get(response.status_code, "x_provider_error"))
    identifier = str(response.json().get("data", {}).get("id", ""))
    if not identifier.isdigit():
        raise FetchError("x_numeric_id_required")
    return identifier


def poll_x(source, token: str | None):
    if not token:
        raise FetchError("no_credentials")
    options = source.options or {}
    resource = "lists" if options.get("list_id") else "users"
    identifier = str(options.get("list_id") or options.get("user_id") or "")
    if not identifier.isdigit():
        raise FetchError("x_numeric_id_required")
    params: dict[str, str | int] = {"max_results": 100, "tweet.fields": "created_at,author_id"}
    cursor = options.get("since_id")
    if cursor and str(cursor).isdigit() and resource == "users":
        params["since_id"] = str(cursor)
    with httpx.Client(timeout=20, follow_redirects=False) as client:
        response = client.get(
            f"https://api.x.com/2/{resource}/{identifier}/tweets",
            params=params,
            headers={"Authorization": f"Bearer {token}"},
        )
    if response.status_code != 200:
        raise FetchError(
            {401: "no_credentials", 403: "not_entitled", 429: "quota_exhausted"}.get(
                response.status_code, "x_provider_error"
            )
        )
    from .ingest import parse_date

    body = response.json()
    items = [
        DocumentInput(
            url=f"https://x.com/i/status/{post['id']}",
            title=post["text"][:2000],
            external_id=post["id"],
            published_at=parse_date(post.get("created_at")),
            publisher=post.get("author_id"),
        )
        for post in body.get("data", [])
        if str(post.get("id", "")).isdigit()
    ]
    return items
