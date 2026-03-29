from __future__ import annotations

import json
import os
import smtplib
from email.message import EmailMessage
from typing import Any
from urllib.request import Request, urlopen


def deliver_report(markdown_report: str, page_data: dict[str, Any]) -> list[str]:
    results: list[str] = []
    title = page_data["title"]
    summary = "\n".join(f"- {line}" for line in page_data["executive_summary"])
    text_payload = f"{title}\n\n{summary}\n"

    feishu_url = os.getenv("FEISHU_WEBHOOK_URL")
    if feishu_url:
        _post_json(feishu_url, {"msg_type": "text", "content": {"text": text_payload}})
        results.append("feishu")

    wecom_url = os.getenv("WECOM_WEBHOOK_URL")
    if wecom_url:
        _post_json(wecom_url, {"msgtype": "markdown", "markdown": {"content": markdown_report[:3500]}})
        results.append("wecom")

    telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
    telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if telegram_token and telegram_chat_id:
        _post_json(
            f"https://api.telegram.org/bot{telegram_token}/sendMessage",
            {"chat_id": telegram_chat_id, "text": markdown_report[:3800]},
        )
        results.append("telegram")

    smtp_host = os.getenv("REPORT_EMAIL_SMTP_HOST")
    if smtp_host:
        _send_email(markdown_report, title)
        results.append("email")

    return results


def send_failure_notice(message: str) -> list[str]:
    payload = {"title": "GitHub Trends Workflow Failure", "executive_summary": [message]}
    return deliver_report(message, payload)


def _post_json(url: str, payload: dict[str, Any]) -> None:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = Request(
        url,
        data=data,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    with urlopen(request, timeout=20):
        return


def _send_email(markdown_report: str, subject: str) -> None:
    host = os.environ["REPORT_EMAIL_SMTP_HOST"]
    port = int(os.getenv("REPORT_EMAIL_SMTP_PORT", "587"))
    username = os.environ["REPORT_EMAIL_USERNAME"]
    password = os.environ["REPORT_EMAIL_PASSWORD"]
    from_addr = os.getenv("REPORT_EMAIL_FROM", username)
    to_addr = os.environ["REPORT_EMAIL_TO"]

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = from_addr
    message["To"] = to_addr
    message.set_content(markdown_report)

    with smtplib.SMTP(host, port, timeout=20) as server:
        server.starttls()
        server.login(username, password)
        server.send_message(message)
