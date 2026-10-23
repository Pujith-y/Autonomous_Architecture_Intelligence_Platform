from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str
    APP_VERSION: str
    DEBUG: bool

    POSTGRES_HOST: str
    POSTGRES_PORT: int
    POSTGRES_DB: str
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str

    NEO4J_URI: str
    NEO4J_USERNAME: str
    NEO4J_PASSWORD: str

    QDRANT_HOST: str
    QDRANT_PORT: int

    SECRET_KEY: str
    ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int

    MODEL_NAME: str
    VECTOR_SIZE: int

    LLM_PROVIDER: str = "openai"
    LLM_MODEL: str = "gpt-4o-mini"
    LLM_API_KEY: str | None = None
    LLM_BASE_URL: str | None = None
    LLM_TEMPERATURE: float = 0.1
    LLM_MAX_TOKENS: int = 1000

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True
    )


settings = Settings()