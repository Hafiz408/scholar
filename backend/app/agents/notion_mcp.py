import asyncio
from app.core.logging import get_logger

import httpx

from sqlalchemy import select, update
from app.core.database import get_session
from app.models.db_models import StudyGoal, StudySession

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
    study_goals row in Postgres after export completes.
    """
    try:
        headers = _make_headers(api_key)

        # Fetch goal and sessions from the database
        async with get_session() as session:
            goal_obj = (
                await session.execute(
                    select(StudyGoal).where(StudyGoal.id == goal_id)
                )
            ).scalar_one_or_none()

            if goal_obj is None:
                logger.error("run_notion_export: goal %s not found in DB", goal_id)
                return

            goal_title = goal_obj.title

            sessions = (
                await session.execute(
                    select(StudySession)
                    .where(StudySession.goal_id == goal_id)
                    .order_by(StudySession.session_number)
                )
            ).scalars().all()

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
            for sess in sessions:
                session_number = sess.session_number
                session_title = sess.title
                notes = sess.notes_markdown or ""  # NULL fallback to empty string

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
        async with get_session() as session:
            await session.execute(
                update(StudyGoal)
                .where(StudyGoal.id == goal_id)
                .values(notion_page_url=goal_page_url)
            )
            await session.commit()

        logger.info("run_notion_export: goal %s exported to %s", goal_id, goal_page_url)

    except Exception as e:
        logger.error("run_notion_export: export failed for goal %s: %s", goal_id, e)
