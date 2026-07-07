# Morning Briefing Agent

Build a working AI agent that checks Gmail, Google Calendar, and Slack, then synthesizes a prioritized morning briefing.

## Stack

| Component | Job |
|-----------|-----|
| **Strands** | Manages the agent loop |
| **LiteLLM** | Connects Strands to OpenRouter |
| **OpenRouter** | Free LLM gateway (`openrouter/openrouter/free`) |
| **Tools** | `check_gmail`, `check_calendar`, `check_slack` |

## Setup

### 1. Virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate   # Mac/Linux
pip install -r requirements.txt
```

### 2. Environment variables

```bash
cp .env.example .env
```

Add your keys to `.env`:
- `OPENROUTER_API_KEY` — from [openrouter.ai](https://openrouter.ai)
- `SLACK_BOT_TOKEN` — User OAuth Token (`xoxp-...`) from [api.slack.com/apps](https://api.slack.com/apps)

### 3. Verify OpenRouter connection

```bash
python3 test_model.py
```

Expected: a one-sentence greeting from the model.

### 4. Google credentials

1. Create a project at [Google Cloud Console](https://console.cloud.google.com)
2. Enable **Gmail API** and **Google Calendar API**
3. Configure OAuth consent screen (External)
4. Create OAuth client ID (Desktop app)
5. Download JSON → save as `credentials.json` in this folder
6. First run opens a browser for sign-in → creates `token.json` automatically

### 5. Slack token

1. Create app at [api.slack.com/apps](https://api.slack.com/apps)
2. Add **User Token Scopes**: `channels:read`, `channels:history`, `groups:read`, `groups:history`
3. Install to workspace → copy User OAuth Token (`xoxp-...`)
4. Add to `.env` as `SLACK_BOT_TOKEN`

## Run

```bash
python3 agent.py
```

The agent calls all three tools, then synthesizes a briefing with sections:
**URGENT**, **UPCOMING EVENTS**, **SLACK HIGHLIGHTS**, **OTHER EMAILS**, **SUGGESTED ACTIONS**

## Test tools individually

```bash
python3 -c "from agent import check_gmail; print(check_gmail(hours_back=24))"
python3 -c "from agent import check_calendar; print(check_calendar(hours_ahead=24))"
python3 -c "from agent import check_slack; print(check_slack(hours_back=24))"
```

## Files (never commit secrets)

| File | Committed? |
|------|------------|
| `agent.py`, `test_model.py` | Yes |
| `.env`, `credentials.json`, `token.json` | **No** |
