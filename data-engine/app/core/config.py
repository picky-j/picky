"""
앱 설정 및 환경변수 관리
"""

import os
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

class Settings:
    # MongoDB 설정
    MONGODB_URL: str = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
    # Redis 설정 
    _redis_url = os.getenv("REDIS_URL", "").strip()
    REDIS_URL: str = _redis_url if _redis_url and _redis_url.startswith("redis://") else "redis://redis:6379/1"
    
    # GMS 설정 (벡터화용)
    GMS_KEY: str = os.getenv("GMS_KEY", "")
    GMS_BASE_URL: str = "https://gms.ssafy.io/gmsapi/api.openai.com/v1"
    
    # Qdrant 설정
    QDRANT_HOST: str = os.getenv("QDRANT_HOST", "localhost")
    QDRANT_PORT: int = int(os.getenv("QDRANT_PORT", "6333"))
    
    # 앱 설정
    APP_NAME: str = "Picky Data Engine"
    VERSION: str = "2.0.0"
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"

settings = Settings()