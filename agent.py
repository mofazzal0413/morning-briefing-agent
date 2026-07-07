"""Morning Briefing Agent — Strands + OpenRouter + Gmail, Calendar, Slack."""

import os
import json
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from strands import Agent, tool
from strands.models.litellm import LiteLLMModel

load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN", "")

GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/calendar.readonly",
]

SYSTEM_PROMPT = """You are a morning briefing assistant.

Always call all three tools in this exact order:
1. check_gmail
2. check_calendar
3. check_slack

After gathering data from all three tools, synthesize a prioritized morning briefing
with these exact section headings:

URGENT
UPCOMING EVENTS
SLACK HIGHLIGHTS
OTHER EMAILS
SUGGESTED ACTIONS

Be concise and actionable. Prioritize time-sensitive items in URGENT."""


def get_google_credentials() -> Credentials:
    """Handle OAuth flow; read from token.json if it exists, save after auth."""
    creds = None
    token_path = "token.json"

    if os.path.exists(token_path) and os.path.getsize(token_path) > 0:
        try:
            creds = Credentials.from_authorized_user_file(token_path, GOOGLE_SCOPES)
        except (ValueError, json.JSONDecodeError):
            os.remove(token_path)
            creds = None

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", GOOGLE_SCOPES)
            creds = flow.run_local_server(port=0)
        with open(token_path, "w", encoding="utf-8") as token_file:
            token_file.write(creds.to_json())

    return creds


@tool
def check_gmail(hours_back: int = 12) -> str:
    """Fetch unread emails from the last N hours using the Gmail API.

    Args:
        hours_back: How many hours back to search for unread emails.

    Returns:
        Sender, subject, date, and a 200-character snippet per email.
    """
    creds = get_google_credentials()
    service = build("gmail", "v1", credentials=creds)

    query = f"is:unread newer_than:{hours_back}h"
    results = service.users().messages().list(userId="me", q=query, maxResults=20).execute()
    messages = results.get("messages", [])

    if not messages:
        return f"No unread emails in the last {hours_back} hours."

    lines = [f"Unread emails (last {hours_back} hours):"]
    for msg_meta in messages:
        msg = (
            service.users()
            .messages()
            .get(userId="me", id=msg_meta["id"], format="metadata", metadataHeaders=["From", "Subject", "Date"])
            .execute()
        )
        headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}
        sender = headers.get("From", "Unknown")
        subject = headers.get("Subject", "(No subject)")
        date = headers.get("Date", "Unknown date")
        snippet = msg.get("snippet", "")[:200]
        lines.append(f"- From: {sender} | Subject: {subject} | Date: {date} | Snippet: {snippet}")

    return "\n".join(lines)


@tool
def check_calendar(hours_ahead: int = 24) -> str:
    """Fetch upcoming calendar events for the next N hours.

    Args:
        hours_ahead: How many hours ahead to look for events.

    Returns:
        Title, start, end, location, and attendees for each event.
    """
    creds = get_google_credentials()
    service = build("calendar", "v3", credentials=creds)

    now = datetime.now(timezone.utc)
    end = now + timedelta(hours=hours_ahead)

    events_result = (
        service.events()
        .list(
            calendarId="primary",
            timeMin=now.isoformat(),
            timeMax=end.isoformat(),
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )
    events = events_result.get("items", [])

    if not events:
        return f"No calendar events in the next {hours_ahead} hours."

    lines = [f"Upcoming events (next {hours_ahead} hours):"]
    for event in events:
        title = event.get("summary", "(No title)")
        start = event["start"].get("dateTime", event["start"].get("date", "Unknown"))
        end_time = event["end"].get("dateTime", event["end"].get("date", "Unknown"))
        location = event.get("location", "No location")
        attendees = ", ".join(
            a.get("email", a.get("displayName", "Unknown")) for a in event.get("attendees", [])
        ) or "No attendees listed"
        lines.append(
            f"- Title: {title} | Start: {start} | End: {end_time} | "
            f"Location: {location} | Attendees: {attendees}"
        )

    return "\n".join(lines)


@tool
def check_slack(hours_back: int = 12, max_channels: int = 5) -> str:
    """Fetch recent messages from the most recently active Slack channels.

    Args:
        hours_back: How many hours back to search for messages.
        max_channels: Maximum number of channels to check.

    Returns:
        Channel name and up to 5 messages per channel.
    """
    if not SLACK_BOT_TOKEN:
        return "Slack: SLACK_BOT_TOKEN not set in .env"

    client = WebClient(token=SLACK_BOT_TOKEN)
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours_back)
    oldest = str(cutoff.timestamp())

    try:
        channels_response = client.conversations_list(
            types="public_channel,private_channel",
            exclude_archived=True,
            limit=200,
        )
    except SlackApiError as exc:
        return f"Slack error listing channels: {exc.response['error']}"

    channels = [ch for ch in channels_response.get("channels", []) if ch.get("is_member")]

    channel_activity: list[tuple[float, dict, list]] = []
    for channel in channels:
        try:
            history = client.conversations_history(
                channel=channel["id"],
                oldest=oldest,
                limit=5,
            )
        except SlackApiError:
            continue

        messages = history.get("messages", [])
        if messages:
            latest_ts = float(messages[0]["ts"])
            channel_activity.append((latest_ts, channel, messages))

    channel_activity.sort(key=lambda item: item[0], reverse=True)
    top_channels = channel_activity[:max_channels]

    if not top_channels:
        return f"No Slack messages in the last {hours_back} hours."

    lines = [f"Slack highlights (last {hours_back} hours, top {max_channels} channels):"]
    for _, channel, messages in top_channels:
        channel_name = channel.get("name", "unknown")
        lines.append(f"\n#{channel_name}:")
        for message in messages[:5]:
            text = message.get("text", "").replace("\n", " ")[:200]
            ts = datetime.fromtimestamp(float(message["ts"]), tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
            lines.append(f"  - [{ts}] {text}")

    return "\n".join(lines)


def run() -> None:
    """Create the agent and generate the morning briefing."""
    if not OPENROUTER_API_KEY or OPENROUTER_API_KEY.startswith("sk-or-your"):
        raise SystemExit(
            "OPENROUTER_API_KEY is missing or still a placeholder.\n"
            "1. Copy .env.example to .env (if needed)\n"
            "2. Get a key at https://openrouter.ai\n"
            "3. Add: OPENROUTER_API_KEY=sk-or-your-real-key"
        )

    model = LiteLLMModel(
        client_args={
            "api_key": OPENROUTER_API_KEY,
            "api_base": "https://openrouter.ai/api/v1",
        },
        model_id="openrouter/openrouter/free",
        params={"max_tokens": 4096},
    )

    agent = Agent(
        model=model,
        system_prompt=SYSTEM_PROMPT,
        tools=[check_gmail, check_calendar, check_slack],
    )

    response = agent("What did I miss? Give me my morning briefing.")
    print(response)


if __name__ == "__main__":
    run()
