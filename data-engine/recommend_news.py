#!/usr/bin/env python3
"""
사용자 벡터 기반 뉴스 추천 시스템
사용자의 관심사 벡터와 유사한 뉴스 20개를 찾아서 JSON으로 반환
"""

import asyncio
import json
import sys
import os
from datetime import datetime
from typing import List, Dict, Optional

# 프로젝트 루트를 Python path에 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.vectorization.qdrant_client import QdrantService
from app.core.mysql_db import SessionLocal
from app.news.models import News
from app.user_logs.profile_service import UserProfileService
from app.core.dependencies import get_profile_service

class NewsRecommendationService:
    """뉴스 추천 서비스"""

    def __init__(self):
        self.qdrant_service = QdrantService()
        self.news_collection = "news"
        self.user_collection = "user_profiles"  # 사용자 벡터 컬렉션

    async def get_user_vector(self, user_id: str) -> Optional[List[float]]:
        """사용자 ID로부터 프로필 벡터 조회 (Redis 캐싱 포함)

        Args:
            user_id: 사용자 ID

        Returns:
            사용자 프로필 벡터 또는 None
        """
        try:
            print(f"👤 사용자 벡터 조회 중: {user_id}")

            # 프로필 서비스 가져오기
            profile_service = get_profile_service()

            # 캐싱된 프로필 벡터 조회
            profile_data = await profile_service.get_user_profile_vector_cached(user_id)

            if profile_data and profile_data.get("vector"):
                vector = profile_data["vector"]
                print(f"✅ 사용자 벡터 발견: {len(vector)}차원")
                return list(vector)
            else:
                print(f"❌ 사용자 {user_id}의 벡터를 찾을 수 없습니다.")
                return None

        except Exception as e:
            print(f"❌ 사용자 벡터 조회 실패: {e}")
            return None

    async def recommend_news_by_user_id(
        self,
        user_id: str,
        limit: int = 500,
        score_threshold: float = 0.2
    ) -> List[Dict]:
        """사용자 ID로 뉴스 추천

        Args:
            user_id: 사용자 ID
            limit: 추천할 뉴스 개수
            score_threshold: 최소 유사도 점수

        Returns:
            추천 뉴스 리스트
        """

        # 1. 사용자 벡터 조회
        user_vector = await self.get_user_vector(user_id)
        if not user_vector:
            print(f"❌ 사용자 {user_id}의 프로필 벡터를 찾을 수 없습니다.")
            return []

        # 2. 벡터 기반 뉴스 추천
        return await self.get_similar_news(
            user_vector=user_vector,
            limit=limit,
            score_threshold=score_threshold
        )

    async def get_similar_news(
        self,
        user_vector: List[float],
        limit: int = 500,
        score_threshold: float = 0.2
    ) -> List[Dict]:
        """사용자 벡터와 유사한 뉴스 검색

        Args:
            user_vector: 사용자 관심사 벡터
            limit: 반환할 뉴스 개수
            score_threshold: 최소 유사도 점수

        Returns:
            뉴스 리스트 (JSON 형태)
        """

        try:
            # 1. Qdrant에서 유사 벡터 검색
            print(f"🔍 Qdrant에서 유사 뉴스 검색 중... (상위 {limit}개)")
            search_results = await self.qdrant_service.search_similar_vectors(
                collection_name=self.news_collection,
                query_vector=user_vector,
                limit=limit,
                score_threshold=score_threshold
            )

            if not search_results:
                print("❌ 유사한 뉴스를 찾을 수 없습니다.")
                return []

            print(f"✅ {len(search_results)}개 유사 벡터 발견")

            # 2. 뉴스 ID 추출 (메타데이터에서 news_id 가져오기)
            news_ids = []
            vector_scores = {}

            for result in search_results:
                # Qdrant 결과에서 메타데이터 확인
                payload = result.payload if hasattr(result, 'payload') else result.get('payload', {})

                # news_id 추출 (여러 가능한 키 확인)
                news_id = payload.get('news_id') or payload.get('id') or payload.get('news_id')

                if news_id:
                    news_ids.append(int(news_id))
                    vector_scores[int(news_id)] = float(result.score if hasattr(result, 'score') else result.get('score', 0))
                else:
                    print(f"⚠️ 뉴스 ID를 찾을 수 없음: {payload}")

            if not news_ids:
                print("❌ 유효한 뉴스 ID를 찾을 수 없습니다.")
                return []

            # 3. DB에서 뉴스 정보 조회
            print(f"📰 DB에서 뉴스 정보 조회 중... ({len(news_ids)}개)")
            news_list = await self._get_news_from_db(news_ids)

            # 4. 유사도 점수와 함께 결과 구성
            result_news = []
            for news in news_list:
                news_data = {
                    "news_id": news.id,
                    "title": news.title,
                    "url": news.url,
                    "summary": news.summary,
                    "category_id": news.category_id,
                    "published_at": news.published_at.isoformat() if news.published_at else None,
                    "created_at": news.created_at.isoformat() if news.created_at else None,
                    "similarity_score": vector_scores.get(news.id, 0.0)
                }
                result_news.append(news_data)

            # 5. 유사도 점수순으로 정렬
            result_news.sort(key=lambda x: x['similarity_score'], reverse=True)

            print(f"✅ {len(result_news)}개 뉴스 추천 완료")
            return result_news

        except Exception as e:
            print(f"❌ 뉴스 추천 실패: {e}")
            return []

    async def _get_news_from_db(self, news_ids: List[int]) -> List[News]:
        """DB에서 뉴스 정보 조회"""
        session = SessionLocal()
        try:
            news_list = session.query(News).filter(News.id.in_(news_ids)).all()
            return news_list
        finally:
            session.close()

    async def recommend_news_to_json(
        self,
        user_id: str,
        limit: int = 20,
        output_file: Optional[str] = None
    ) -> str:
        """사용자 ID 기반 뉴스 추천 후 JSON 파일 생성

        Args:
            user_id: 사용자 ID
            limit: 추천할 뉴스 개수
            output_file: 출력 파일명 (None이면 자동 생성)

        Returns:
            생성된 JSON 파일 경로
        """

        # 뉴스 추천
        recommended_news = await self.recommend_news_by_user_id(user_id, limit)

        if not recommended_news:
            print(f"❌ 사용자 {user_id}에 대한 추천 뉴스가 없습니다.")
            return ""

        # JSON 데이터 구성
        json_data = {
            "user_id": user_id,
            "recommended_at": datetime.now().isoformat(),
            "total_count": len(recommended_news),
            "recommended_news": recommended_news
        }

        # 파일명 생성 (호스트 마운트 경로에 저장)
        if output_file is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            # 호스트와 공유되는 경로에 저장
            output_file = f"/app/recommended_news_{timestamp}.json"

        # JSON 파일 저장
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(json_data, f, ensure_ascii=False, indent=2)

            print(f"✅ 추천 뉴스 JSON 저장 완료: {output_file}")
            print(f"📊 총 {len(recommended_news)}개 뉴스 추천됨")

            return output_file

        except Exception as e:
            print(f"❌ JSON 파일 저장 실패: {e}")
            return ""


# ====== 테스트 및 사용 예시 ======
async def recommend_for_user(user_id: str, limit: int = 20):
    """특정 사용자에 대한 뉴스 추천"""
    service = NewsRecommendationService()

    print(f"🎯 사용자 {user_id}에 대한 뉴스 추천 시작...")

    # 뉴스 추천 및 JSON 생성
    json_file = await service.recommend_news_to_json(
        user_id=user_id,
        limit=limit
    )

    if json_file:
        print(f"\n🎉 추천 완료!")
        print(f"📄 생성된 파일: {json_file}")
        print(f"👤 사용자: {user_id}")
        print(f"📊 추천 뉴스 개수: {limit}개")
        print(f"\n💡 파일 복사 명령어:")
        print(f"docker cp picky-data-engine:{json_file} ~/Desktop/picky/data-engine/S13P21C102/data-engine/")
    else:
        print(f"\n❌ 사용자 {user_id}에 대한 추천 실패!")

    return json_file


if __name__ == "__main__":
    import argparse

    # 명령행 인자 처리
    parser = argparse.ArgumentParser(description="사용자 ID 기반 뉴스 추천")
    parser.add_argument("user_id", help="사용자 ID (예: dummy-user@picky.com)")
    parser.add_argument("--limit", type=int, default=20, help="추천할 뉴스 개수 (기본값: 20)")

    args = parser.parse_args()

    # 뉴스 추천 실행
    asyncio.run(recommend_for_user(args.user_id, args.limit))
