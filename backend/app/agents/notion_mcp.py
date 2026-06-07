import asyncio
from app.core.logging import get_logger

import aiosqlite
import httpx

from app.config import settings

logger = get_logger(__name__)

NOTION_BASE_URL = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"
MAX_RETRIES = 3


def _make_headers(api_key: str) -> dict:
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Notion-Version": NOTION_VERSION,
    }


async def _post_with_backoff(client: httpx.AsyncClient, url: str, json: dict, headers: dict) -> dict:
    """POST to Notion with exponential backoff on 429 rate-limit responses.

    Retries up to MAX_RETRIES times. Delays are 2^attempt seconds:
    attempt 0 -> sleep(1s), attempt 1 -> sleep(2s), attempt 2 -> sleep(4s).
    After all retries are exhausted, makes one final attempt and raises on failure.
    """
    for attempt in range(MAX_RETRIES):
        response = await client.post(url, json=json, headers=headers)
        if response.status_code == 429:
            await asyncio.sleep(2 ** attempt)
            continue
        response.raise_for_status()
        return response.json()

    # Final attempt after MAX_RETRIES retries were all rate-limited
    response = await client.post(url, json=json, headers=headers)
    response.raise_for_status()
    return response.json()


async def run_notion_export(goal_id: str, api_key: str, parent_page_id: str) -> None:
    """Export a goal and its sessions to Notion as a background task.

    Creates a parent page for the goal under parent_page_id, then creates one
    child page per session (sequential). Writes the goal page URL back to the
    study_goals row in SQLite after export completes.
    """
    try:
        headers = _make_headers(api_key)

        # Fetch goal and sessions from the database
        async with aiosqlite.connect(settings.sqlite_path) as db:
            db.row_factory = aiosqlite.Row

            async with db.execute(
                "SELECT title FROM study_goals WHERE id = ?", (goal_id,)
            ) as cur:
                goal_row = await cur.fetchone()

            if goal_row is None:
                logger.error("run_notion_export: goal %s not found in DB", goal_id)
                return

            goal_title = goal_row["title"]

            async with db.execute(
                """SELECT session_number, title, notes_markdown
                   FROM study_sessions
                   WHERE goal_id = ?
                   ORDER BY session_number""",
                (goal_id,),
            ) as cur:
                sessions = await cur.fetchall()

        async with httpx.AsyncClient(timeout=30.0) as client:
            # Step 1 — Create goal parent page
            goal_body = {
                "parent": {"page_id": parent_page_id},
                "properties": {
                    "title": {
                        "title": [{"type": "text", "text": {"content": goal_title}}]
                    }
                },
            }
            goal_resp = await _post_with_backoff(
                client, f"{NOTION_BASE_URL}/pages", goal_body, headers
            )
            goal_page_id = goal_resp["id"]
            goal_page_url = goal_resp["url"]

            # Step 2 — Create one child page per session (sequential)
            for session in sessions:
                session_number = session["session_number"]
                session_title = session["title"]
                notes = session["notes_markdown"] or ""  # NULL fallback to empty string

                session_body = {
                    "parent": {"page_id": goal_page_id},
                    "properties": {
                        "title": {
                            "title": [
                                {
                                    "type": "text",
                                    "text": {
                                        "content": f"Session {session_number}: {session_title}"
                                    },
                                }
                            ]
                        }
                    },
                    "children": (
                        [
                            {
                                "object": "block",
                                "type": "paragraph",
                                "paragraph": {
                                    "rich_text": [
                                        {"type": "text", "text": {"content": notes}}
                                    ]
                                },
                            }
                        ]
                        if notes
                        else []
                    ),
                }
                await _post_with_backoff(
                    client, f"{NOTION_BASE_URL}/pages", session_body, headers
                )

        # Write URL back to DB
        async with aiosqlite.connect(settings.sqlite_path) as db:
            await db.execute(
                "UPDATE study_goals SET notion_page_url = ? WHERE id = ?",
                (goal_page_url, goal_id),
            )
            await db.commit()

        logger.info("run_notion_export: goal %s exported to %s", goal_id, goal_page_url)

    except Exception as e:
        logger.error("run_notion_export: export failed for goal %s: %s", goal_id, e)
