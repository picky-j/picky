"""
공통 임베딩 모델 로직
OpenAI API 또는 Sentence Transformers를 활용한 벡터화
"""

import logging
import os
from concurrent.futures import ThreadPoolExecutor
from typing import List
import asyncio
import numpy as np


logger = logging.getLogger(__name__)

# Sentence Transformers는 선택적 import
try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False
    SentenceTransformer = None


class EmbeddingService:
    """공통 임베딩 서비스 - 모든 도메인에서 사용"""

    def __init__(self):
        # Sentence Transformers 로컬 모델 사용
        # Hugging Face에서 모델을 다운로드하여 로컬에서 실행 (API 아님)
        
        self.embedding_model_name = os.getenv("EMBEDDING_MODEL", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
        self.executor = ThreadPoolExecutor(max_workers=4)
        self.local_model = None
        
        self._validate_config()
        self._initialize_model()

    def _validate_config(self):
        """임베딩 설정 검증"""
        if not SENTENCE_TRANSFORMERS_AVAILABLE:
            raise RuntimeError(
                "Sentence Transformers가 설치되지 않았습니다.\n"
                "설치: pip install sentence-transformers"
            )
        logger.info(f"[임베딩] Sentence Transformers 사용 모드 (모델: {self.embedding_model_name})")

    def _initialize_model(self):
        """로컬 모델 초기화"""
        if SENTENCE_TRANSFORMERS_AVAILABLE:
            try:
                logger.info(f"[임베딩] 모델 로딩 중: {self.embedding_model_name}")
                self.local_model = SentenceTransformer(self.embedding_model_name)
                logger.info("[임베딩] 모델 로딩 완료!")
            except Exception as e:
                raise RuntimeError(f"모델 로딩 실패: {e}")

    async def _encode_local(self, texts: List[str]) -> List[List[float]]:
        """Sentence Transformers를 사용한 벡터화 (로컬)"""
        if not self.local_model:
            raise RuntimeError("로컬 모델이 초기화되지 않았습니다.")
        
        # ThreadPoolExecutor를 사용하여 동기 함수를 비동기로 실행
        loop = asyncio.get_running_loop()

        def _run_encode():
            # Sentence Transformers는 2D numpy array를 반환
            return self.local_model.encode(
                texts,
                convert_to_numpy=True,  # numpy array로 변환
                show_progress_bar=False
            )

        embeddings = await loop.run_in_executor(
            self.executor,
            _run_encode
        )
        
        # numpy 2D 배열을 리스트의 리스트로 변환
        if isinstance(embeddings, np.ndarray):
            return embeddings.tolist()
        else:
            # 이미 리스트인 경우
            return [emb.tolist() if hasattr(emb, 'tolist') else list(emb) for emb in embeddings]

    async def _encode_async(self, texts: List[str]) -> List[List[float]]:
        """비동기식 텍스트 벡터화 (Sentence Transformers 로컬 모델 사용)"""
        return await self._encode_local(texts)

    async def encode(self, text: str) -> List[float]:
        """단일 텍스트를 벡터로 변환"""
        vectors = await self._encode_async([text])
        return vectors[0]

    async def encode_batch(self, texts: List[str]) -> List[List[float]]:
        """텍스트 리스트를 벡터로 변환 (배치)"""
        return await self._encode_async(texts)


# 전역 임베딩 서비스 인스턴스
embedding_service = EmbeddingService()
