from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    github_token: str | None = None
    gh_api_token: str | None = None
    github_repository: str | None = None

    yandex_iam_token: str | None = None
    yandex_folder_id: str | None = None
    yandex_model: str = "yandexgpt-lite"

    openai_api_key: str | None = None
    openai_model: str = "gpt-4.1-mini"

    log_level: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )


settings = Settings()