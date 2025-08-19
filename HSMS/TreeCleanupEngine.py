import asyncio
import time
import re
from collections import defaultdict
from .AIManager import AIManager
from .MemoryNode import MemoryNode


class TreeCleanupEngine:
    """트리 정리 엔진 - 클러스터링 기반 자동 트리 최적화"""
    
    def __init__(self, memory_manager, max_depth=4, fanout_limit=12, debug=False):
        self.memory_manager = memory_manager
        self.ai_manager = AIManager(debug=debug)
        self.max_depth = max_depth
        self.fanout_limit = fanout_limit
        self.debug = debug
        self.cleanup_stats = {
            'moves': 0,
            'merges': 0,
            'new_groups': 0,
            'renames': 0,
            'start_time': 0,
            'end_time': 0
        }
    
    def __del__(self):
        """Cleanup when object is destroyed"""
        try:
            if hasattr(self, 'ai_manager'):
                del self.ai_manager
        except:
            pass
    
    async def run_cleanup(self, rename_nodes=False, dry_run=False):
        """전체 트리 정리 프로세스를 실행합니다."""
        self.cleanup_stats['start_time'] = time.time()
        
        if self.debug:
            print(f"\n=== 트리 정리 엔진 시작 ===")
            print(f">> 설정: max_depth={self.max_depth}, fanout_limit={self.fanout_limit}")
            print(f">> 모드: {'드라이런' if dry_run else '실제 적용'}, 이름변경={'활성' if rename_nodes else '비활성'}")
        
        # 0. 정리 전 스냅샷
        pre_stats = self._generate_tree_stats()
        if self.debug:
            print(f">> 정리 전: 노드 {pre_stats['total_nodes']}개, 평균 fanout {pre_stats['avg_fanout']:.1f}, 최대 깊이 {pre_stats['max_depth']}")
        
        if dry_run:
            print(f"\n=== 드라이런 모드: 변경 계획만 출력 ===")
            await self._dry_run_analysis()
            return self.cleanup_stats
        
        # 1. 자식 과다 군집화
        await self._cluster_excessive_fanouts()
        
        # 2. 교차 부모 중복/유사 처리
        await self._resolve_cross_parent_duplicates()
        
        # 3. 리프 병합
        await self._merge_similar_leaves()
        
        # 4. 이름 정리 (옵션)
        if rename_nodes:
            await self._rename_nodes()
        
        # 5. 정리 후 통계 및 저장
        self.memory_manager.save_tree()
        self.cleanup_stats['end_time'] = time.time()
        
        post_stats = self._generate_tree_stats()
        if self.debug:
            print(f"\n=== 정리 완료 ===")
            print(f">> 정리 후: 노드 {post_stats['total_nodes']}개, 평균 fanout {post_stats['avg_fanout']:.1f}, 최대 깊이 {post_stats['max_depth']}")
            print(f">> 변경사항: 이동 {self.cleanup_stats['moves']}개, 병합 {self.cleanup_stats['merges']}개, 그룹 {self.cleanup_stats['new_groups']}개, 이름변경 {self.cleanup_stats['renames']}개")
            print(f">> 소요시간: {self.cleanup_stats['end_time'] - self.cleanup_stats['start_time']:.1f}초")
        
        return self.cleanup_stats
    
    async def _dry_run_analysis(self):
        """드라이런 모드에서 변경 계획을 분석하고 출력합니다."""
        print(f"\n--- 1. 자식 과다 분석 ---")
        excessive_nodes = self._find_excessive_fanout_nodes()
        for node_id, child_count in excessive_nodes:
            node = self.memory_manager.get_node(node_id)
            print(f"- '{node.topic}': {child_count}개 자식 (한도: {self.fanout_limit}) -> 군집화 예정")
        
        print(f"\n--- 2. 중복 노드 분석 ---")
        duplicates = await self._find_duplicate_topics()
        for topic, node_ids in duplicates.items():
            if len(node_ids) > 1:
                print(f"- 중복 주제 '{topic}': {len(node_ids)}개 노드 -> 병합 예정")
        
        print(f"\n--- 3. 유사 리프 분석 ---")
        similar_groups = await self._find_similar_leaf_groups()
        for group in similar_groups:
            if len(group) > 1:
                topics = [self.memory_manager.get_node(nid).topic for nid in group]
                print(f"- 유사 리프 그룹: {topics} -> 병합 예정")
        
        print(f"\n=== 예상 결과 ===")
        print(f"- 생성될 그룹: {len(excessive_nodes)}개")
        print(f"- 병합될 노드: {sum(len(ids)-1 for ids in duplicates.values())}개")
        print(f"- 정리될 리프: {sum(len(group)-1 for group in similar_groups)}개")
    
    async def _cluster_excessive_fanouts(self):
        """자식 수가 fanout_limit를 초과하는 노드들을 군집화합니다."""
        if self.debug:
            print(f"\n--- 1단계: 자식 과다 군집화 ---")
        
        excessive_nodes = self._find_excessive_fanout_nodes()
        
        for node_id, child_count in excessive_nodes:
            node = self.memory_manager.get_node(node_id)
            
            if self.debug:
                print(f">> 처리 중: '{node.topic}' ({child_count}개 자식)")
            
            # 깊이 확인
            current_depth = self.memory_manager.get_node_depth(node_id)
            if current_depth + 1 >= self.max_depth:
                if self.debug:
                    print(f">>>> 건너뛰기: 깊이 한계 도달 ({current_depth + 1} >= {self.max_depth})")
                continue
            
            # 자식 노드들 클러스터링
            children = [self.memory_manager.get_node(cid) for cid in node.children_ids 
                       if self.memory_manager.get_node(cid)]
            
            clusters = await self._cluster_nodes_by_similarity(children)
            
            # 각 클러스터를 그룹으로 변환
            for i, cluster in enumerate(clusters):
                if len(cluster) >= 2:  # 2개 이상인 클러스터만 그룹화
                    await self._create_cluster_group(node_id, cluster, f"그룹{i+1}")
                    self.cleanup_stats['new_groups'] += 1
    
    async def _cluster_nodes_by_similarity(self, nodes):
        """노드들을 유사도 기반으로 클러스터링합니다."""
        if len(nodes) <= 2:
            return [nodes]  # 2개 이하면 클러스터링 불필요
        
        if self.debug:
            print(f">>>> 클러스터링 시작: {len(nodes)}개 노드")
        
        # 노드 간 유사도 매트릭스 생성
        similarity_matrix = await self._build_similarity_matrix(nodes)
        
        # 간단한 연결 요소 기반 클러스터링
        clusters = self._connected_components_clustering(nodes, similarity_matrix)
        
        if self.debug:
            print(f">>>> 클러스터링 완료: {len(clusters)}개 클러스터")
            for i, cluster in enumerate(clusters):
                topics = [node.topic for node in cluster]
                print(f">>>>   클러스터 {i+1}: {topics}")
        
        return clusters
    
    async def _build_similarity_matrix(self, nodes):
        """노드 간 유사도 매트릭스를 구축합니다."""
        n = len(nodes)
        matrix = [[False for _ in range(n)] for _ in range(n)]
        
        # 모든 노드 쌍에 대해 유사도 검사
        queries = []
        pairs = []
        
        for i in range(n):
            for j in range(i+1, n):
                query = f"""노드1: {nodes[i].topic}
요약1: {nodes[i].summary[:100]}
노드2: {nodes[j].topic}  
요약2: {nodes[j].summary[:100]}

이 두 노드가 같은 그룹으로 묶일 만큼 유사한가요?"""
                queries.append(query)
                pairs.append((i, j))
        
        if queries:
            system_prompt = """두 노드가 같은 상위 그룹으로 묶일 만큼 유사한지 판단하세요.
유사하면 "True", 다르면 "False"로만 답하세요."""
            
            results = await self.ai_manager.call_ai_async_multiple(queries, system_prompt)
            
            # 결과를 매트릭스에 반영
            for idx, result in enumerate(results):
                if result and result.strip().lower() == 'true':
                    i, j = pairs[idx]
                    matrix[i][j] = matrix[j][i] = True
        
        return matrix
    
    def _connected_components_clustering(self, nodes, similarity_matrix):
        """연결 요소 알고리즘으로 클러스터링을 수행합니다."""
        n = len(nodes)
        visited = [False] * n
        clusters = []
        
        def dfs(node_idx, current_cluster):
            visited[node_idx] = True
            current_cluster.append(nodes[node_idx])
            
            for j in range(n):
                if not visited[j] and similarity_matrix[node_idx][j]:
                    dfs(j, current_cluster)
        
        for i in range(n):
            if not visited[i]:
                cluster = []
                dfs(i, cluster)
                clusters.append(cluster)
        
        return clusters
    
    async def _create_cluster_group(self, parent_id, cluster_nodes, group_name):
        """클러스터를 위한 그룹 노드를 생성하고 자식들을 재배치합니다."""
        # 그룹명과 요약을 병렬로 AI 생성
        topics = [node.topic for node in cluster_nodes]
        topic_task = self._generate_group_name(topics)
        summary_task = self._generate_group_summary(cluster_nodes)
        group_topic, group_summary = await asyncio.gather(topic_task, summary_task)
        
        # 그룹 노드 생성
        group_node = MemoryNode(
            topic=group_topic,
            summary=group_summary,
            parent_id=parent_id,
            coordinates={"start": -1, "end": -1}  # 그룹 표시
        )
        
        self.memory_manager.add_node(group_node, parent_id)
        
        # 클러스터 노드들을 그룹 하위로 이동
        parent_node = self.memory_manager.get_node(parent_id)
        for node in cluster_nodes:
            # 기존 부모에서 제거
            if node.node_id in parent_node.children_ids:
                parent_node.children_ids.remove(node.node_id)
            
            # 새 그룹 하위로 이동
            node.parent_id = group_node.node_id
            group_node.children_ids.append(node.node_id)
            self.cleanup_stats['moves'] += 1
        
        self.memory_manager.save_tree()
        
        if self.debug:
            print(f">>>> 그룹 생성: '{group_topic}' ({len(cluster_nodes)}개 노드)")
    
    async def _generate_group_name(self, topics):
        """주제들을 기반으로 그룹명을 생성합니다."""
        system_prompt = """주어진 주제들을 포괄하는 적절한 그룹명을 생성하세요.
IMPORTANT: 오직 그룹명만 답변하세요. 설명이나 다른 텍스트는 포함하지 마세요.
- 2-8자의 간결한 한국어 단어
- 예: "과학", "음식", "언어", "경제", "철학"
- 주제들의 공통점을 반영한 핵심 단어"""
        
        topics_text = ", ".join(topics[:3])  # 최대 3개만 사용
        
        try:
            result = await self.ai_manager.call_ai_async_single(
                f"주제들: {topics_text}", system_prompt
            )
            # AI 응답에서 실제 그룹명만 추출
            group_name = self._extract_group_name(result.strip())
            return group_name
        except Exception as e:
            if self.debug:
                print(f">>>> [ERROR] 그룹명 생성 오류: {e}")
            return f"그룹{len(topics)}"
    
    def _extract_group_name(self, ai_response):
        """AI 응답에서 실제 그룹명만 추출합니다."""
        
        # 먼저 따옴표나 별표 안의 내용을 찾기
        quoted_matches = re.findall(r'["""\'\'*]{1,2}([^"""\'\'*]{2,8})["""\'\'*]{1,2}', ai_response)
        if quoted_matches:
            candidate = quoted_matches[0].strip()
            if 2 <= len(candidate) <= 8 and re.match(r'^[가-힣a-zA-Z\s]+$', candidate):
                return candidate
        
        # 줄바꿈이나 구두점으로 분리
        lines = ai_response.split('\n')
        first_line = lines[0].strip()
        
        # 숫자와 점으로 시작하는 경우 제거
        first_line = re.sub(r'^\d+\.\s*', '', first_line)
        
        # 특수문자나 숫자 제거
        clean_name = re.sub(r'[^가-힣a-zA-Z\s]', '', first_line)
        clean_name = clean_name.strip()
        
        # 단어별로 분리해서 적절한 길이 찾기
        words = clean_name.split()
        if words:
            # 첫 번째 단어가 적절한 길이면 사용
            if 2 <= len(words[0]) <= 8:
                return words[0]
            # 첫 두 단어 결합이 적절하면 사용
            elif len(words) > 1:
                combined = words[0] + words[1]
                if 2 <= len(combined) <= 8:
                    return combined
        
        # 길이 제한
        if len(clean_name) > 8:
            clean_name = clean_name[:8]
        elif len(clean_name) < 2:
            clean_name = "그룹"
            
        return clean_name
    
    def _extract_clean_name(self, ai_response):
        """AI 응답에서 깨끗한 이름만 추출합니다."""
        
        # 먼저 따옴표나 별표 안의 내용을 찾기
        quoted_matches = re.findall(r'["""\'\'*]{1,2}([^"""\'\'*]{2,15})["""\'\'*]{1,2}', ai_response)
        if quoted_matches:
            candidate = quoted_matches[0].strip()
            if 2 <= len(candidate) <= 15 and re.match(r'^[가-힣a-zA-Z\s]+$', candidate):
                return candidate
        
        # 줄바꿈이나 구두점으로 분리
        lines = ai_response.split('\n')
        first_line = lines[0].strip()
        
        # 숫자와 점으로 시작하는 경우 제거
        first_line = re.sub(r'^\d+\.\s*', '', first_line)
        
        # 설명적인 문구 제거
        first_line = re.sub(r'.*이름.*[\'"""]([^\'"""]+)[\'"""].*', r'\1', first_line)
        first_line = re.sub(r'.*제안.*[\'"""]([^\'"""]+)[\'"""].*', r'\1', first_line)
        first_line = re.sub(r'.*명칭.*[\'"""]([^\'"""]+)[\'"""].*', r'\1', first_line)
        
        # 특수문자나 숫자 제거
        clean_name = re.sub(r'[^가-힣a-zA-Z\s]', '', first_line)
        clean_name = clean_name.strip()
        
        # 단어별로 분리해서 적절한 길이 찾기
        words = clean_name.split()
        if words:
            # 첫 번째 단어가 적절한 길이면 사용
            if 2 <= len(words[0]) <= 15:
                return words[0]
            # 첫 두 단어 결합이 적절하면 사용
            elif len(words) > 1:
                combined = words[0] + ' ' + words[1]
                if 2 <= len(combined) <= 15:
                    return combined.replace(' ', '')
        
        # 길이 제한
        if len(clean_name) > 15:
            clean_name = clean_name[:15]
        elif len(clean_name) < 2:
            clean_name = "주제"
            
        return clean_name
    
    async def _generate_group_summary(self, nodes):
        """그룹 노드의 요약을 생성합니다."""
        system_prompt = """주어진 노드들의 공통 주제와 내용을 요약하세요.
- 1-2문장으로 간결하게
- 하위 노드들의 공통점 강조"""
        
        nodes_text = "\n".join([f"- {node.topic}: {node.summary[:50]}" for node in nodes])
        
        try:
            result = await self.ai_manager.call_ai_async_single(nodes_text, system_prompt)
            return result.strip()
        except Exception as e:
            if self.debug:
                print(f">>>> [ERROR] 그룹 요약 생성 오류: {e}")
            return f"{len(nodes)}개의 관련 주제들을 포함하는 그룹입니다."
    
    def _find_excessive_fanout_nodes(self):
        """fanout_limit를 초과하는 노드들을 찾습니다."""
        excessive = []
        
        for node_id, node in self.memory_manager.memory_tree.items():
            if len(node.children_ids) > self.fanout_limit:
                # 카테고리 노드만 대상 (coordinates.start == -1)
                if node.coordinates.get("start") == -1:
                    excessive.append((node_id, len(node.children_ids)))
        
        return excessive
    
    async def _resolve_cross_parent_duplicates(self):
        """교차 부모간 중복/유사 노드를 해결합니다."""
        if self.debug:
            print(f"\n--- 2단계: 교차 부모 중복 해결 ---")
        
        # 동일 topic 노드들 찾기
        duplicates = await self._find_duplicate_topics()
        
        for topic, node_ids in duplicates.items():
            if len(node_ids) > 1:
                await self._merge_duplicate_nodes(node_ids, topic)
    
    async def _find_duplicate_topics(self):
        """동일한 topic을 가진 노드들을 찾습니다."""
        topic_groups = defaultdict(list)
        
        for node_id, node in self.memory_manager.memory_tree.items():
            if node.topic != "ROOT":  # 루트 제외
                topic_groups[node.topic].append(node_id)
        
        # 2개 이상인 그룹만 반환
        return {topic: node_ids for topic, node_ids in topic_groups.items() if len(node_ids) > 1}
    
    async def _merge_duplicate_nodes(self, node_ids, topic):
        """중복된 노드들을 병합합니다."""
        if self.debug:
            print(f">> 중복 병합: '{topic}' ({len(node_ids)}개 노드)")
        
        # 대표 노드 선정 (가장 오래된 것 또는 자식이 많은 것)
        representative = self._select_representative_node(node_ids)
        
        # 나머지 노드들을 대표 노드에 병합
        for node_id in node_ids:
            if node_id != representative.node_id:
                await self._merge_node_to_representative(node_id, representative)
                self.cleanup_stats['merges'] += 1
    
    def _select_representative_node(self, node_ids):
        """대표 노드를 선정합니다."""
        nodes = [self.memory_manager.get_node(nid) for nid in node_ids]
        
        # 자식 수가 가장 많은 노드 선택
        representative = max(nodes, key=lambda n: len(n.children_ids))
        
        return representative
    
    async def _merge_node_to_representative(self, source_node_id, target_node):
        """소스 노드를 타겟 노드에 병합합니다."""
        source_node = self.memory_manager.get_node(source_node_id)
        
        # 대화 인덱스 병합
        if hasattr(source_node, 'conversation_indices') and hasattr(target_node, 'conversation_indices'):
            target_node.conversation_indices.extend(source_node.conversation_indices)
        
        # 자식 노드들을 타겟으로 이동
        for child_id in source_node.children_ids:
            child_node = self.memory_manager.get_node(child_id)
            if child_node:
                child_node.parent_id = target_node.node_id
                target_node.children_ids.append(child_id)
        
        # 요약 업데이트
        merged_summary = await self._generate_merged_summary(target_node, source_node)
        target_node.summary = merged_summary
        
        # 소스 노드 제거
        self._remove_node(source_node_id)
        
        if self.debug:
            print(f">>>> 병합 완료: '{source_node.topic}' -> '{target_node.topic}'")
    
    async def _generate_merged_summary(self, target_node, source_node):
        """병합된 노드의 요약을 생성합니다."""
        system_prompt = """두 노드가 병합되었습니다. 통합된 요약을 작성하세요.
- 두 노드의 핵심 내용 모두 포함
- 1-2문장으로 간결하게"""
        
        merge_text = f"""타겟 노드: {target_node.topic}
타겟 요약: {target_node.summary}
소스 노드: {source_node.topic}
소스 요약: {source_node.summary}"""
        
        try:
            result = await self.ai_manager.call_ai_async_single(merge_text, system_prompt)
            return result.strip()
        except Exception as e:
            if self.debug:
                print(f">>>> [ERROR] 병합 요약 생성 오류: {e}")
            return f"{target_node.summary} {source_node.summary}"
    
    def _remove_node(self, node_id):
        """노드를 트리에서 제거합니다."""
        node = self.memory_manager.get_node(node_id)
        if not node:
            return
        
        # 부모에서 자식 목록 제거
        if node.parent_id:
            parent = self.memory_manager.get_node(node.parent_id)
            if parent and node_id in parent.children_ids:
                parent.children_ids.remove(node_id)
        
        # 메모리 트리에서 제거
        if node_id in self.memory_manager.memory_tree:
            del self.memory_manager.memory_tree[node_id]
    
    async def _merge_similar_leaves(self):
        """유사한 리프 노드들을 병합합니다."""
        if self.debug:
            print(f"\n--- 3단계: 유사 리프 병합 ---")
        
        similar_groups = await self._find_similar_leaf_groups()
        
        for group in similar_groups:
            if len(group) > 1:
                await self._merge_leaf_group(group)
    
    async def _find_similar_leaf_groups(self):
        """유사한 리프 노드 그룹들을 찾습니다."""
        # 모든 리프 노드 수집
        leaf_nodes = []
        for node_id, node in self.memory_manager.memory_tree.items():
            if not node.children_ids and node.coordinates.get("start") != -1:  # 리프이면서 대화 노드
                leaf_nodes.append(node)
        
        if len(leaf_nodes) <= 1:
            return []
        
        # 같은 부모를 가진 리프들끼리만 비교
        parent_groups = defaultdict(list)
        for node in leaf_nodes:
            parent_groups[node.parent_id].append(node)
        
        similar_groups = []
        for parent_id, nodes in parent_groups.items():
            if len(nodes) > 1:
                # 유사도 기반 그룹핑
                similarity_matrix = await self._build_similarity_matrix(nodes)
                clusters = self._connected_components_clustering(nodes, similarity_matrix)
                
                # 2개 이상인 클러스터만 추가
                for cluster in clusters:
                    if len(cluster) > 1:
                        similar_groups.append([node.node_id for node in cluster])
        
        return similar_groups
    
    async def _merge_leaf_group(self, leaf_node_ids):
        """유사한 리프 노드 그룹을 병합합니다."""
        if len(leaf_node_ids) <= 1:
            return
        
        # 대표 노드 선정
        representative_id = leaf_node_ids[0]  # 첫 번째를 대표로
        representative = self.memory_manager.get_node(representative_id)
        
        # 나머지 노드들 병합
        for node_id in leaf_node_ids[1:]:
            source_node = self.memory_manager.get_node(node_id)
            if source_node:
                # 대화 인덱스 병합
                if hasattr(representative, 'conversation_indices') and hasattr(source_node, 'conversation_indices'):
                    representative.conversation_indices.extend(source_node.conversation_indices)
                
                # 소스 노드 제거
                self._remove_node(node_id)
                self.cleanup_stats['merges'] += 1
        
        # 대표 노드 요약 업데이트
        updated_summary = await self._generate_leaf_merge_summary(representative)
        representative.summary = updated_summary
        
        if self.debug:
            topics = [self.memory_manager.get_node(nid).topic for nid in leaf_node_ids if self.memory_manager.get_node(nid)]
            print(f">>>> 리프 병합: {topics} -> '{representative.topic}'")
    
    async def _generate_leaf_merge_summary(self, merged_node):
        """병합된 리프 노드의 요약을 생성합니다."""
        system_prompt = """여러 대화가 병합된 노드의 요약을 작성하세요.
- 모든 대화의 핵심 내용 포함
- "여러 대화가 포함됨"을 명시"""
        
        conv_count = len(merged_node.conversation_indices) if hasattr(merged_node, 'conversation_indices') else 1
        
        try:
            result = await self.ai_manager.call_ai_async_single(
                f"노드: {merged_node.topic}\n기존 요약: {merged_node.summary}\n대화 수: {conv_count}",
                system_prompt
            )
            return result.strip()
        except Exception as e:
            if self.debug:
                print(f">>>> [ERROR] 리프 병합 요약 생성 오류: {e}")
            return f"{merged_node.summary} (병합된 {conv_count}개 대화)"
    
    async def _rename_nodes(self):
        """노드들의 이름을 정리합니다."""
        if self.debug:
            print(f"\n--- 4단계: 노드 이름 정리 ---")
        
        # 모든 카테고리 노드 대상
        category_nodes = [
            node for node in self.memory_manager.memory_tree.values()
            if node.coordinates.get("start") == -1 and node.topic != "ROOT"
        ]
        
        for node in category_nodes:
            new_name = await self._generate_improved_name(node)
            if new_name != node.topic:
                old_name = node.topic
                node.topic = new_name
                self.cleanup_stats['renames'] += 1
                
                if self.debug:
                    print(f">>>> 이름 변경: '{old_name}' -> '{new_name}'")
    
    async def _generate_improved_name(self, node):
        """개선된 노드 이름을 생성합니다."""
        system_prompt = """노드의 요약과 하위 내용을 바탕으로 더 적절한 이름을 제안하세요.
- 2-8자의 간결한 한국어
- 현재 이름보다 더 명확하고 포괄적인 표현

IMPORTANT: 오직 그룹명만 답변하세요. 설명이나 추가 텍스트 없이 그룹명만 출력하세요."""
        
        # 하위 노드들의 주제도 참고
        child_topics = []
        for child_id in node.children_ids:
            child = self.memory_manager.get_node(child_id)
            if child:
                child_topics.append(child.topic)
        
        context = f"""현재 이름: {node.topic}
요약: {node.summary}
하위 주제들: {', '.join(child_topics[:5])}"""
        
        try:
            result = await self.ai_manager.call_ai_async_single(context, system_prompt)
            clean_name = self._extract_clean_name(result)
            
            # 기존 이름과 크게 다르지 않으면 변경하지 않음
            if len(clean_name) < 2 or clean_name == node.topic:
                return node.topic
            
            return clean_name
        except Exception as e:
            if self.debug:
                print(f">>>> [ERROR] 이름 개선 오류: {e}")
            return node.topic
    
    def _generate_tree_stats(self):
        """트리 통계를 생성합니다."""
        total_nodes = len(self.memory_manager.memory_tree)
        
        fanouts = []
        max_depth = 0
        
        for node in self.memory_manager.memory_tree.values():
            fanouts.append(len(node.children_ids))
            node_depth = self.memory_manager.get_node_depth(node.node_id)
            max_depth = max(max_depth, node_depth)
        
        avg_fanout = sum(fanouts) / len(fanouts) if fanouts else 0
        
        return {
            'total_nodes': total_nodes,
            'avg_fanout': avg_fanout,
            'max_depth': max_depth,
            'fanouts': fanouts
        }
