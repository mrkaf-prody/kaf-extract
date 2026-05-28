"""Slack notification service for extraction results.

Posts formatted extraction results to a Slack channel via incoming webhook.
Users configure their Slack webhook URL in profile settings.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# Maximum Slack message size (blocks + text)
MAX_BLOCKS = 50
MAX_TEXT_LENGTH = 3000


def _build_slack_payload(
    url: str,
    status: str,
    data: dict[str, Any] | None,
    job_id: str | None = None,
    schedule_name: str | None = None,
) -> dict[str, Any]:
    """Build a Slack Block Kit message for extraction results.

    Returns a dict suitable for POST to Slack's chat.postMessage or incoming webhook.
    """
    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    emoji = "✅" if status == "success" else "❌"

    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"{emoji} Extraction {'Complete' if status == 'success' else 'Failed'}",
            },
        },
        {"type": "divider"},
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*URL:*\n{url}"},
                {"type": "mrkdwn", "text": f"*Status:*\n{status.upper()}"},
            ],
        },
    ]

    if schedule_name:
        blocks.append({
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Schedule:*\n{schedule_name}"},
                {"type": "mrkdwn", "text": f"*Time:*\n{now}"},
            ],
        })
    else:
        blocks.append({
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Job ID:*\n`{job_id or 'N/A'}`"},
                {"type": "mrkdwn", "text": f"*Time:*\n{now}"},
            ],
        })

    # Add extracted data preview (if success)
    if data and status == "success":
        # Format the data nicely
        data_preview = json.dumps(data, indent=2, ensure_ascii=False)
        if len(data_preview) > MAX_TEXT_LENGTH:
            data_preview = data_preview[:MAX_TEXT_LENGTH - 3] + "..."

        blocks.append({"type": "divider"})
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Extracted Data:*\n```{data_preview}```",
            },
        })

    # Limit blocks to avoid Slack API errors
    if len(blocks) > MAX_BLOCKS:
        blocks = blocks[:MAX_BLOCKS]

    return {
        "blocks": blocks,
        "text": f"{emoji} Extraction {status} for {url}",
    }


async def send_slack_notification(
    webhook_url: str,
    extraction_url: str,
    status: str,
    data: dict[str, Any] | None = None,
    job_id: str | None = None,
    schedule_name: str | None = None,
) -> bool:
    """Send an extraction result notification to Slack.

    Args:
        webhook_url: Slack incoming webhook URL.
        extraction_url: The URL that was extracted.
        status: 'success' or 'error'.
        data: Extracted data dict (shown in Slack message).
        job_id: Job identifier.
        schedule_name: Schedule name if this was a scheduled extraction.

    Returns:
        True if the notification was sent successfully, False otherwise.
    """
    payload = _build_slack_payload(
        url=extraction_url,
        status=status,
        data=data,
        job_id=job_id,
        schedule_name=schedule_name,
    )

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
            resp = await client.post(webhook_url, json=payload)
            if resp.is_success:
                logger.info("Slack notification sent for %s", extraction_url)
                return True
            else:
                logger.warning(
                    "Slack notification failed: HTTP %d — %s",
                    resp.status_code, resp.text[:200],
                )
                return False
    except Exception as exc:
        logger.error("Slack notification error: %s", exc)
        return False
