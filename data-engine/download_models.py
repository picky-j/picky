#!/usr/bin/env python3
"""
Docker 빌드 시 모델 사전 다운로드 스크립트
"""

import os
import logging
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def download_kobart_model():
    """KoBART 요약 모델 다운로드"""
    model_name = "EbanLee/kobart-summary-v3"

    try:
        logger.info(f"🔄 KoBART 모델 다운로드 시작: {model_name}")

        # 토크나이저 다운로드
        logger.info("📦 토크나이저 다운로드 중...")
        tokenizer = AutoTokenizer.from_pretrained(model_name)

        # 모델 다운로드
        logger.info("🤖 모델 다운로드 중...")
        model = AutoModelForSeq2SeqLM.from_pretrained(model_name)

        logger.info("✅ KoBART 모델 다운로드 완료!")
        logger.info(f"📍 캐시 위치: {os.path.expanduser('~/.cache/huggingface/transformers')}")

    except Exception as e:
        logger.error(f"❌ 모델 다운로드 실패: {e}")
        raise

def download_embedding_model():
    """Sentence Transformers 임베딩 모델 다운로드"""
    # 환경 변수에서 모델명 가져오기 (기본값 사용)
    model_name = os.getenv("EMBEDDING_MODEL", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
    
    try:
        # sentence-transformers가 설치되어 있는지 확인
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError:
            logger.warning("⚠️ sentence-transformers가 설치되지 않았습니다. 임베딩 모델 다운로드를 건너뜁니다.")
            return
        
        logger.info(f"🔄 임베딩 모델 다운로드 시작: {model_name}")
        
        # Sentence Transformer 모델 다운로드 (자동으로 캐시됨)
        model = SentenceTransformer(model_name)
        
        logger.info("✅ 임베딩 모델 다운로드 완료!")
        logger.info(f"📍 캐시 위치: {os.path.expanduser('~/.cache/huggingface/hub')}")
        
    except Exception as e:
        logger.error(f"❌ 임베딩 모델 다운로드 실패: {e}")
        # 임베딩 모델 다운로드 실패는 치명적이지 않음 (런타임에 재시도 가능)
        logger.warning("⚠️ 임베딩 모델은 런타임에 자동으로 다운로드됩니다.")

if __name__ == "__main__":
    download_kobart_model()
    download_embedding_model()