"""
사용자 프로필 벡터 생성 및 관리 서비스
GPT_recommend.md의 증분 갱신 공식 구현
"""

import asyncio
import hashlib
import logging
import numpy as np
import uuid
from typing import Dict, List, Optional
from ..core.database import get_database, get_collection_name, get_url_hash
from ..vectorization.embeddings import embedding_service
from ..vectorization.qdrant_client import QdrantService
from ..core.redis_client import redis_cache

logger = logging.getLogger(__name__)

# 17개 카테고리 정의 (setup_categories.py와 동일)
CATEGORIES = [
    "정치", "사회", "경제", "기술", "과학", "건강",
    "교육", "문화", "엔터테인먼트", "스포츠", "역사",
    "환경", "여행", "생활", "가정", "종교", "철학"
]


class UserProfileService:
    """사용자 프로필 벡터 생성 및 관리"""

    def __init__(self):
        self.qdrant_service = QdrantService()
        self.user_locks = {}  # 사용자별 asyncio.Lock

    def _get_deterministic_profile_id(self, user_id: str) -> str:
        """사용자 ID 기반으로 고유한 프로필 Point ID 생성 (UUID 형식)"""
        # SHA-256 해시를 사용해 동일한 user_id에 대해 항상 같은 ID 생성
        hash_input = f"user_profile_{user_id}".encode('utf-8')
        hash_hex = hashlib.sha256(hash_input).hexdigest()
        # UUID 형식으로 변환 (8-4-4-4-12)
        uuid_format = f"{hash_hex[:8]}-{hash_hex[8:12]}-{hash_hex[12:16]}-{hash_hex[16:20]}-{hash_hex[20:32]}"
        return uuid_format

    def _calculate_weight(self, data: dict) -> float:
        """사용자 행동 기반 가중치 계산 (visitCount 가중가중치 문제 해결)"""
        base_weight = 1.0

        # 체류시간 기반 가중치 (30초 이상이면 가중치 증가)
        time_spent = data.get('timeSpent', 0)
        if time_spent > 30:
            base_weight += min((time_spent - 30) / 60, 2.0)  # 최대 3.0

        # 스크롤 깊이 기반 가중치 (50% 이상이면 가중치 증가)
        scroll_depth = data.get('maxScrollDepth', 0)
        if scroll_depth > 50:
            base_weight += (scroll_depth - 50) / 100  # 최대 0.5 추가

        # visitCount는 메타데이터로만 저장, 가중치 계산에서 제외 (가중가중치 문제 방지)
        # 대신 히스토리 데이터의 경우 typedCount 비율을 활용
        if data.get('dataType') == 'history':
            typed_count = data.get('typedCount', 0)
            visit_count = data.get('visitCount', 1)
            typed_ratio = typed_count / max(visit_count, 1)

            if typed_ratio > 0.3:  # 30% 이상 직접 타이핑
                base_weight += 0.5  # 의도성 보너스

        return round(base_weight, 3)

    def _prepare_text_for_embedding(self, data: dict) -> str:
        """브라우징/히스토리 데이터에서 임베딩용 텍스트 추출"""
        combined_text = ""

        if 'content' in data:
            content = data['content']
            clean_title = content.get('cleanTitle', '').strip()
            clean_content = content.get('cleanContent', '')[:1500].strip()

            if clean_title and clean_content:
                combined_text = f"{clean_title} {clean_content}"
            elif clean_title:
                combined_text = clean_title
            elif clean_content:
                combined_text = clean_content

        return combined_text.strip()

    async def _classify_and_update_categories(self, valid_data: List[Dict], vectors: List[List[float]], collection):
        """벡터 기반 카테고리 분류 및 MongoDB 업데이트"""
        logger.info(f"[카테고리 분류] {len(vectors)}개 URL 카테고리 분류 시작")

        try:
            # 17개 카테고리 벡터 가져오기 (setup_categories.py로 미리 저장된 것)
            category_vectors = await self._get_category_vectors()

            if not category_vectors:
                logger.warning("[카테고리 분류] 카테고리 벡터를 찾을 수 없습니다. setup_categories.py를 먼저 실행하세요.")
                return

            # 각 URL 벡터와 카테고리 벡터 비교
            categories_assigned = []
            bulk_updates = []

            for i, (data, vector) in enumerate(zip(valid_data, vectors)):
                # 코사인 유사도 계산
                similarities = []
                for category, cat_vector in category_vectors.items():
                    similarity = self._cosine_similarity(vector, cat_vector)
                    similarities.append((category, similarity))

                # 가장 유사한 카테고리 선택
                best_category, best_score = max(similarities, key=lambda x: x[1])
                categories_assigned.append(best_category)

                # MongoDB 업데이트 쿼리 준비
                bulk_updates.append({
                    "_id": data["_id"],
                    "category": best_category,
                    "category_score": round(best_score, 3)
                })

                if i < 5:  # 처음 5개만 로깅
                    logger.info(f"  URL: {data.get('url', '')[:50]}... → {best_category} (유사도: {best_score:.3f})")

            # MongoDB 벌크 업데이트
            if bulk_updates:
                await self._bulk_update_categories(collection, bulk_updates)

            # 카테고리별 통계
            category_stats = {}
            for cat in categories_assigned:
                category_stats[cat] = category_stats.get(cat, 0) + 1

            logger.info(f"[카테고리 통계] {dict(sorted(category_stats.items(), key=lambda x: x[1], reverse=True))}")

        except Exception as e:
            logger.error(f"[카테고리 분류 에러] {e}")

    async def _get_category_vectors(self) -> Dict[str, List[float]]:
        """Qdrant에서 17개 카테고리 벡터 가져오기"""
        try:
            category_vectors = {}
            for i, category in enumerate(CATEGORIES):
                point_id = i  # 정수 ID 사용 (0, 1, 2, ...)
                point = await self.qdrant_service.get_point("user_logs", point_id)
                if point and point.get("vector"):
                    category_vectors[category] = point["vector"]

            logger.info(f"[카테고리 벡터] {len(category_vectors)}개 카테고리 벡터 로드 완료")
            return category_vectors

        except Exception as e:
            logger.error(f"[카테고리 벡터 로드 에러] {e}")
            return {}

    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """코사인 유사도 계산"""
        vec1_np = np.array(vec1)
        vec2_np = np.array(vec2)

        dot_product = np.dot(vec1_np, vec2_np)
        norm1 = np.linalg.norm(vec1_np)
        norm2 = np.linalg.norm(vec2_np)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return dot_product / (norm1 * norm2)

    async def _bulk_update_categories(self, collection, bulk_updates: List[Dict]):
        """MongoDB 벌크 카테고리 업데이트"""
        try:
            from pymongo import UpdateOne

            operations = []
            for update in bulk_updates:
                operations.append(UpdateOne(
                    {"_id": update["_id"]},
                    {"$set": {
                        "category": update["category"],
                        "categoryScore": update["category_score"]
                    }}
                ))

            if operations:
                result = await collection.bulk_write(operations)
                logger.info(f"[MongoDB 업데이트] {result.modified_count}개 문서 카테고리 업데이트 완료")

        except Exception as e:
            logger.error(f"[MongoDB 업데이트 에러] {e}")

    async def create_initial_profile_from_history(self, user_id: str, limit: int = 500) -> Dict:
        """히스토리 데이터로부터 초기 user_profile 생성 (중복 생성 방지)"""
        logger.info(f"[프로필 생성] 사용자 {user_id}의 초기 프로필 생성 시작")

        try:
            # 사용자별 고유 Point ID 생성
            profile_point_id = self._get_deterministic_profile_id(user_id)

            # 기존 프로필 존재 여부 확인 (Point ID로 직접 조회)
            existing_profile = await self.qdrant_service.get_point("user_profiles", profile_point_id)
            if existing_profile:
                logger.info(f"[건너뛰기] 사용자 {user_id}의 프로필이 이미 존재합니다 (Point ID: {profile_point_id})")
                return {
                    "success": False,
                    "message": "사용자 프로필이 이미 존재합니다.",
                    "existing_profile": {
                        "user_id": user_id,
                        "point_id": profile_point_id,
                        "weight_sum": existing_profile.get("payload", {}).get("weight_sum"),
                        "log_count": existing_profile.get("payload", {}).get("log_count"),
                        "created_from": existing_profile.get("payload", {}).get("created_from")
                    }
                }
            # MongoDB에서 히스토리 데이터 조회
            database = get_database()
            collection_name = get_collection_name(user_id, 'history')
            collection = database[collection_name]

            logger.info(f"[데이터 조회] 샤드 {collection_name}에서 최대 {limit}개 조회")
            cursor = collection.find({"userId": user_id}).sort("savedAt", -1).limit(limit)
            history_data = await cursor.to_list(length=limit)

            if not history_data:
                return {"success": False, "message": "히스토리 데이터가 없습니다."}

            logger.info(f"[데이터 수집] {len(history_data)}개 히스토리 데이터 수집")

            # 텍스트 추출 및 임베딩 생성
            texts_for_embedding = []
            weights = []
            valid_data = []

            for data in history_data:
                combined_text = self._prepare_text_for_embedding(data)

                if combined_text.strip():  # 빈 콘텐츠만 제외
                    texts_for_embedding.append(combined_text)
                    weights.append(self._calculate_weight(data))
                    valid_data.append(data)

            if not texts_for_embedding:
                return {"success": False, "message": "임베딩 가능한 히스토리 데이터가 없습니다."}

            logger.info(f"[임베딩 생성] {len(texts_for_embedding)}개 텍스트 임베딩 시작")

            # 배치 임베딩 생성 (청크 단위로 처리하여 GMS API 크기 제한 해결)
            chunk_size = 20
            vectors = []
            for i in range(0, len(texts_for_embedding), chunk_size):
                chunk = texts_for_embedding[i:i + chunk_size]
                logger.info(f"  → {i+1}~{min(i+chunk_size, len(texts_for_embedding))}번째 텍스트 임베딩 중...")
                chunk_vectors = await embedding_service.encode_batch(chunk)
                vectors.extend(chunk_vectors)

            # 카테고리 분류 및 MongoDB 업데이트
            await self._classify_and_update_categories(valid_data, vectors, collection)

            # GPT_recommend.md 증분 공식: 가중평균으로 프로필 벡터 계산
            profile_vector, total_weight = self._calculate_weighted_average(vectors, weights)

            # user_logs 컬렉션에 개별 로그 저장 (URL 해시 기반)
            await self._save_user_logs_to_qdrant(user_id, valid_data, vectors, weights)

            # user_profiles 컬렉션에 프로필 벡터 저장 (고유 Point ID 사용)
            await self._save_user_profile_to_qdrant(user_id, profile_vector, total_weight, len(vectors), weights, profile_point_id)

            logger.info(f"[완료] 사용자 {user_id} 프로필 생성 완료 - 총 가중치: {total_weight}")

            # 히스토리 처리 완료 후 브라우징 데이터 일괄 처리
            await self._process_all_browsing_data(user_id)

            return {
                "success": True,
                "message": "초기 사용자 프로필 생성 완료",
                "user_id": user_id,
                "processed_count": len(vectors),
                "total_weight": total_weight,
                "profile_vector_dim": len(profile_vector)
            }

        except Exception as e:
            logger.error(f"[에러] 프로필 생성 실패: {e}")
            return {"success": False, "message": f"프로필 생성 실패: {str(e)}"}

    def _calculate_weighted_average(self, vectors: List[List[float]], weights: List[float]) -> tuple:
        """가중평균으로 프로필 벡터 계산"""
        vectors_array = np.array(vectors)
        weights_array = np.array(weights)

        # 가중평균: (v1*w1 + v2*w2 + ...) / (w1 + w2 + ...)
        weighted_sum = np.sum(vectors_array * weights_array.reshape(-1, 1), axis=0)
        total_weight = np.sum(weights_array)

        profile_vector = weighted_sum / total_weight

        # L2 정규화
        profile_vector = profile_vector / np.linalg.norm(profile_vector)

        return profile_vector.tolist(), float(total_weight)

    async def _save_user_logs_to_qdrant(self, user_id: str, data_list: List[Dict], vectors: List[List[float]], weights: List[float]):
        """user_logs 컬렉션에 개별 로그 벡터 저장 (URL 해시 기반)"""
        try:
            collection_name = "user_logs"

            # 메타데이터 생성
            metadatas = []
            point_ids = []

            for i, (data, weight) in enumerate(zip(data_list, weights)):
                url = data.get('url', '')
                url_hash = get_url_hash(url)

                metadata = {
                    "user_id": user_id,
                    "url": url,
                    "url_hash": url_hash,
                    "weight": weight,  # 가중치는 메타데이터에 저장
                    "domain": data.get('domain', ''),
                    "title": data.get('content', {}).get('cleanTitle', ''),
                    "data_source": data.get('dataType', 'history'),
                    "visit_count": data.get('visitCount', 1),
                    "saved_at": data.get('savedAt')
                }

                # 히스토리 특화 필드 추가
                if data.get('dataType') == 'history':
                    metadata.update({
                        "typed_count": data.get('typedCount', 0),
                        "total_visits": data.get('totalVisits', 0),
                        "direct_visits": data.get('directVisits', 0),
                        "last_visit_time": data.get('lastVisitTime')
                    })

                metadatas.append(metadata)
                point_ids.append(str(uuid.uuid4()))  # UUID로 고유 ID 생성

            # Qdrant에 저장 (URL 해시 기반 Upsert)
            await self.qdrant_service.save_vectors_with_metadata_and_ids(
                collection_name, vectors, metadatas, point_ids
            )

            logger.info(f"[저장] user_logs 컬렉션에 {len(vectors)}개 벡터 저장 완료")

        except Exception as e:
            logger.error(f"[에러] user_logs 저장 실패: {e}")
            raise

    async def _save_user_profile_to_qdrant(self, user_id: str, profile_vector: List[float], total_weight: float, log_count: int, weights: List[float], profile_point_id: str):
        """user_profiles 컬렉션에 프로필 벡터 저장 (고유 Point ID 사용)"""
        try:
            collection_name = "user_profiles"

            # 통계 계산
            avg_weight = total_weight / log_count if log_count > 0 else 0.0
            max_weight = max(weights) if weights else 0.0
            min_weight = min(weights) if weights else 0.0

            metadata = {
                "user_id": user_id,
                "weight_sum": total_weight,  # GPT_recommend.md의 W_old
                "log_count": log_count,              # 반영된 로그 개수
                "avg_weight": round(avg_weight, 3),   # 평균 가중치
                "max_weight": max_weight,            # 최대 가중치
                "min_weight": min_weight,            # 최소 가중치
                "created_from": "history_data"
            }

            # 디버깅: 저장할 데이터 확인
            logger.info(f"[디버그] 프로필 저장 중: user_id={user_id}, point_id={profile_point_id}")
            logger.info(f"[디버그] profile_vector 타입: {type(profile_vector)}, None 여부: {profile_vector is None}")
            if profile_vector is not None:
                logger.info(f"[디버그] profile_vector 길이: {len(profile_vector)}, 처음 3개 값: {profile_vector[:3]}")
            logger.info(f"[디버그] total_weight: {total_weight} (타입: {type(total_weight)})")

            await self.qdrant_service.save_vectors_with_metadata_and_ids(
                collection_name, [profile_vector], [metadata], [profile_point_id]
            )

            logger.info(f"[저장] user_profiles 컬렉션에 {user_id} 프로필 저장 완료")

        except Exception as e:
            logger.error(f"[에러] user_profiles 저장 실패: {e}")
            raise

    async def get_user_profile_vector_cached(self, user_id: str) -> Optional[Dict]:
        """
        사용자 프로필 벡터 조회 (Redis 캐싱 포함)
        
        Args:
            user_id: 사용자 ID (이메일)
        
        Returns:
            프로필 정보 (vector, metadata) 또는 None
        """
        cache_key = f"user:profile:vector:{user_id}"
        
        # 1. Redis 캐시 확인
        try:
            cached = await redis_cache.get(cache_key)
            if cached:
                logger.info(f"[캐시 히트] 사용자 프로필 벡터: {user_id}")
                return cached
        except Exception as e:
            logger.warning(f"[캐시 조회 실패] {user_id}: {e}")
        
        # 2. 캐시 미스 - Qdrant에서 조회
        logger.info(f"[캐시 미스] Qdrant에서 프로필 벡터 조회: {user_id}")
        
        try:
            profile_point_id = self._get_deterministic_profile_id(user_id)
            existing_profile = await self.qdrant_service.get_point("user_profiles", profile_point_id)
            
            if existing_profile and existing_profile.get("vector"):
                result = {
                    "vector": existing_profile.get("vector"),
                    "metadata": {
                        "point_id": profile_point_id,
                        "weight_sum": existing_profile.get("payload", {}).get("weight_sum"),
                        "log_count": existing_profile.get("payload", {}).get("log_count"),
                        "created_from": existing_profile.get("payload", {}).get("created_from")
                    }
                }
                
                # 3. Redis에 캐시 저장 (TTL: 1시간)
                try:
                    await redis_cache.set(cache_key, result, ttl=3600)
                    logger.info(f"[캐시 저장] 사용자 프로필 벡터: {user_id}")
                except Exception as e:
                    logger.warning(f"[캐시 저장 실패] {user_id}: {e}")
                
                return result
            else:
                logger.info(f"[프로필 없음] 사용자 프로필이 존재하지 않음: {user_id}")
                return None
                
        except Exception as e:
            logger.error(f"[프로필 조회 실패] {user_id}: {e}")
            return None

    async def invalidate_user_profile_cache(self, user_id: str):
        """
        사용자 프로필 캐시 무효화
        프로필이 업데이트될 때 호출
        """
        cache_key = f"user:profile:vector:{user_id}"
        try:
            await redis_cache.delete(cache_key)
            logger.info(f"[캐시 무효화] 사용자 프로필: {user_id}")
        except Exception as e:
            logger.warning(f"[캐시 무효화 실패] {user_id}: {e}")

    async def update_profile_with_new_log(self, user_id: str, new_data: Dict) -> Dict:
        """새로운 브라우징 로그로 프로필 증분 업데이트 (GPT_recommend.md 공식)"""
        # 사용자별 Lock 생성 및 적용
        if user_id not in self.user_locks:
            self.user_locks[user_id] = asyncio.Lock()

        async with self.user_locks[user_id]:
            logger.info(f"[프로필 업데이트] 사용자 {user_id} 증분 업데이트 시작")

            try:
                # 새 로그 벡터화
                combined_text = self._prepare_text_for_embedding(new_data)
                if not combined_text.strip():
                    return {"success": False, "message": "임베딩 가능한 텍스트가 없습니다."}

                v_new = await embedding_service.encode(combined_text)
                w_new = self._calculate_weight(new_data)

                # 기존 프로필 벡터 가져오기 (고유 Point ID 사용)
                profile_point_id = self._get_deterministic_profile_id(user_id)
                old_profile = await self.qdrant_service.get_point("user_profiles", profile_point_id)

                if not old_profile:
                    # 프로필이 없으면 히스토리 처리 완료를 기다림 (히스토리 재처리 방지)
                    logger.warning(f"[건너뛰기] 사용자 {user_id} 프로필이 없습니다. 히스토리 처리 완료를 기다리세요.")
                    return {
                        "success": False,
                        "message": "프로필이 없습니다. 히스토리 처리 완료를 기다리세요.",
                        "skipped": True
                    }

                V_old = old_profile.get("vector")
                W_old = old_profile.get("payload", {}).get("weight_sum")

                # 디버깅: None 값 원인 분석
                logger.info(f"[디버그] old_profile 구조: id={old_profile.get('id')}, vector는 None: {V_old is None}, payload keys: {list(old_profile.get('payload', {}).keys())}")
                logger.info(f"[디버그] weight_sum 값: {W_old} (타입: {type(W_old)})")

                if V_old is None:
                    logger.error(f"[에러] V_old가 None입니다. 프로필 저장 시 벡터가 제대로 저장되지 않았을 가능성")
                if W_old is None:
                    logger.error(f"[에러] W_old가 None입니다. 프로필 저장 시 weight_sum이 제대로 저장되지 않았을 가능성")

                # GPT_recommend.md 증분 공식: V_new = (V_old * W_old + v_new * w_new) / (W_old + w_new)
                V_old_array = np.array(V_old)
                v_new_array = np.array(v_new)

                V_new = (V_old_array * W_old + v_new_array * w_new) / (W_old + w_new)
                V_new = V_new / np.linalg.norm(V_new)  # L2 정규화

                # user_logs에 새 로그 저장 (UUID 기반)
                url = new_data.get('url', '')
                url_hash = get_url_hash(url)
                point_id = str(uuid.uuid4())  # UUID로 고유 ID 생성

                metadata = {
                    "user_id": user_id,
                    "url": url,
                    "url_hash": url_hash,
                    "weight": w_new,
                    "domain": new_data.get('domain', ''),
                    "title": new_data.get('content', {}).get('cleanTitle', ''),
                    "data_source": new_data.get('dataType', 'browsing'),
                    "visit_count": new_data.get('visitCount', 1),
                    "saved_at": new_data.get('savedAt')
                }

                await self.qdrant_service.save_vectors_with_metadata_and_ids(
                    "user_logs", [v_new], [metadata], [point_id]
                )

                # 기존 통계 정보 가져오기
                old_payload = old_profile.get("payload", {})
                old_log_count = old_payload.get("log_count", 0)
                old_max_weight = old_payload.get("max_weight", 0.0)
                old_min_weight = old_payload.get("min_weight", 0.0)

                # 새로운 통계 계산
                new_log_count = old_log_count + 1
                new_weight_sum = W_old + w_new
                new_avg_weight = new_weight_sum / new_log_count
                new_max_weight = max(old_max_weight, w_new)
                new_min_weight = min(old_min_weight, w_new) if old_min_weight > 0 else w_new

                # user_profiles 업데이트
                updated_metadata = {
                    "user_id": user_id,
                    "weight_sum": new_weight_sum,  # GPT_recommend.md의 W_old + w_new
                    "log_count": new_log_count,
                    "avg_weight": round(new_avg_weight, 3),
                    "max_weight": new_max_weight,
                    "min_weight": new_min_weight,
                    "created_from": old_payload.get("created_from", "history_data"),
                    "last_update": new_data.get('savedAt')
                }

                # 고유 Point ID를 사용해서 업데이트 (덮어쓰기)
                await self.qdrant_service.save_vectors_with_metadata_and_ids(
                    "user_profiles", [V_new.tolist()], [updated_metadata], [profile_point_id]
                )

                # Qdrant 저장 완료 후 카테고리 분류 수행
                try:
                    from ..core.database import get_database, get_collection_name
                    collection_name = get_collection_name(user_id, "browsing")
                    collection = get_database()[collection_name]
                    await self._classify_and_update_categories([new_data], [v_new], collection)
                    logger.info("[완료] 실시간 브라우징 데이터 카테고리 분류 완료")
                except Exception as e:
                    logger.warning(f"[경고] 카테고리 분류 실패: {e}")

                logger.info(f"[완료] 프로필 증분 업데이트 완료 - 새 가중치: {W_old + w_new}")

                # 무효화 추가
                await self.invalidate_user_profile_cache(user_id)

                return {
                    "success": True,
                    "message": "프로필 증분 업데이트 완료",
                    "user_id": user_id,
                    "old_weight": W_old,
                    "new_weight": w_new,
                    "total_weight": W_old + w_new
                }

            except Exception as e:
                logger.error(f"[에러] 프로필 업데이트 실패: {e}")
                return {"success": False, "message": f"프로필 업데이트 실패: {str(e)}"}


    async def _process_all_browsing_data(self, user_id: str):
        """히스토리 처리 완료 후 모든 브라우징 데이터 일괄 처리"""
        try:
            logger.info(f"🔍 [후처리] 사용자 {user_id} 히스토리 처리 완료 후 브라우징 데이터 일괄 처리 시작")
            print(f"🔍 [후처리] 사용자 {user_id} 히스토리 처리 완료 후 브라우징 데이터 일괄 처리 시작")

            # 해당 사용자의 모든 브라우징 데이터 조회
            database = get_database()
            collection_name = get_collection_name(user_id, 'browsing')
            collection = database[collection_name]

            # 모든 브라우징 데이터 조회 (히스토리 수집 중 쌓인 데이터)
            browsing_data_cursor = collection.find({
                "userId": user_id
            }).sort("savedAt", 1)  # 시간순 정렬

            browsing_data = await browsing_data_cursor.to_list(length=None)

            if not browsing_data:
                logger.info(f"✅ [완료] 처리할 브라우징 데이터가 없습니다.")
                print(f"✅ [완룜] 처리할 브라우징 데이터가 없습니다.")
                return

            logger.info(f"📦 [발견] 처리할 브라우징 데이터 {len(browsing_data)}개 발견, 일괄 증분 처리 시작")
            print(f"📦 [발견] 처리할 브라우징 데이터 {len(browsing_data)}개 발견, 일괄 증분 처리 시작")

            # 모든 브라우징 데이터를 하나씩 증분 업데이트
            success_count = 0
            for data in browsing_data:
                try:
                    result = await self.update_profile_with_new_log(user_id, data)
                    if result.get("success"):
                        success_count += 1
                except Exception as e:
                    logger.warning(f"[경고] 브라우징 데이터 처리 실패: {e}")
                    continue

            logger.info(f"🎯 [완료] 브라우징 데이터 {success_count}/{len(browsing_data)}개 처리 완료")
            print(f"🎯 [완료] 브라우징 데이터 {success_count}/{len(browsing_data)}개 처리 완료")

        except Exception as e:
            logger.error(f"❌ [에러] 브라우징 데이터 후처리 실패: {e}")
            print(f"❌ [에러] 브라우징 데이터 후처리 실패: {e}")
