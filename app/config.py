from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    OLLAMA_HOST: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "qwen2.5:3b"
    CART_SERVICE_URL: str = "http://ustbite-cart-service-prod:8010"
    ORDER_SERVICE_URL: str = "http://ustbite-order-service-prod:8003"
    RESTAURANT_SERVICE_URL: str = "http://ustbite-restaurant-service-prod:8002"
    SERVICE_NAME: str = "ai-agent-service"
    LOG_LEVEL: str = "INFO"

    class Config:
        env_file = ".env"


settings = Settings()
