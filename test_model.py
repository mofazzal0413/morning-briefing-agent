"""Verify OpenRouter connection via Strands + LiteLLM."""

import os

from dotenv import load_dotenv
from strands import Agent
from strands.models.litellm import LiteLLMModel

load_dotenv()

api_key = os.getenv("OPENROUTER_API_KEY", "")
if not api_key or api_key.startswith("sk-or-your"):
    raise SystemExit(
        "OPENROUTER_API_KEY is missing or still a placeholder.\n"
        "Add your key to .env: OPENROUTER_API_KEY=sk-or-..."
    )

model = LiteLLMModel(
    client_args={
        "api_key": api_key,
        "api_base": "https://openrouter.ai/api/v1",
    },
    model_id="openrouter/openrouter/free",
    params={"max_tokens": 512},
)

agent = Agent(model=model)
response = agent("Say hello and tell me what model you are in one sentence.")
print(response)
