from pydantic_ai.models.openrouter import (
    OpenRouterModel,
    OpenRouterModelSettings,
    OpenRouterProviderConfig,
)
from pydantic_ai.providers.openrouter import OpenRouterProvider

from config import EnvSettings
from http_client import http_client

env = EnvSettings()

model = OpenRouterModel(
    "deepseek/deepseek-v4-flash",
    provider=OpenRouterProvider(
        http_client=http_client, api_key=env.openrouter_api_key
    ),
    settings=OpenRouterModelSettings(
        openrouter_provider=OpenRouterProviderConfig(
            only=["deepinfra/fp4", "akashml/fp8", "digitalocean"],
            allow_fallbacks=False,
        ),
        thinking="medium",
    ),
)
