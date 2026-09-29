from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440

    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str = ""
    qdrant_collection: str = "upsc_corpus"

    ollama_host: str = "http://localhost:11434"
    embed_model: str = "nomic-embed-text:latest"
    chat_model: str = "qwen2.5:3b"

    # Set to 0 for a private installation with no daily question cap.
    free_tier_daily_limit: int = 0

    class Config:
        env_file = ".env"


settings = Settings()
