from typing import Literal

from pydantic import BaseModel
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    YamlConfigSettingsSource,
)


class EnvSettings(BaseSettings):
    openrouter_api_key: str
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


class MCPConfig(BaseModel):
    enable: bool
    type: Literal["http"]
    url: str
    headers: dict[str, str] | None = None


class Config(BaseSettings):
    skill_dir: str
    mcpServers: dict[str, MCPConfig]
    model_config = SettingsConfigDict(
        yaml_file="config.yaml", extra="ignore", case_sensitive=True
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        **kwargs,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (
            init_settings,
            YamlConfigSettingsSource(settings_cls),
        )
