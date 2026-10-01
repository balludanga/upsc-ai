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

    # Handwriting OCR for uploaded answers.
    # rapidocr = local PP-OCR on CPU (no extra model download)
    # ollama-vision = Ollama vision model (needs a large local model)
    # auto = rapidocr when installed, otherwise ollama-vision
    ocr_engine: str = "rapidocr"

    # Mean recognition confidence below which the UI warns about misreads.
    ocr_min_confidence: float = 0.75

    # Vision model used only when OCR_ENGINE=ollama-vision.
    vision_model: str = "llava"

    # Upload / transcription limits.
    upload_max_files: int = 6
    upload_max_bytes: int = 15 * 1024 * 1024
    upload_max_pages: int = 8
    upload_render_dpi: int = 200

    # Set to 0 for a private installation with no daily question cap.
    free_tier_daily_limit: int = 0

    class Config:
        env_file = ".env"


settings = Settings()
