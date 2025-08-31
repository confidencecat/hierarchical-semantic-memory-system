import asyncio
from config import get_config_value


class KDistanceSearch:
    """K-거리 기반 효율적인 유사도 검색 엔진"""

    def __init__(self, memory_manager, ai_manager, debug=False):
        self.memory_manager = memory_manager
        self.ai_manager = ai_manager
        self.debug = debug
        self.k = get_config_value('k_distance')
        # 중복 비교 방지를 위한 2D 캐시: {(node_id1, node_id2): similarity_score}
        self.similarity_cache = {}

    def set_k(self, k):
        """K 값을 동적으로 설정"""
        self.k = k

    async def find_similar_nodes(self, target_node, k=None):
        """K-거리 이내 노드와의 유사도를 계산하여 가장 유사한 노드들을 반환"""
        if k is None:
            k = self.k

        if self.debug:
            print(f"K-거리 검색 시작: 대상 노드 '{target_node.topic}', k={k}")

        # 1. K-거리 이내 노드 수집
        nearby_nodes = self.memory_manager.get_nodes_within_k_distance(target_node.node_id, k)

        if self.debug:
            print(f"K-거리 이내 노드 수: {len(nearby_nodes)}개")

        # 2. 유사도 계산 (캐시 활용)
        similarities = []
        for node in nearby_nodes:
            if node.node_id == target_node.node_id:
                continue  # 자기 자신 제외

            cache_key = tuple(sorted([target_node.node_id, node.node_id]))
            if cache_key not in self.similarity_cache:
                similarity = await self.calculate_similarity(target_node, node)
                self.similarity_cache[cache_key] = similarity
            similarities.append((node, self.similarity_cache[cache_key]))

        # 3. 유사도 순으로 정렬
        similarities.sort(key=lambda x: x[1], reverse=True)

        if self.debug:
            print(f"유사도 계산 완료: {len(similarities)}개 노드")

        return similarities

    async def calculate_similarity(self, node1, node2):
        """두 노드 간의 유사도를 AI로 계산"""
        try:
            prompt = f"""두 노드의 유사도를 0-1 사이의 실수로 평가하라.

노드 1:
주제: {node1.topic}
요약: {node1.summary}

노드 2:
주제: {node2.topic}
요약: {node2.summary}

유사도 기준:
- 주제와 내용이 매우 유사: 0.9-1.0
- 주제는 같지만 내용이 다름: 0.7-0.8
- 주제가 관련있음: 0.5-0.6
- 약간 관련: 0.3-0.4
- 무관: 0.0-0.2

숫자만 출력하라."""

            system_prompt = "두 노드의 유사도를 평가하는 AI입니다."
            result = await self.ai_manager.call_ai_async_single(prompt, system_prompt)

            # 숫자 추출
            import re
            match = re.search(r'(\d+\.?\d*)', result.strip())
            if match:
                similarity = float(match.group(1))
                return max(0.0, min(1.0, similarity))  # 0-1 범위 제한
            else:
                return 0.5  # 기본값

        except Exception as e:
            if self.debug:
                print(f"유사도 계산 오류: {e}")
            return 0.5  # 오류 시 중간값 반환

    def clear_cache(self):
        """유사도 캐시 초기화"""
        self.similarity_cache.clear()
        if self.debug:
            print("유사도 캐시 초기화됨")

    def get_cache_size(self):
        """캐시 크기 반환"""
        return len(self.similarity_cache)
