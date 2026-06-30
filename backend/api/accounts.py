"""Account management API — CRUD for multi-account publishing (#5).

Each account pairs:
    - a name (UI label),
    - a platform (currently 'youtube'; 'tiktok' is reserved),
    - a Playwright cookies file (`cookies_path`),
    - a content preset it prefers (e.g. 'films_anime'),
    - an optional proxy URL (deferred per user — column reserved).

The 'default' account is seeded by the DB layer and is never deletable,
so legacy code paths using `account_id=None` keep working.
"""
import logging
import uuid

from fastapi import APIRouter, HTTPException

from backend.db import (
    list_accounts, get_account, create_account, update_account,
    delete_account, touch_account,
)
from backend.models import (
    Account, AccountCreate, AccountUpdate,
)
from backend.services.content_presets import PRESETS

logger = logging.getLogger(__name__)
router = APIRouter()


def _row_to_account(row: dict) -> Account:
    """Translate a DB row into the Pydantic Account model."""
    return Account(
        id=row["id"],
        name=row["name"],
        platform=row.get("platform", "youtube"),
        cookies_path=row.get("cookies_path"),
        proxy=row.get("proxy"),
        preferred_preset=row.get("preferred_preset", "default"),
        last_used_at=row.get("last_used_at"),
        created_at=row.get("created_at"),
    )


@router.get("/accounts", response_model=list[Account])
async def get_accounts():
    """All accounts, default row pinned to top, then most-recently used."""
    rows = await list_accounts()
    return [_row_to_account(r) for r in rows]


@router.get("/accounts/{account_id}", response_model=Account)
async def get_single_account(account_id: str):
    row = await get_account(account_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Account not found")
    return _row_to_account(row)


@router.post("/accounts", response_model=Account, status_code=201)
async def create_new_account(body: AccountCreate):
    """Mint a new account row. `id` is a UUID4; cookies_path is optional so
    the operator can create the row, sign in once in a real browser, export
    cookies, then PATCH the path in."""
    if body.preferred_preset not in PRESETS:
        raise HTTPException(
            status_code=400,
            detail=f"unknown preset: {body.preferred_preset!r} "
                   f"(known: {sorted(PRESETS)})",
        )
    acc_id = str(uuid.uuid4())
    await create_account({
        "id": acc_id,
        "name": body.name,
        "platform": body.platform,
        "cookies_path": body.cookies_path,
        "proxy": body.proxy,
        "preferred_preset": body.preferred_preset,
    })
    row = await get_account(acc_id)
    return _row_to_account(row)


@router.patch("/accounts/{account_id}", response_model=Account)
async def patch_account(account_id: str, body: AccountUpdate):
    if body.preferred_preset and body.preferred_preset not in PRESETS:
        raise HTTPException(
            status_code=400,
            detail=f"unknown preset: {body.preferred_preset!r}",
        )
    updates = body.model_dump(exclude_unset=True)
    if not updates:
        # No-op — return the unchanged row so the caller can still see it.
        row = await get_account(account_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Account not found")
        return _row_to_account(row)
    ok = await update_account(account_id, updates)
    if not ok:
        raise HTTPException(status_code=404, detail="Account not found")
    row = await get_account(account_id)
    return _row_to_account(row)


@router.delete("/accounts/{account_id}", status_code=204)
async def remove_account(account_id: str):
    if account_id == "default":
        raise HTTPException(
            status_code=400,
            detail="the 'default' account is the system fallback and "
                   "cannot be deleted. Create a new account and migrate "
                   "your uploads there instead.",
        )
    ok = await delete_account(account_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Account not found")


@router.post("/accounts/{account_id}/touch", response_model=Account)
async def mark_account_used(account_id: str):
    """Bump `last_used_at` to NOW — exposed so the UI can show a
    'this account is hot' dot after a successful publish."""
    row = await get_account(account_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Account not found")
    await touch_account(account_id)
    row = await get_account(account_id)
    return _row_to_account(row)
