from typing import Any
from src.core.logging import get_logger

logger = get_logger(__name__)

def format_results_for_slack(
    question: str,
    sql: str,
    results: list[dict[str, Any]]
) -> list[dict]:

    if not results:
        return [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Query returned no results.*\n```{sql}```"
                }
            }
        ]

    # build preview table (max 10 rows)
    preview = results[:10]
    headers = list(preview[0].keys())

    # header row
    col_width = 15
    header_row = " | ".join(h.upper().ljust(col_width) for h in headers)
    divider = "-+-".join("-" * col_width for _ in headers)
    data_rows = "\n".join(
        " | ".join(str(row.get(h, "")).ljust(col_width) for h in headers)
        for row in preview
    )

    table = f"{header_row}\n{divider}\n{data_rows}"
    total_rows = len(results)
    note = f"_Showing {min(10, total_rows)} of {total_rows} rows_"

    blocks = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f":mag: *Question:* {question}"
            }
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Generated SQL:*\n```{sql}```"
            }
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Results:*\n```{table}```\n{note}"
            }
        },
        {"type": "divider"},
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": ":arrow_down: Export CSV",
                        "emoji": True
                    },
                    "style": "primary",
                    "action_id": "export_csv",
                    "value": question  # pass question so we can fetch from cache on click
                }
            ]
        }
    ]

    return blocks


def format_error_for_slack(question: str, error: str) -> list[dict]:
    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f":x: *Failed to process:* _{question}_"
            }
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Error:*\n```{error}```"
            }
        }
    ]