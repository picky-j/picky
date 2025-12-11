#!/usr/bin/env python3
"""
사용자 벡터 기반 퀴즈 추천 시스템
사용자의 관심사 벡터와 유사한 퀴즈를 찾아서 JSON으로 반환
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
from sqlalchemy import text
from app.user_logs.profile_service import UserProfileService
from app.core.dependencies import get_profile_service

class QuizRecommendationService:
    """퀴즈 추천 서비스"""

    def __init__(self):
        self.qdrant_service = QdrantService()
        self.quiz_collection = "quizzes"
        self.user_collection = "user_profiles"

    async def get_user_vector(self, user_id: str) -> Optional[List[float]]:
        """사용자 ID로부터 프로필 벡터 조회"""
        try:
            print(f"👤 사용자 벡터 조회 중: {user_id}")

            # 프로필 서비스 가져오기
            profile_service = get_profile_service()

            # 캐싱된 프로필 벡터 조회
            profile_data = await profile_service.get_user_profile_vector_cached(user_id)

            if profile_data and profile_data.get("vector"):
                return list(profile_data['vector'])
            else:
                print(f"❌ 캐싱된 사용자 벡터를 찾을 수 없습니다.")
                return None

        except Exception as e:
            print(f"❌ 사용자 벡터 조회 실패: {e}")
            return None

    def get_quiz_details(self, quiz_ids: List[int]) -> Dict[int, Dict]:
        """MySQL에서 퀴즈 상세 정보 조회"""
        if not quiz_ids:
            return {}

        session = SessionLocal()
        try:
            # IN 절을 위해 quiz_ids를 문자열로 변환
            ids_str = ','.join(map(str, quiz_ids))

            query = text(f"""
                SELECT id, title, question, explanation
                FROM quiz
                WHERE id IN ({ids_str})
            """)

            result = session.execute(query)

            quiz_details = {}
            for row in result:
                quiz_details[row[0]] = {
                    "id": row[0],
                    "title": row[1] or "",
                    "question": row[2] or "",
                    "explanation": row[3] or ""
                }

            print(f"📋 퀴즈 상세 정보 조회 완료: {len(quiz_details)}개")
            return quiz_details

        except Exception as e:
            print(f"❌ 퀴즈 상세 정보 조회 실패: {e}")
            return {}
        finally:
            session.close()

    async def recommend_quizzes_by_user_id(self, user_id: str, limit: int = 500) -> List[Dict]:
        """사용자 ID 기반 퀴즈 추천"""
        try:
            # 1. 사용자 벡터 조회
            user_vector = await self.get_user_vector(user_id)
            if not user_vector:
                print(f"⚠️ 사용자 {user_id}의 벡터가 없어 추천할 수 없습니다.")
                return []

            # 2. 퀴즈 벡터와 유사도 검색
            print(f"🔍 Qdrant에서 유사 퀴즈 검색 중... (상위 {limit}개)")
            search_results = await self.qdrant_service.search_similar_vectors(
                collection_name=self.quiz_collection,
                query_vector=user_vector,
                limit=limit,
                score_threshold=0.1
            )

            if not search_results:
                print("❌ 유사한 퀴즈를 찾을 수 없습니다.")
                return []

            print(f"✅ Qdrant 검색 완료: {len(search_results)}개 퀴즈 발견")

            # 3. 퀴즈 ID 추출
            quiz_ids = []
            quiz_scores = {}
            for result in search_results:
                # Qdrant 결과에서 메타데이터 확인
                payload = result.payload if hasattr(result, 'payload') else result.get('payload', {})
                score = result.score if hasattr(result, 'score') else result.get('score', 0.0)

                quiz_id = payload.get('quiz_id') if payload else None
                if quiz_id:
                    quiz_ids.append(quiz_id)
                    quiz_scores[quiz_id] = float(score)

            if not quiz_ids:
                print("❌ 유효한 퀴즈 ID가 없습니다.")
                return []

            # 4. MySQL에서 퀴즈 상세 정보 조회
            quiz_details = self.get_quiz_details(quiz_ids)

            # 5. 결과 조합 (유사도 점수 포함)
            recommendations = []
            for quiz_id in quiz_ids:
                if quiz_id in quiz_details:
                    quiz_info = quiz_details[quiz_id].copy()
                    quiz_info['similarity_score'] = quiz_scores.get(quiz_id, 0.0)
                    recommendations.append(quiz_info)

            print(f"🎯 최종 추천 퀴즈: {len(recommendations)}개")
            return recommendations

        except Exception as e:
            print(f"❌ 퀴즈 추천 실패: {e}")
            import traceback
            traceback.print_exc()
            return []

    async def recommend_quizzes_by_vector(self, user_vector: List[float], limit: int = 20) -> List[Dict]:
        """사용자 벡터 직접 입력으로 퀴즈 추천"""
        try:
            print(f"🔍 벡터 기반 퀴즈 검색 중... (상위 {limit}개)")

            search_results = await self.qdrant_service.search_similar_vectors(
                collection_name=self.quiz_collection,
                query_vector=user_vector,
                limit=limit,
                score_threshold=0.1
            )

            if not search_results:
                print("❌ 유사한 퀴즈를 찾을 수 없습니다.")
                return []

            quiz_ids = []
            quiz_scores = {}
            for result in search_results:
                payload = result.payload if hasattr(result, 'payload') else result.get('payload', {})
                score = result.score if hasattr(result, 'score') else result.get('score', 0.0)

                quiz_id = payload.get('quiz_id') if payload else None
                if quiz_id:
                    quiz_ids.append(quiz_id)
                    quiz_scores[quiz_id] = float(score)

            quiz_details = self.get_quiz_details(quiz_ids)

            recommendations = []
            for quiz_id in quiz_ids:
                if quiz_id in quiz_details:
                    quiz_info = quiz_details[quiz_id].copy()
                    quiz_info['similarity_score'] = quiz_scores.get(quiz_id, 0.0)
                    recommendations.append(quiz_info)

            return recommendations

        except Exception as e:
            print(f"❌ 벡터 기반 퀴즈 추천 실패: {e}")
            return []


async def main():
    """테스트용 메인 함수"""
    print("=" * 60)
    print("🎯 퀴즈 추천 시스템 테스트")
    print("=" * 60)

    service = QuizRecommendationService()

    # 테스트 사용자로 추천
    test_user = "dummy-user@picky.com"
    print(f"\n🧪 테스트 사용자: {test_user}")

    recommendations = await service.recommend_quizzes_by_user_id(test_user, limit=10)

    if recommendations:
        print(f"\n📝 추천 퀴즈 결과:")
        for i, quiz in enumerate(recommendations, 1):
            print(f"{i}. [ID: {quiz['id']}] {quiz['title']}")
            print(f"   유사도: {quiz['similarity_score']:.3f}")
            print(f"   문제: {quiz['question']}")
            if quiz['explanation']:
                print(f"   설명: {quiz['explanation']}")
            print()
    else:
        print("❌ 추천할 퀴즈가 없습니다.")

if __name__ == "__main__":
    asyncio.run(main())
