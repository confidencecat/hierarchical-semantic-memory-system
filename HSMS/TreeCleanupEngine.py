import asyncio
import time
import re
from collections import defaultdict
from .AIManager import AIManager
from .MemoryNode import MemoryNode
from config import NODE_SIMILARITY_FINE


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
            'removed_nodes': 0,
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
            print("트리 정리 시작")

        pre_stats = self._generate_tree_stats()
        if self.debug:
            print(f">> 정리 전: 노드 {pre_stats['total_nodes']}개, 평균 fanout {pre_stats['avg_fanout']:.1f}, 최대 깊이 {pre_stats['max_depth']}")

        if dry_run:
            print("\n=== 드라이런 모드: 변경 계획만 출력 ===")
            await self._dry_run_analysis()
            return

        # === 간단하고 빠른 정리: fanout_limit만 적용 ===
        
        # 1단계: fanout_limit 적용 (클러스터링)
        await self._enforce_fanout_limits()
        
        # 마지막: 모든 부모 노드 요약 병렬 업데이트
        await self._update_all_parent_summaries_parallel()

        self.cleanup_stats['end_time'] = time.time()
        duration = self.cleanup_stats['end_time'] - self.cleanup_stats['start_time']
        
        if self.debug:
            print(f"트리 정리 완료 ({duration:.1f}초)")

        await self.apply_fanout_to_all_parents()
        await self._resolve_cross_parent_duplicates()
        await self._merge_similar_categories()
        await self._merge_similar_leaves()

        # 모든 부모 노드를 병렬로 업데이트
        await self._update_all_parent_summaries_parallel()

        if rename_nodes:
            await self._rename_nodes()

        self.memory_manager.save_tree()
        self.cleanup_stats['end_time'] = time.time()
        post_stats = self._generate_tree_stats()
        if self.debug:
            print(f"트리 정리 완료 ({self.cleanup_stats['end_time'] - self.cleanup_stats['start_time']:.1f}초)")
        return self.cleanup_stats

    async def _dry_run_analysis(self):
        """드라이런 모드에서 변경 계획을 분석하고 출력합니다."""
        print("\n--- 1. 자식 과다 분석 ---")
        excessive_nodes = self._find_excessive_fanout_nodes()
        for node_id, child_count in excessive_nodes:
            node = self.memory_manager.get_node(node_id)
            print(f"- '{node.topic}': {child_count}개 자식 (한도: {self.fanout_limit}) -> 군집화 예정")

        print("\n--- 2. 중복 노드 분석 ---")
        duplicates = await self._find_duplicate_topics()
        for topic, node_ids in duplicates.items():
            if len(node_ids) > 1:
                print(f"- 중복 주제 '{topic}': {len(node_ids)}개 노드 -> 병합 예정")

        print("\n--- 3. 유사 리프 분석 ---")
        similar_groups = await self._find_similar_leaf_groups()
        for group in similar_groups:
            if len(group) > 1:
                topics = [self.memory_manager.get_node(nid).topic for nid in group]
                print(f"- 유사 리프 그룹: {topics} -> 병합 예정")

        print("\n=== 예상 결과 ===")
        print(f"- 생성될 그룹: {len(excessive_nodes)}개")
        print(f"- 병합될 노드: {sum(len(ids)-1 for ids in duplicates.values())}개")
        print(f"- 정리될 리프: {sum(len(group)-1 for group in similar_groups)}개")

    async def apply_fanout_to_all_parents(self):
        """모든 부모 노드에 fanout_limit 적용"""
        if self.debug:
            print("모든 부모 노드에 fanout_limit 적용 시작")

        all_nodes = list(self.memory_manager.memory_tree.values())

        for node in all_nodes:
            if node.topic != "ROOT" and len(node.children_ids) > self.fanout_limit:
                if self.debug:
                    print(f"노드 '{node.topic}'의 자식 수 {len(node.children_ids)}개 > fanout_limit {self.fanout_limit}")

                # 초과 자식들을 간단하게 그룹화
                await self._simple_group_excess_children(node)

        if self.debug:
            print("모든 부모 노드에 fanout_limit 적용 완료")

    async def _simple_group_excess_children(self, parent_node):
        """초과 자식들을 클러스터링하여 fanout_limit를 엄격하게 준수"""
        if len(parent_node.children_ids) <= self.fanout_limit:
            return

        if self.debug:
            print(f"클러스터링 시작: {len(parent_node.children_ids)}개 -> 최대 {self.fanout_limit}개")

        # 간단한 접근: fanout_limit까지는 그대로 두고, 나머지는 그룹화
        children_to_keep = parent_node.children_ids[:self.fanout_limit-1]  # 하나 자리를 그룹을 위해 비워둠
        children_to_group = parent_node.children_ids[self.fanout_limit-1:]
        
        if not children_to_group:
            return
            
        # 초과 자식들을 하나의 그룹으로 통합
        group_nodes = [self.memory_manager.get_node(cid) for cid in children_to_group if self.memory_manager.get_node(cid)]
        if not group_nodes:
            return
            
        group_name = await self._generate_cluster_group_name(group_nodes)
        
        # 새 그룹 노드 생성
        group_node = MemoryNode(
            topic=group_name,
            summary=f"{group_name} 관련 개념들",
            parent_id=parent_node.node_id,
            coordinates={"start": -1, "end": -1}
        )
        self.memory_manager.add_node(group_node, parent_node.node_id)

        # 초과 자식들을 그룹으로 이동
        for child_id in children_to_group:
            self.memory_manager.reparent_node(child_id, group_node.node_id)

        # 최종 검증
        final_count = len(parent_node.children_ids)
        if final_count > self.fanout_limit:
            if self.debug:
                print(f"경고: 클러스터링 후에도 fanout_limit 초과 ({final_count} > {self.fanout_limit})")
        else:
            if self.debug:
                original_count = final_count + len(children_to_group)
                print(f"클러스터링 완료: {original_count}개 → {final_count}개 (limit: {self.fanout_limit})")

    async def _generate_simple_group_name(self, nodes):
        """노드들을 기반으로 간단한 그룹 이름을 생성합니다."""
        if not nodes:
            return "기타 그룹"

        topics = [node.topic for node in nodes if node.topic != "ROOT"]
        
    async def _generate_cluster_group_name(self, nodes):
        """클러스터링된 노드들을 기반으로 의미있는 그룹 이름을 생성합니다."""
        if not nodes:
            return "기타 그룹"

        # 노드들의 토픽과 요약을 수집
        topics = [node.topic for node in nodes if node.topic != "ROOT"]
        summaries = [node.summary[:100] for node in nodes if node.summary]
        
        if len(topics) <= 2:
            # 적은 수의 노드는 단순 결합
            return " & ".join(topics[:2])
        
        # AI를 통해 의미있는 그룹명 생성
        try:
            prompt = f"""다음 개념들을 포괄하는 적절한 카테고리명을 한국어로 제안해주세요:

개념들: {', '.join(topics)}
요약: {' | '.join(summaries[:3])}

요구사항:
- 2-4글자의 간결한 카테고리명
- 모든 개념을 포괄할 수 있는 상위 개념
- 예시: "물리학", "생물학", "기초과학", "실용정보" 등

카테고리명:"""
            
            group_name = await self.ai_manager.call_ai_async_single(prompt, "클러스터 그룹명 생성")
            group_name = group_name.strip().replace('"', '').replace("'", '')
            
            # 길이 제한
            if len(group_name) > 10:
                group_name = group_name[:10]
                
            return group_name if group_name else "관련 개념"
            
        except Exception as e:
            if self.debug:
                print(f"그룹명 생성 실패: {e}")
            return "관련 개념"
        if len(topics) <= 2:
            return " & ".join(topics[:2]) if topics else "기타 그룹"

        # 첫 번째 토픽의 첫 단어들로 그룹명 생성
        first_topic_words = topics[0].split()[:2]
        return " ".join(first_topic_words) + " 등"

    def _find_excessive_fanout_nodes(self):
        """fanout_limit를 초과하는 노드들을 찾습니다."""
        return [(nid, len(n.children_ids)) for nid, n in self.memory_manager.memory_tree.items()
                if len(n.children_ids) > self.fanout_limit and n.topic != "ROOT"]

    async def _resolve_cross_parent_duplicates(self):
        """교차 부모간 중복/유사 노드를 해결합니다."""
        if self.debug: print("\n--- 2단계: 교차 부모 중복 해결 ---")
        duplicates = await self._find_duplicate_topics()
        for topic, node_ids in duplicates.items():
            if len(node_ids) > 1:
                await self._merge_duplicate_nodes(node_ids, topic)

    async def _find_duplicate_topics(self):
        """동일한 topic을 가진 노드들을 찾습니다."""
        topic_groups = defaultdict(list)
        for node_id, node in self.memory_manager.memory_tree.items():
            if node.topic != "ROOT":
                topic_groups[node.topic].append(node_id)
        return {topic: ids for topic, ids in topic_groups.items() if len(ids) > 1}

    async def _merge_duplicate_nodes(self, node_ids, topic):
        """중복된 노드들을 병합합니다."""
        if self.debug: print(f"중복 병합: '{topic}'")

        nodes = [self.memory_manager.get_node(nid) for nid in node_ids]
        
        # 카테고리 노드와 대화 노드 분리
        category_nodes = [n for n in nodes if n.is_category_node()]
        talk_nodes = [n for n in nodes if n.is_talk_node()]
        
        # 카테고리 노드들끼리만 병합
        if len(category_nodes) > 1:
            representative = max(category_nodes, key=lambda n: len(n.children_ids))
            for node in category_nodes:
                if node.node_id != representative.node_id:
                    await self._merge_category_to_representative(node, representative)
                    self.cleanup_stats['merges'] += 1
        
        # 대화 노드들끼리만 병합
        if len(talk_nodes) > 1:
            representative = max(talk_nodes, key=lambda n: len(getattr(n, 'conversation_indices', [])))
            for node in talk_nodes:
                if node.node_id != representative.node_id:
                    await self._merge_talk_to_representative(node, representative)
                    self.cleanup_stats['merges'] += 1

    async def _merge_category_to_representative(self, source_node, target_node):
        """카테고리 노드를 대표 카테고리 노드에 병합합니다."""
        # 카테고리 노드는 대화 인덱스를 가지면 안 됨
        if hasattr(source_node, 'conversation_indices') and source_node.conversation_indices:
            if self.debug:
                print(f"⚠️  경고: 카테고리 노드 '{source_node.topic}'가 대화를 가지고 있음 - 대화 제거")
            source_node.conversation_indices = []
        
        # 참조 정보 병합
        if hasattr(source_node, 'references') and hasattr(target_node, 'references'):
            for ref_id in source_node.references:
                if ref_id not in target_node.references:
                    target_node.references.append(ref_id)

        # 자식 노드 재부모 설정
        for child_id in source_node.children_ids:
            self.memory_manager.reparent_node(child_id, target_node.node_id)

        # 요약 업데이트 (AI를 통한 자연스러운 통합)
        target_node.summary = await self._generate_merged_summary(target_node, source_node)

        # 소스 노드 제거
        self._remove_node(source_node.node_id)

        # 병합 후 부모 노드 요약 업데이트는 마지막에 병렬로 처리
        # (개별 업데이트 제거하여 중복 방지)

        if self.debug:
            print(f"카테고리 병합 완료: '{source_node.topic}' -> '{target_node.topic}'")
            print(f"  - 최종 자식 수: {len(target_node.children_ids)}")

    async def _merge_talk_to_representative(self, source_node, target_node):
        """대화 노드를 대표 대화 노드에 병합합니다."""
        # 대화 인덱스 안전하게 병합 (중복 제거)
        if hasattr(source_node, 'conversation_indices') and hasattr(target_node, 'conversation_indices'):
            original_count = len(target_node.conversation_indices)
            for conv_idx in source_node.conversation_indices:
                if conv_idx not in target_node.conversation_indices:
                    target_node.conversation_indices.append(conv_idx)
            target_node.conversation_indices.sort()
            added_count = len(target_node.conversation_indices) - original_count
            if self.debug and added_count > 0:
                print(f"대화 인덱스 병합: {added_count}개 추가, 총 {len(target_node.conversation_indices)}개")

        # 참조 정보 병합
        if hasattr(source_node, 'references') and hasattr(target_node, 'references'):
            for ref_id in source_node.references:
                if ref_id not in target_node.references:
                    target_node.references.append(ref_id)

        # 요약 업데이트 (AI를 통한 자연스러운 통합)
        target_node.summary = await self._generate_merged_summary(target_node, source_node)

        # 소스 노드 제거
        self._remove_node(source_node.node_id)

        # 병합 후 부모 노드 요약 업데이트는 마지막에 병렬로 처리
        # (개별 업데이트 제거하여 중복 방지)

        if self.debug:
            print(f"대화 병합 완료: '{source_node.topic}' -> '{target_node.topic}'")
            print(f"  - 최종 대화 수: {len(target_node.conversation_indices)}")

    async def _merge_node_to_representative(self, source_node, target_node):
        """소스 노드를 타겟 노드에 병합합니다."""
        # 1. 대화 인덱스 안전하게 병합 (중복 제거)
        if hasattr(source_node, 'conversation_indices') and hasattr(target_node, 'conversation_indices'):
            original_count = len(target_node.conversation_indices)
            for conv_idx in source_node.conversation_indices:
                if conv_idx not in target_node.conversation_indices:
                    target_node.conversation_indices.append(conv_idx)
            target_node.conversation_indices.sort()
            added_count = len(target_node.conversation_indices) - original_count
            if self.debug and added_count > 0:
                print(f"대화 인덱스 병합: {added_count}개 추가, 총 {len(target_node.conversation_indices)}개")

        # 2. 참조 정보 병합
        if hasattr(source_node, 'references') and hasattr(target_node, 'references'):
            for ref_id in source_node.references:
                if ref_id not in target_node.references:
                    target_node.references.append(ref_id)

        # 3. 자식 노드 재부모 설정
        for child_id in source_node.children_ids:
            self.memory_manager.reparent_node(child_id, target_node.node_id)

        # 4. 요약 업데이트 (AI를 통한 자연스러운 통합)
        target_node.summary = await self._generate_merged_summary(target_node, source_node)

        # 5. 소스 노드 제거
        self._remove_node(source_node.node_id)

        if self.debug:
            print(f"병합 완료: '{source_node.topic}' -> '{target_node.topic}'")
            print(f"  - 최종 대화 수: {len(target_node.conversation_indices)}")
            print(f"  - 참조 수: {len(target_node.references) if hasattr(target_node, 'references') else 0}")

    async def _generate_merged_summary(self, target_node, source_node):
        """병합된 노드의 요약을 생성합니다."""
        # 요약 변경 최소화를 위한 개선된 로직
        if not target_node.summary and not source_node.summary:
            return f"{target_node.topic}에 대한 내용"

        if not target_node.summary:
            return source_node.summary

        if not source_node.summary:
            return target_node.summary

        # 두 요약이 동일하면 변경하지 않음
        if target_node.summary == source_node.summary:
            return target_node.summary

        # AI를 통한 자연스러운 요약 통합
        system_prompt = """두 노드의 요약을 자연스럽게 통합하라.
중요한 지시사항:
- 원래 요약의 핵심 내용을 최대한 보존하라
- 새로운 내용을 추가하되 원래 의미를 왜곡하지 마라
- 중복되는 내용은 정리하고 간결하게 작성하라
- 1-2문장으로 요약하라"""

        merge_text = f"""기존 요약: {target_node.summary}
추가 요약: {source_node.summary}
주제: {target_node.topic}"""

        try:
            merged = await self.ai_manager.call_ai_async_single(merge_text, system_prompt)
            if self.debug:
                print(f"요약 통합 완료: {len(merged)}자")
            return merged
        except Exception as e:
            if self.debug:
                print(f">>>> [ERROR] 병합 요약 생성 오류: {e}")
            # 폴백: 간단한 결합
            return f"{target_node.summary}; {source_node.summary}"

    def _remove_node(self, node_id):
        """노드를 트리에서 제거합니다."""
        node = self.memory_manager.get_node(node_id)
        if not node:
            return

        # 대화 삭제 방지: 노드에 대화가 남아있는지 확인
        if hasattr(node, 'conversation_indices') and node.conversation_indices:
            if self.debug:
                print(f"⚠️  경고: 삭제하려는 노드 '{node.topic}'에 {len(node.conversation_indices)}개 대화가 남아있음")
                print(f"   대화 인덱스: {node.conversation_indices}")
                print(f"   이 노드는 병합되지 않은 상태로 삭제될 수 없음")
            return  # 대화가 있는 노드는 삭제하지 않음

        # 부모에서 제거
        if node.parent_id and (parent := self.memory_manager.get_node(node.parent_id)):
            if node_id in parent.children_ids:
                parent.children_ids.remove(node_id)
                if self.debug:
                    print(f"부모 '{parent.topic}'에서 노드 제거 완료")

        # 트리에서 완전히 제거
        if node_id in self.memory_manager.memory_tree:
            del self.memory_manager.memory_tree[node_id]
            if self.debug:
                print(f"노드 '{node.topic}' 트리에서 완전히 제거됨")

        # 통계 업데이트
        self.cleanup_stats['removed_nodes'] += 1

    async def _merge_similar_leaves(self):
        """유사한 리프 노드들을 병합합니다."""
        if self.debug: print("\n--- 4단계: 유사 리프 병합 ---")
        for group in await self._find_similar_leaf_groups():
            if len(group) > 1:
                await self._merge_leaf_group(group)

    async def _merge_similar_categories(self):
        """의미적으로 유사한 카테고리들을 병합합니다."""
        if self.debug: print("\n--- 3단계: 유사 카테고리 병합 ---")
        for group in await self._find_similar_category_groups():
            if len(group) > 1:
                await self._merge_category_group(group)

    async def _find_similar_category_groups(self):
        """유사한 카테고리 노드 그룹들을 찾습니다."""
        root = self.memory_manager.get_root_node()
        if not root: return []

        category_nodes = [self.memory_manager.get_node(cid) for cid in root.children_ids if self.memory_manager.get_node(cid) and self.memory_manager.get_node(cid).coordinates.get("start") == -1]
        if len(category_nodes) <= 1: return []

        if self.debug: print(f">> {len(category_nodes)}개 최상위 카테고리 간 유사도 분석 시작.")
        clusters = self._connected_components_clustering(category_nodes, await self._build_similarity_matrix(category_nodes))
        return [[node.node_id for node in c] for c in clusters if len(c) > 1]

    async def _merge_category_group(self, category_node_ids):
        """유사 카테고리 그룹을 하나의 대표 카테고리로 병합합니다."""
        nodes = [self.memory_manager.get_node(nid) for nid in category_node_ids]
        representative = max(nodes, key=lambda n: len(n.children_ids))

        if self.debug: print(f">> 카테고리 병합: {[n.topic for n in nodes]} -> '{representative.topic}'")

        # 모든 자식 노드들을 대표 노드로 이동
        for node in nodes:
            if node.node_id != representative.node_id:
                for child_id in node.children_ids:
                    self.memory_manager.reparent_node(child_id, representative.node_id)
                    self.cleanup_stats['moves'] += 1
                # summary 누적 병합
                representative.summary = await self._generate_merged_summary(representative, node)
                self._remove_node(node.node_id)
                self.cleanup_stats['merges'] += 1

        # 병합 완료 후 대표 노드의 주제와 요약을 자식들에 맞게 재생성
        await self._update_merged_category_topic_and_summary(representative)

    async def _update_merged_category_topic_and_summary(self, category_node):
        """병합된 카테고리 노드의 주제와 요약을 자식 노드들에 맞게 업데이트합니다."""
        if not category_node.children_ids:
            return
        
        # 자식 노드들의 정보 수집
        child_nodes = [self.memory_manager.get_node(cid) for cid in category_node.children_ids]
        child_nodes = [c for c in child_nodes if c]  # None 제거
        
        if not child_nodes:
            return
        
        child_topics = [c.topic for c in child_nodes]
        child_summaries = [c.summary for c in child_nodes]
        
        # 새로운 주제 생성
        old_topic = category_node.topic
        topic_prompt = f"""
        다음 하위 주제들을 포괄하는 적절한 상위 카테고리명을 2-8자의 한국어로 생성하라:
        하위 주제들: {', '.join(child_topics)}
        
        기존 주제: {old_topic}
        
        원칙:
        - 모든 하위 주제들을 포괄할 수 있는 상위 개념
        - 2-8자의 간결한 한국어
        - 구체적이면서도 포괄적인 표현
        - 예: "지구 위성", "태양계 최대 행성", "물 화학식" → "우주와 물질"
        - 예: "피타고라스 정리", "뉴턴 제1법칙" → "물리수학 법칙"
        
        오직 카테고리명만 답변하라.
        """
        
        try:
            new_topic = await self.ai_manager.call_ai_async_single(topic_prompt, "카테고리 주제 생성")
            new_topic = new_topic.strip()[:20]  # 최대 20자 제한
            
            if new_topic and new_topic != old_topic:
                category_node.topic = new_topic
                if self.debug:
                    print(f">> 병합 카테고리 주제 업데이트: '{old_topic}' -> '{new_topic}'")
        except Exception as e:
            if self.debug:
                print(f">> [ERROR] 카테고리 주제 업데이트 실패: {e}")
        
        # 새로운 요약 생성 (자식 노드들의 구체적 내용 반영)
        summary_prompt = f"""
        다음 하위 주제들을 포괄하는 카테고리의 요약을 생성하라:
        
        카테고리명: {category_node.topic}
        하위 주제들과 내용:
        {chr(10).join([f"- {topics}: {summaries}" for topics, summaries in zip(child_topics[:5], child_summaries[:5])])}
        
        이 카테고리가 포함하는 실제 내용을 반영하여 요약하라.
        구체적인 하위 주제들이 무엇을 다루는지 명시적으로 언급하라.
        예: "지구의 자연 위성인 달과 태양계 최대 행성인 목성에 관한 정보"
        예: "물의 화학적 조성과 피타고라스 정리 등 기초 과학 개념들"
        
        최대 120자 이내로 작성하라.
        """
        
        try:
            new_summary = await self.ai_manager.call_ai_async_single(summary_prompt, "카테고리 요약 생성")
            new_summary = new_summary.strip()[:120]  # 최대 120자 제한
            
            if new_summary:
                old_summary = category_node.summary
                category_node.summary = new_summary
                if self.debug:
                    print(f">> 병합 카테고리 요약 업데이트 완료 (길이: {len(new_summary)}자)")
        except Exception as e:
            if self.debug:
                print(f">> [ERROR] 카테고리 요약 업데이트 실패: {e}")

    async def _find_similar_leaf_groups(self):
        """유사한 리프 노드 그룹들을 찾습니다."""
        leaf_nodes = [n for n in self.memory_manager.memory_tree.values() if not n.children_ids and n.coordinates.get("start") != -1]
        if len(leaf_nodes) <= 1: return []

        parent_groups = defaultdict(list)
        for node in leaf_nodes:
            parent_groups[node.parent_id].append(node)

        similar_groups = []
        for nodes in parent_groups.values():
            if len(nodes) > 1:
                clusters = self._connected_components_clustering(nodes, await self._build_similarity_matrix(nodes))
                similar_groups.extend([c for c in clusters if len(c) > 1])

        return [[node.node_id for node in group] for group in similar_groups]

    async def _merge_leaf_group(self, leaf_node_ids):
        """유사한 리프 노드 그룹을 병합합니다."""
        nodes = [self.memory_manager.get_node(nid) for nid in leaf_node_ids]
        nodes = [n for n in nodes if n]  # None 제거

        if len(nodes) < 2:
            return

        representative = nodes[0]

        # conversation_indices를 안전하게 병합 (중복 제거)
        if not hasattr(representative, 'conversation_indices'):
            representative.conversation_indices = []

        original_count = len(representative.conversation_indices)

        for node in nodes[1:]:
            if hasattr(node, 'conversation_indices'):
                for conv_idx in node.conversation_indices:
                    if conv_idx not in representative.conversation_indices:
                        representative.conversation_indices.append(conv_idx)

            # 참조 정보도 병합
            if hasattr(node, 'references') and hasattr(representative, 'references'):
                for ref_id in node.references:
                    if ref_id not in representative.references:
                        representative.references.append(ref_id)

            # 깊이 제한 초과 시 참조 추가로 해결
            current_depth = self.memory_manager.get_node_depth(representative.node_id)
            if current_depth >= self.max_depth:
                if self.debug:
                    print(f"깊이 제한 초과: 노드 '{node.topic}'을 참조로 추가")
                # 깊이 초과 시 병합 대신 참조 추가
                if node.node_id not in representative.references:
                    representative.references.append(node.node_id)
                continue

            # 노드 삭제 전에 부모 관계 정리
            if node.parent_id and (parent := self.memory_manager.get_node(node.parent_id)):
                if node.node_id in parent.children_ids:
                    parent.children_ids.remove(node.node_id)

            # 트리에서 노드 삭제
            if node.node_id in self.memory_manager.memory_tree:
                del self.memory_manager.memory_tree[node.node_id]

            self.cleanup_stats['merges'] += 1

        representative.conversation_indices.sort()
        added_conversations = len(representative.conversation_indices) - original_count

        # 요약 업데이트
        representative.summary = await self._generate_leaf_merge_summary(representative)

        if self.debug:
            print(f">>>> 리프 병합: {[n.topic for n in nodes]} -> '{representative.topic}'")
            print(f">>>>   - 추가된 대화: {added_conversations}개, 총 {len(representative.conversation_indices)}개")
            print(f">>>>   - 참조 수: {len(representative.references) if hasattr(representative, 'references') else 0}개")

    async def _generate_leaf_merge_summary(self, merged_node):
        """병합된 리프 노드의 요약을 생성합니다."""
        system_prompt = '여러 대화가 병합된 노드의 요약을 "여러 대화가 포함됨"을 명시하여 작성하라.'
        conv_count = len(merged_node.conversation_indices) if hasattr(merged_node, 'conversation_indices') else 1
        try:
            return await self.ai_manager.call_ai_async_single(f"노드: {merged_node.topic}, 기존 요약: {merged_node.summary}, 대화 수: {conv_count}", system_prompt)
        except Exception as e:
            if self.debug: print(f">>>> [ERROR] 리프 병합 요약 생성 오류: {e}")
            return f"{merged_node.summary} (병합된 {conv_count}개 대화)"

    async def _rename_nodes(self):
        """노드들의 이름을 병렬로 정리합니다."""
        if self.debug:
            print("\n--- 5단계: 노드 이름 정리 ---")

        category_nodes = [
            node for node in self.memory_manager.memory_tree.values()
            if node.coordinates.get("start") == -1 and node.topic != "ROOT"
        ]
        if not category_nodes:
            return

        system_prompt = """노드의 정보를 바탕으로 더 적절한 2~15자의 한국어 이름을 제안하라. 현재 이름보다 명확하고 포괄적이어야 한다. 답변은 반드시 따옴표 안에 하나의 이름만 포함하라. 예: \"과일 종류\" """
        queries = []
        for node in category_nodes:
            subtopics = ', '.join([
                self.memory_manager.get_node(cid).topic
                for cid in node.children_ids[:3]
                if self.memory_manager.get_node(cid)
            ])
            queries.append(f'현재 이름: "{node.topic}", 요약: {node.summary}, 하위 주제: {subtopics}')

        if self.debug:
            print(f">> {len(queries)}개 카테고리 이름 병렬 생성 시작...")

        start_time = time.time()
        new_names_raw = await self.ai_manager.call_ai_async_multiple(queries, system_prompt)
        if self.debug:
            print(f">> 이름 생성 완료. (소요시간: {time.time() - start_time:.2f}초)")
        for i, node in enumerate(category_nodes):
            new_name = self._extract_clean_name(new_names_raw[i], node.topic)
            # 빈 문자열, "주제", "이름" 등 무의미한 결과는 무시
            if not new_name or new_name.strip() in ["", "주제", "이름"]:
                if self.debug:
                    print(f">>>> [WARN] AI 이름 무의미: '{new_name}' -> 원본 유지")
                continue
            if new_name != node.topic:
                old_name = node.topic
                node.topic = new_name
                self.cleanup_stats['renames'] += 1
                if self.debug:
                    print(f">>>> 이름 변경: '{old_name}' -> '{new_name}'")

    def _extract_clean_name(self, ai_response, original_name):
        """AI 응답에서 깨끗한 이름만 추출합니다. 실패 시 원본 이름을 반환합니다."""
        if ai_response:
            match = re.search(r'["\"]([^"\\]{2,15})["\"]', ai_response)
            if match:
                candidate = match.group(1).strip()
                if 2 <= len(candidate) <= 15 and candidate not in ["", "주제", "이름"]:
                    return candidate
        return original_name

    def _generate_tree_stats(self):
        """트리 통계를 생성합니다."""
        total_nodes = len(self.memory_manager.memory_tree)
        if not total_nodes:
            return {'total_nodes': 0, 'avg_fanout': 0, 'max_depth': 0}

        fanouts = [len(n.children_ids) for n in self.memory_manager.memory_tree.values()]
        max_depth = max(self.memory_manager.get_node_depth(nid) for nid in self.memory_manager.memory_tree)

        return {
            'total_nodes': total_nodes,
            'avg_fanout': sum(fanouts) / total_nodes,
            'max_depth': max_depth
        }

    async def _build_similarity_matrix(self, nodes):
        """노드들 간의 유사도 매트릭스를 구축합니다."""
        n = len(nodes)
        similarity_matrix = [[0.0 for _ in range(n)] for _ in range(n)]
        
        # 대각선은 1.0 (자기 자신과의 유사도)
        for i in range(n):
            similarity_matrix[i][i] = 1.0
        
        # 상삼각 행렬만 계산하고 대칭으로 복사
        queries = []
        pairs = []
        
        for i in range(n):
            for j in range(i + 1, n):
                node1, node2 = nodes[i], nodes[j]
                prompt = f"""노드1: "{node1.topic}"
노드1 설명: {node1.summary}

노드2: "{node2.topic}"  
노드2 설명: {node2.summary}

위 두 노드가 **정확히 동일한 세부 주제**이거나 **직접적인 상위/하위 관계**인가요?
완전히 다른 주제는 절대 병합하지 마라.

예시:
- "지구 위성" + "달의 특성" → True (직접적 관련)
- "지구 위성" + "물의 화학식" → False (완전히 다른 주제)
- "수학 이론" + "기하학" → True (직접적 상위/하위)
- "수학 이론" + "화학 원소" → False (완전히 다른 주제)"""
                queries.append(prompt)
                pairs.append((i, j))
        
        if queries:
            system_prompt = """두 노드가 **정확히 동일한 세부 주제**이거나 **직접적인 상위/하위 관계**인지만 판단하라.

❌ 병합하지 말아야 할 경우:
- 서로 다른 학문 분야 (물리학 vs 화학)
- 서로 다른 주제 영역 (천문학 vs 수학)  
- 간접적 연관성만 있는 경우
- 같은 큰 범주라는 이유만으로 연결되는 경우

✅ 병합해야 할 경우만:
- 정확히 동일한 주제
- 직접적인 상위/하위 개념 관계
- 실질적으로 같은 맥락에서 다뤄지는 주제

확실하지 않으면 무조건 "False"로 답하라.
반드시 "True" 또는 "False"로만 답하라."""
            
            results = await self.ai_manager.call_ai_async_multiple(
                queries, system_prompt, fine=NODE_SIMILARITY_FINE
            )
            
            for k, (i, j) in enumerate(pairs):
                is_similar = results[k].strip().lower() == 'true'
                similarity = 0.95 if is_similar else 0.05  # 더욱 엄격한 임계값 설정
                similarity_matrix[i][j] = similarity
                similarity_matrix[j][i] = similarity  # 대칭 복사
        
        return similarity_matrix

    def _connected_components_clustering(self, nodes, similarity_matrix):
        """연결 성분 기반 클러스터링을 수행합니다."""
        n = len(nodes)
        if n <= 1:
            return [nodes] if nodes else []
        
        # 인접 리스트 구성 (유사도 임계값 0.9 이상으로 매우 엄격하게)
        threshold = 0.9
        adjacency = [[] for _ in range(n)]
        
        for i in range(n):
            for j in range(i + 1, n):
                if similarity_matrix[i][j] >= threshold:
                    adjacency[i].append(j)
                    adjacency[j].append(i)
        
        # DFS로 연결 성분 찾기
        visited = [False] * n
        clusters = []
        
        def dfs(start, current_cluster):
            visited[start] = True
            current_cluster.append(nodes[start])
            for neighbor in adjacency[start]:
                if not visited[neighbor]:
                    dfs(neighbor, current_cluster)
        
        for i in range(n):
            if not visited[i]:
                cluster = []
                dfs(i, cluster)
                clusters.append(cluster)
        
        return clusters

    async def _update_all_parent_summaries_parallel(self):
        """모든 부모 노드들의 요약을 병렬로 업데이트합니다."""
        if self.debug:
            print("\n--- 최종 단계: 모든 부모 노드 요약 병렬 업데이트 ---")
        
        # 자식이 있는 모든 노드 (ROOT 제외)
        parent_nodes = []
        for node_id, node in self.memory_manager.memory_tree.items():
            if node.children_ids and node.topic != "ROOT":
                parent_nodes.append(node)
        
        if not parent_nodes:
            return
        
        if self.debug:
            print(f">> {len(parent_nodes)}개 부모 노드 병렬 업데이트 시작...")
            start_time = time.time()
        
        from .AuxiliaryAI import AuxiliaryAI
        auxiliary_ai = AuxiliaryAI(self.memory_manager, debug=False)  # 개별 디버그 끄기
        
        # 진짜 병렬로 실행하기 위해 create_task 사용
        tasks = []
        for i, node in enumerate(parent_nodes):
            task = asyncio.create_task(
                auxiliary_ai.update_topic_and_summary(node, recursive=False),
                name=f"update_parent_{i}_{node.topic}"
            )
            tasks.append(task)
        
        # 모든 업데이트를 병렬로 실행하고 결과 대기
        try:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 에러 체크
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    if self.debug:
                        print(f"부모 노드 업데이트 실패 {parent_nodes[i].topic}: {result}")
                        
        except Exception as e:
            if self.debug:
                print(f"병렬 업데이트 중 오류: {e}")
        
        if self.debug:
            elapsed = time.time() - start_time
            print(f">> {len(parent_nodes)}개 부모 노드 병렬 업데이트 완료 ({elapsed:.2f}초)")

    async def _refresh_merged_category_summaries(self, merged_nodes):
        """병합된 카테고리 노드들의 요약을 자식 내용 기반으로 새로 고침합니다."""
        if not merged_nodes:
            return
        
        if self.debug:
            print(f"\n--- 병합된 {len(merged_nodes)}개 카테고리 요약 새로고침 ---")
        
        from .AuxiliaryAI import AuxiliaryAI
        auxiliary_ai = AuxiliaryAI(self.memory_manager, debug=self.debug)
        
        # 각 병합된 노드를 병렬로 업데이트
        tasks = []
        for node in merged_nodes:
            # 강제로 자식 내용 기반 요약 재생성
            task = auxiliary_ai.update_topic_and_summary(node, recursive=False)
            tasks.append(task)
        
        await asyncio.gather(*tasks, return_exceptions=True)
        
        if self.debug:
            print(f">> 병합된 카테고리 요약 새로고침 완료")
