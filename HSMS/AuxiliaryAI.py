import asyncio
import re
from config import (CATEGORY_RELEVANCE_FINE, 
                   NEW_TOPIC_FINE, CONVERSATION_SEPARATION_FINE, GROUP_SIMILARITY_FINE, ALL_MEMORY, get_config_value)
from .AIManager import AIManager
from .KDistanceSearch import KDistanceSearch
from .MemoryNode import MemoryNode


class AuxiliaryAI:
    """보조 인공지능 - 계층적 기억 관리 시스템의 핵심 컨트롤러"""
    
    def __init__(self, memory_manager, debug=False, short_debug=False, max_depth=None, top_search_n=None):
        from config import get_config_value
        self.memory_manager = memory_manager
        self.ai_manager = AIManager(debug=debug, short_debug=short_debug)
        self.k_distance_search = KDistanceSearch(memory_manager, self.ai_manager, debug=debug)
        self.debug = debug
        self.short_debug = short_debug
        self.max_depth = max_depth if max_depth is not None else get_config_value('max_depth')
        self.top_search_n = top_search_n if top_search_n is not None else get_config_value('top_search_n')
        self._save_lock = asyncio.Lock()  # save_tree 동기화를 위한 락

    async def update_topic_and_summary(self, node, recursive=False):
        """
        노드의 topic(주제)와 summary(요약)을 AI로 재생성.
        recursive=True면 부모/자식 노드까지 재귀적으로 갱신.
        """
        # 1. 자식 노드 요약/주제 정보 수집
        child_nodes = [self.memory_manager.get_node(cid) for cid in getattr(node, 'children_ids', [])]
        child_topics = [c.topic for c in child_nodes if c]
        child_summaries = [c.summary for c in child_nodes if c]

        # 2. AI 프롬프트 구성
        topic_prompt = f"""
        부모 노드 주제: {node.topic}
        자식 노드 주제 목록: {', '.join(child_topics)}
        현재 노드의 위치와 자식 노드들의 주제를 고려하여, 이 노드의 새로운 주제를 2~8자 이내의 명사로 생성하라. 답변은 반드시 따옴표 안에 하나의 단어만 포함해야 한다.
        """
        
        # 3. AI 호출 (topic)
        try:
            new_topic = await self.ai_manager.call_ai_async_single(topic_prompt, "주제 생성")
            # 따옴표 제거 및 후처리
            import re
            match = re.search(r'"([^"]{2,8})"', new_topic)
            if match:
                new_topic = match.group(1).strip()
            else:
                new_topic = new_topic.strip().replace('"', '')
        except Exception as e:
            if self.debug:
                print(f"[ERROR] 주제 생성 실패: {e}")
            new_topic = node.topic
        
        # 자식 노드 요약 결합
        combined_child_summaries = '; '.join(child_summaries)
        max_length = get_config_value('max_summary_length')
        
        if len(combined_child_summaries) > max_length:
            # 길이가 초과되면 AI로 요약
            print(f"📝 [요약 시작] 자식 노드 요약이 {len(combined_child_summaries)}자 > {max_length}자 제한을 초과하여 AI 요약을 시작합니다...")
            
            summary_prompt = f"""
            다음 자식 노드 요약들을 {max_length}자 이내로 요약하라.
            
            중요한 지시사항:
            - 사용자가 한 말, 키워드, 구체적인 용어, 고유명사, 숫자, 날짜 등을 중요도를 따지지 않고 모두 유지하라
            - 원래 내용의 핵심 의미와 세부사항을 최대한 보존하라
            - 요약하되 정보 손실을 최소화하라
            - 사용자의 질문, AI의 답변, 구체적인 사실 관계를 모두 포함하라
            - 전문 용어와 기술적 세부사항을 우선적으로 유지하라
            
            요약할 내용:
            {combined_child_summaries}
            """
            try:
                new_summary = await self.ai_manager.call_ai_async_single(summary_prompt, "요약 생성")
                if len(new_summary) > max_length:
                    new_summary = new_summary[:max_length].rstrip() + "..."
                print(f"✅ [요약 완료] 자식 노드 요약이 {len(new_summary)}자로 요약되었습니다.")
            except Exception as e:
                if self.debug:
                    print(f"[ERROR] 요약 생성 실패: {e}")
                new_summary = combined_child_summaries[:max_length].rstrip() + "..."
        else:
            new_summary = combined_child_summaries

        # 4. 노드 정보 갱신
        self.memory_manager.update_node(node.node_id, topic=new_topic, summary=new_summary)

        # 5. 재귀적 갱신 (부모/자식)
        if recursive:
            # 부모 노드 갱신
            if node.parent_id:
                parent_node = self.memory_manager.get_node(node.parent_id)
                if parent_node and parent_node.topic != "ROOT":
                    await self.update_topic_and_summary(parent_node, recursive=True)
            # 자식 노드 갱신
            for child in child_nodes:
                if child:
                    await self.update_topic_and_summary(child, recursive=True)

    async def _safe_save_tree(self):
        """Thread-safe tree saving operation"""
        async with self._save_lock:
            return self.memory_manager.save_tree()
    
    async def handle_conversation(self, conversation, conversation_index=None):
        """
        새로운 대화를 처리하고 적절한 노드에 저장한 뒤,
        마지막으로 상호작용한 리프 노드의 ID를 반환합니다.
        """
        # 1. 전체 기록에 저장
        if conversation_index is None:
            conversation_index = self.memory_manager.save_to_all_memory(conversation)
        
        # 2. 사용자 입력 분석
        user_input = conversation[0]['content']
        
        # 3. AI 기반 다중 카테고리 분류 및 동적 구조 관리
        # 이 함수가 마지막에 수정한 노드 ID를 반환하도록 수정합니다.
        last_node_id = await self._process_conversation_with_dynamic_structure(conversation, conversation_index)
        
        # 4. 노드 체인 업데이트 (새로운 방식)
        if last_node_id:
            await self.update_node_chain_after_save(last_node_id, conversation_index)
        
        return last_node_id
    async def _process_conversation_with_dynamic_structure(self, conversation, conversation_index):
        """동적 트리 구조를 고려하여 대화를 분류하고 저장합니다."""
        user_input = conversation[0]['content']
        
        if self.debug:
            print(f"\n>> [AUX] 동적 구조 처리 시작")
            print(f">>>> [AUX] 최대 깊이: {self.max_depth}")
        
        # 1. 기존 카테고리들과의 관련성 검사
        existing_categories = await self._get_existing_categories()
        
        if self.debug:
            if existing_categories:
                print(f">>>> [AUX] 기존 카테고리 {len(existing_categories)}개: {list(existing_categories.keys())}")
            else:
                print(f">>>> [AUX] 기존 카테고리 없음")
        
        # 2. 카테고리별 관련성 평가 (병렬 처리)
        category_summaries = {name: info['summary'] for name, info in existing_categories.items()}
        category_relevance = await self._check_category_relevance_async(user_input, category_summaries)
        relevant_categories = [name for name, is_relevant in category_relevance.items() if is_relevant]
        
        if self.debug:
            print(f">>>> [AUX] 관련 카테고리: {relevant_categories}")
        
        # 3. 카테고리 수에 따른 동적 처리
        if len(relevant_categories) == 0:
            # 신규 카테고리 생성
            node_id = await self._create_new_category_structure(conversation, conversation_index, user_input)
            return node_id
        elif len(relevant_categories) == 1:
            # 기존 카테고리 하위에 추가
            category_name = relevant_categories[0]
            node_id = await self._add_to_existing_category(conversation, conversation_index, category_name, user_input)
            return node_id
        else:
            # 다중 카테고리 - 그룹화 고려
            node_id = await self._handle_multiple_categories(conversation, conversation_index, relevant_categories, user_input)
            return node_id

    async def _create_new_category_structure(self, conversation, conversation_index, user_input):
        """새로운 카테고리 A와 그 하위 대화 노드 A1을 생성합니다."""
        if self.debug:
            print("신규 카테고리 생성")
        
        # 루트 깊이 확인
        root_node = self.memory_manager.get_root_node()
        if not self.memory_manager.can_insert_child(root_node.node_id, self.max_depth):
            if self.debug:
                print("깊이 초과: 기존 카테고리에 추가")
            # 가장 관련성 높은 기존 카테고리에 추가
            existing_categories = await self._get_existing_categories()
            if existing_categories:
                # 첫 번째 카테고리에 추가
                first_category = list(existing_categories.keys())[0]
                node_id = await self._add_to_existing_category(conversation, conversation_index, first_category, user_input)
                return node_id
        
        # fanout_limit 확인
        from config import get_config_value
        fanout_limit = get_config_value('fanout_limit')
        if len(root_node.children_ids) >= fanout_limit:
            if self.debug:
                print(f"fanout 초과 ({len(root_node.children_ids)} >= {fanout_limit}): 트리 정리 트리거")
            # 트리 정리 실행
            from .TreeCleanupEngine import TreeCleanupEngine
            cleanup_engine = TreeCleanupEngine(self.memory_manager, debug=self.debug)
            await cleanup_engine.run_cleanup()
        
        # AI를 통한 카테고리명과 요약을 병렬 생성
        category_name_task = self._generate_category_name(user_input)
        category_summary_task = self._generate_category_summary(user_input)
        category_name, category_summary = await asyncio.gather(category_name_task, category_summary_task)
        
        if self.debug:
            print(f"카테고리 생성: '{category_name}'")
        
        # 카테고리 노드 생성 (초기 요약은 기본값으로 설정)
        category_node = MemoryNode(
            topic=category_name,
            summary="",  # 초기에는 빈 요약으로 설정, 자식 노드 생성 후 업데이트
            parent_id=root_node.node_id,
            coordinates={"start": -1, "end": -1}  # 카테고리 표시
        )
        
        self.memory_manager.add_node(category_node, root_node.node_id)
        
        # 대화 노드 A1 생성
        conversation_topic = await self._generate_conversation_topic(user_input)
        conversation_summary = await self._generate_conversation_summary(conversation)
        
        conversation_node = MemoryNode(
            topic=conversation_topic,
            summary=conversation_summary,
            parent_id=category_node.node_id,
            coordinates={"start": conversation_index, "end": conversation_index},
            conversation_indices=[conversation_index]
        )
        
        self.memory_manager.add_node(conversation_node, category_node.node_id)
        
        # 부모 노드 요약 업데이트
        await self.update_parent_summary(category_node)
        
        if self.debug:
            print(f">>>> [AUX] 완료: 카테고리 '{category_name}' 및 대화 노드 생성")
        
        return conversation_node.node_id  # 생성된 대화 노드 ID 반환

    async def _add_to_existing_category(self, conversation, conversation_index, category_name, user_input):
        """기존 카테고리 A 하위에 새로운 대화 노드를 추가합니다."""
        if self.debug:
            print(f"기존 카테고리 확장: '{category_name}'")
        
        category_node_id = await self._find_category_node_id(category_name)
        category_node = self.memory_manager.get_node(category_node_id)
        
        # 깊이 확인
        if not self.memory_manager.can_insert_child(category_node_id, self.max_depth):
            if self.debug:
                print(f"깊이 초과: '{category_name}' 병합 적용")
            # 가장 유사한 기존 대화 노드에 병합
            node_id = await self._merge_to_similar_conversation(conversation, conversation_index, category_node_id, user_input)
            return node_id
        
        # fanout_limit 확인
        from config import get_config_value
        fanout_limit = get_config_value('fanout_limit')
        if len(category_node.children_ids) >= fanout_limit:
            if self.debug:
                print(f"fanout 초과 ({len(category_node.children_ids)} >= {fanout_limit}): '{category_name}' 카테고리 정리 트리거")
            # 트리 정리 실행
            from .TreeCleanupEngine import TreeCleanupEngine
            cleanup_engine = TreeCleanupEngine(self.memory_manager, debug=self.debug)
            await cleanup_engine.run_cleanup()
            
            # 정리 후 다시 확인
            category_node = self.memory_manager.get_node(category_node_id)  # 업데이트된 노드 가져오기
            if len(category_node.children_ids) >= fanout_limit:
                if self.debug:
                    print(f"정리 후에도 fanout 초과: 기존 노드에 병합")
                # 가장 유사한 기존 대화 노드에 병합
                node_id = await self._merge_to_similar_conversation(conversation, conversation_index, category_node_id, user_input)
                return node_id
        
        # 새로운 대화 노드 생성 (A2, A3, ...)
        conversation_topic = await self._generate_conversation_topic(user_input)
        conversation_summary = await self._generate_conversation_summary(conversation)
        
        conversation_node = MemoryNode(
            topic=conversation_topic,
            summary=conversation_summary,
            parent_id=category_node_id,
            coordinates={"start": conversation_index, "end": conversation_index},
            conversation_indices=[conversation_index]
        )
        
        self.memory_manager.add_node(conversation_node, category_node_id)
        
        # 부모 노드 요약 업데이트
        await self.update_parent_summary(category_node)
        
        if self.debug:
            print(f"대화 노드 추가 완료: '{category_name}'")
        
        return conversation_node.node_id  # 생성된 대화 노드 ID 반환

    async def _handle_multiple_categories(self, conversation, conversation_index, relevant_categories, user_input):
        """다중 카테고리 상황에서 그룹화를 고려합니다."""
        if self.debug:
            print(f"다중 카테고리 그룹화: {len(relevant_categories)}개")
        
        # 그룹화 가능성 평가
        should_group = await self._evaluate_grouping_necessity(relevant_categories, user_input)
        
        if should_group and len(relevant_categories) == 2:
            # AB 그룹 생성 고려
            node_id = await self._create_group_structure(conversation, conversation_index, relevant_categories, user_input)
            return node_id
        else:
            # 가장 관련성 높은 단일 카테고리 선택
            best_category = await self._select_best_category(relevant_categories, user_input)
            node_id = await self._add_to_existing_category(conversation, conversation_index, best_category, user_input)
            return node_id
    
    async def _evaluate_grouping_necessity(self, relevant_categories, user_input):
        """다중 카테고리에 대해 그룹화가 필요한지 평가합니다."""
        if len(relevant_categories) < 2:
            return False
        
        # 간단한 휴리스틱: 2개 카테고리가 모두 관련성이 높으면 그룹화 고려
        return len(relevant_categories) == 2
    
    async def _create_group_structure(self, conversation, conversation_index, relevant_categories, user_input):
        """여러 카테고리를 위한 그룹 구조를 생성합니다."""
        if self.debug:
            print(f"그룹 생성 시작: {len(relevant_categories)}개 카테고리")
        
        # 다중 카테고리가 있을 때는 첫 번째 카테고리에 추가
        if len(relevant_categories) >= 2:
            category_a = relevant_categories[0]
            
            if self.debug:
                print(f"다중 카테고리 감지: {relevant_categories} - 첫 번째 '{category_a}'에 추가")
            
            node_id = await self._add_to_existing_category(conversation, conversation_index, category_a, user_input)
            return node_id
        
        # 단일 카테고리인 경우
        if relevant_categories:
            first_category = relevant_categories[0]
            node_id = await self._add_to_existing_category(conversation, conversation_index, first_category, user_input)
            return node_id
        
        # 관련 카테고리가 없는 경우 새 카테고리 생성
        return await self._create_new_category_structure(conversation, conversation_index, user_input)
    
    """
    async def _process_conversation_with_ai_classification(self, conversation, conversation_index):
        user_input = conversation[0]['content']
        
        if self.debug:
            print(f"AI 분류 시작: '{user_input[:30]}{'...' if len(user_input) > 30 else ''}'")
        
        # 1. 기존 카테고리들과의 관련성 검사 (비동기 병렬)
        existing_categories = await self._get_existing_categories()
        
        if self.debug:
            if existing_categories:
                print(f">>>> [AUX] 기존 카테고리 {len(existing_categories)}개: {list(existing_categories.keys())}")
            else:
                print(f">>>> [AUX] 기존 카테고리 없음")
        
        if existing_categories:
            # 2. 기존 카테고리들과의 관련성을 AI로 판단
            category_relevance = await self._check_category_relevance_async(user_input, existing_categories)
            
            if self.debug:
                relevant_cats = [cat for cat, rel in category_relevance.items() if rel]
                if relevant_cats:
                    print(f"관련 카테고리: {len(relevant_cats)}개")
                else:
                    print("관련 카테고리: 없음")
            
            # 3. 관련된 카테고리가 있으면 해당 카테고리별로 대화 내용 분리
            if any(category_relevance.values()):
                await self._process_multiple_categories(conversation, conversation_index, category_relevance, existing_categories)
            else:
                # 4. 기존 카테고리와 관련 없으면 새 카테고리 생성
                if self.debug:
                    print("새 카테고리 생성 필요")
                await self._create_new_category_and_node(conversation, conversation_index)
        else:
            # 기존 카테고리가 없으면 새 카테고리 생성
            if self.debug:
                print("첫 번째 카테고리 생성")
            await self._create_new_category_and_node(conversation, conversation_index)
        
        if self.debug:
            print("AI 분류 완료")
            
            # 저장 결과 요약
            recent_nodes = []
            for node in self.memory_manager.memory_tree.values():
                if hasattr(node, 'coordinates'):
                    if (node.coordinates.get('start') == conversation_index and 
                        node.coordinates.get('end') == conversation_index):
                        recent_nodes.append(node)
            
            if recent_nodes:
                print(f"생성된 노드: {len(recent_nodes)}개")
    """
    
    async def _get_existing_categories(self):
        """기존에 존재하는 카테고리 노드들을 가져옵니다."""
        categories = {}
        root_node = self.memory_manager.get_root_node()
        
        if not root_node:
            return categories
        
        for child_id in root_node.children_ids:
            child_node = self.memory_manager.get_node(child_id)
            if child_node and child_node.coordinates["start"] == -1:  # 카테고리 노드
                categories[child_node.topic] = {
                    'summary': child_node.summary,
                    'node': child_node
                }
        
        return categories
    
    async def _check_category_relevance_async(self, user_input, categories):
        """기존 카테고리들과 사용자 입력의 관련성을 AI로 비동기 병렬 판단합니다."""
        system_prompt = """사용자의 대화 내용이 특정 카테고리와 관련이 있는지 판단하라.

사용자의 대화를 분석하고, 주어진 카테고리와의 관련성을 정확히 판단하라.
단순히 단어가 포함되어 있다고 관련이 있는 것이 아니라, 실제 대화의 주제와 내용을 고려하라.

반드시 "True" (관련 있음) 또는 "False" (관련 없음)로만 답하라."""
        
        # 각 카테고리별로 개별 쿼리 생성 (병렬 처리용)
        queries = []
        category_names = list(categories.keys())
        
        for name, desc in categories.items():
            prompt = f"""카테고리: {name}
카테고리 설명: {desc}

사용자 대화: {user_input}

위 대화가 '{name}' 카테고리와 관련이 있습니까?"""
            queries.append(prompt)
        
        if self.debug:
            print(f"카테고리 관련성 판단: {len(categories)}개")
        
        try:
            # 여러 API 키를 사용한 병렬 처리
            results = await self.ai_manager.call_ai_async_multiple(
                queries, system_prompt, fine=CATEGORY_RELEVANCE_FINE, label="카테고리 관련성"
            )
            
            # 결과 파싱
            relevance = {}
            for i, result in enumerate(results):
                category_name = category_names[i]
                value = result.strip().lower()
                relevance[category_name] = value in ['true', '참', 'yes']
            
            if self.debug:
                relevant_count = sum(relevance.values())
                print(f"카테고리 관련 결과: {relevant_count}/{len(categories)}개")
            
            return relevance
        except Exception as e:
            print(f"|| 오류: 카테고리 관련성 검사 중 오류: {e}")
            return {cat: False for cat in categories.keys()}
    
    async def _process_multiple_categories(self, conversation, conversation_index, category_relevance, categories):
        """여러 카테고리에 관련된 대화를 적절히 분리하여 처리합니다."""
        user_input = conversation[0]['content']
        ai_response = conversation[1]['content']
        
        # 관련된 카테고리들 필터링
        relevant_categories = [cat for cat, is_relevant in category_relevance.items() if is_relevant]
        
        if self.debug:
            print(f">> [DEBUG] === 다중 카테고리 처리 시작 ===")
            print(f">> [DEBUG] 관련 카테고리 수: {len(relevant_categories)}")
            print(f">> [DEBUG] 관련 카테고리들: {relevant_categories}")
        
        if len(relevant_categories) == 1:
            # 단일 카테고리인 경우
            if self.debug:
                print(f"단일 카테고리: '{relevant_categories[0]}'")
            await self._process_single_category(conversation, conversation_index, relevant_categories[0])
        else:
            # 다중 카테고리인 경우 - 대화 내용을 분리
            if self.debug:
                print(f"다중 카테고리 분리: {len(relevant_categories)}개")
            await self._process_multi_category_conversation(conversation, conversation_index, relevant_categories)
    
    async def _process_single_category(self, conversation, conversation_index, category_name):
        """단일 카테고리에 대한 대화를 처리하고 노드 ID를 반환합니다."""
        if self.debug:
            print(f"'{category_name}' 카테고리 처리 시작")
        
        # 카테고리 노드 찾기
        category_node = None
        for node in self.memory_manager.memory_tree.values():
            if node.topic == category_name and node.coordinates["start"] == -1:
                category_node = node
                break
        
        if not category_node:
            if self.debug:
                print(f"|| 오류: '{category_name}' 카테고리 노드를 찾을 수 없음")
            return None
        
        if self.debug:
            print(f">> 완료: '{category_name}' 카테고리 노드 발견 (ID: {category_node.node_id})")
        
        user_input = conversation[0]['content']
        processed_node_id = None  # 처리된 노드 ID를 저장
        
        if self.debug:
            print(f">> 검색중: 새로운 주제인지 AI로 판단 중...")
        
        # 새로운 주제인지 판단
        if await self._check_for_new_topic_async(category_node, user_input):
            # 새로운 노드 생성
            if self.debug:
                print(f">> 완료: 새로운 주제로 판단 - 새 노드 생성")
            new_node = await self._create_new_node_async(category_node, user_input, conversation, conversation_index)
            # 새로운 방식: conversation_indices에 대화 추가 (대화 노드에만)
            new_node.add_conversation(conversation_index)
            # 부모 카테고리에는 대화 인덱스를 추가하지 않음 (카테고리는 대화를 가지지 않음)
            await self._safe_save_tree()
            processed_node_id = new_node.node_id
            if self.debug:
                print(f"새 노드 생성: '{new_node.topic}' (ID: {processed_node_id})")
        else:
            # 기존 노드에 추가
            if self.debug:
                print("기존 노드에 추가")
            relevant_child = await self._find_relevant_child_node_async(category_node, user_input)
            if relevant_child:
                if self.debug:
                    print(f"대상 노드: '{relevant_child.topic}'")
                await self.update_node_and_parents(relevant_child, conversation, conversation_index)
                processed_node_id = relevant_child.node_id
                if self.debug:
                    print("노드 업데이트 완료")
            else:
                # 관련 하위 노드가 없으면 새로운 노드 생성
                if self.debug:
                    print("새 노드 생성")
                new_node = await self._create_new_node_async(category_node, user_input, conversation, conversation_index)
                # 새로운 방식: conversation_indices에 대화 추가 (대화 노드에만)
                new_node.add_conversation(conversation_index)
                # 부모 카테고리에는 대화 인덱스를 추가하지 않음 (카테고리는 대화를 가지지 않음)
                await self._safe_save_tree()
                processed_node_id = new_node.node_id
                if self.debug:
                    print(f"|| 새 노드 생성 완료:")
                    print(f">> [DEBUG]   노드 ID: {processed_node_id}")
                    print(f">> [DEBUG]   주제: '{new_node.topic}'")
                    print(f">> [DEBUG]   부모: '{category_name}' 카테고리")
                    print(f">> [DEBUG]   대화 인덱스: {new_node.conversation_indices}")
        
        if self.debug:
            print(f">> [DEBUG] === '{category_name}' 카테고리 처리 완료 ===\n")
        
        return processed_node_id  # 처리된 노드 ID 반환
    
    async def _process_multi_category_conversation(self, conversation, conversation_index, relevant_categories):
        """다중 카테고리에 걸친 대화를 분리하여 처리합니다."""
        user_input = conversation[0]['content']
        ai_response = conversation[1]['content']
        
        if self.debug:
            print(f"대화 분리 시작: {len(relevant_categories)}개 카테고리")
        
        # 각 카테고리별로 관련된 대화 내용 분리
        separated_content = await self._separate_conversation_by_categories(user_input, ai_response, relevant_categories)
        
        if self.debug:
            print(f">> [DEBUG] === 분리 결과 ===")
            for category, content_parts in separated_content.items():
                print(f">> [DEBUG] 카테고리 '{category}':")
                print(f">> [DEBUG]   사용자: {content_parts['user']}")
                print(f">> [DEBUG]   AI: {content_parts['ai']}")
        
        # 분리된 내용을 각 카테고리에 병렬로 저장
        tasks = []
        for category, content_parts in separated_content.items():
            # 사용자 입력이 있으면 저장 (AI 응답이 없어도 처리)
            if content_parts['user'] and content_parts['user'].strip():
                if self.debug:
                    print(f"|| 저장중: '{category}' 카테고리에 분리된 대화 저장 중...")
                
                # 분리된 대화로 새로운 conversation 객체 생성 (AI 응답이 빈 문자열이어도 그대로 저장)
                separated_conversation = [
                    {"role": "user", "content": content_parts['user']},
                    {"role": "assistant", "content": content_parts['ai']}
                ]
                # 병렬 처리를 위해 태스크로 추가
                tasks.append(self._process_single_category(separated_conversation, conversation_index, category))
            elif self.debug:
                print(f"|| 건너뜀: '{category}' 카테고리 - 사용자 입력이 비어있음")
        
        # 모든 카테고리를 병렬로 처리
        if tasks:
            await asyncio.gather(*tasks)
    
    async def _create_new_category_and_node(self, conversation, conversation_index):
        """새로운 카테고리와 노드를 생성합니다."""
        user_input = conversation[0]['content']
        
        if self.debug:
            print(f"|| 생성중: 새 카테고리 생성 시작...")
        
        # AI로 새 카테고리명 생성
        category_name = await self._generate_category_name_async(user_input)
        
        if self.debug:
            print(f">> 완료: 생성된 카테고리명: '{category_name}'")
        
        # 새 카테고리 노드 생성
        root_node = self.memory_manager.get_root_node()
        category_node = MemoryNode(
            topic=category_name,
            summary=f"{category_name}에 대한 모든 대화를 관리하는 카테고리입니다.",
            coordinates={"start": -1, "end": -1}
        )
        
        self.memory_manager.add_node(category_node, root_node.node_id)
        
        if self.debug:
            print(f"카테고리 생성: '{category_name}'")
        
        # 카테고리 하위에 실제 대화 노드 생성
        new_node = await self._create_new_node_async(category_node, user_input, conversation, conversation_index)
        # 새로운 방식: conversation_indices에 대화 추가 (대화 노드에만)
        new_node.add_conversation(conversation_index)
        # 부모 카테고리에는 대화 인덱스를 추가하지 않음 (카테고리는 대화를 가지지 않음)
        await self._safe_save_tree()
        
        if self.debug:
            print(f"하위 노드 생성: '{new_node.topic}'")
    
    async def update_node_and_parents(self, node, conversation, conversation_index):
        """노드와 부모 노드들을 업데이트합니다."""
        # 현재 노드 요약 업데이트 (인라인)
        system_prompt = """기존 대화 요약에 새로운 대화 내용을 통합하여 더욱 상세하고 풍부한 요약을 만들어라.
다음 원칙에 따라 요약을 업데이트하라:
- 기존 요약의 핵심 내용을 유지하면서, 새로운 대화의 정보를 빠짐없이 추가하라.
- 사용자 발언과 AI 응답의 세부사항을 모두 포함하여 전체 대화의 흐름과 맥락이 명확히 드러나게 하라.
- 단순히 내용을 더하는 것을 넘어, 두 대화가 어떻게 연결되는지 자연스럽게 서술하라.
- 최종 요약은 나중에 이 내용만 봐도 전체 대화의 흐름을 완벽하게 이해할 수 있을 정도로 상세해야 한다."""
        
        user_content = conversation[0]['content']
        ai_content = conversation[1]['content']
        
        # AI 응답 유무에 따라 다른 프롬프트 생성
        if ai_content.strip():  # AI 응답이 있는 경우
            prompt = f"""기존 요약: {node.summary}

새로운 대화:
사용자: {user_content}
AI: {ai_content}

기존 요약에 새로운 대화를 통합하여 업데이트된 요약을 작성해주세요."""
        else:  # AI 응답이 없는 경우 (record 모드)
            prompt = f"""기존 요약: {node.summary}

새로운 사용자 발언:
사용자: {user_content}

기존 요약에 새로운 사용자 정보를 통합하여 업데이트된 요약을 작성해주세요."""
        
        new_summary = await self.ai_manager.call_ai_async_single(prompt, system_prompt)
        
        # 대화 노드에만 conversation_indices 추가 (카테고리 노드는 제외)
        if node.coordinates["start"] != -1:  # 대화 노드인 경우만
            node.add_conversation(conversation_index)
        
        self.memory_manager.update_node(
            node.node_id,
            summary=new_summary
        )
        
        # 부모 카테고리에는 대화 인덱스를 추가하지 않음 (카테고리는 대화를 가지지 않음)
        if node.parent_id:
            parent_node = self.memory_manager.get_node(node.parent_id)
            if parent_node:
                # 부모 노드 요약 업데이트
                await self.update_parent_summary(parent_node, node)
        
        # 부모 노드들 재귀적으로 업데이트
        if node.parent_id:
            parent_node = self.memory_manager.get_node(node.parent_id)
            if parent_node:
                await self.update_parent_summary(parent_node, node)
    
    async def update_summary(self, current_summary, new_conversation):
        """기존 요약에 새로운 대화를 통합합니다."""
        system_prompt = """기존 대화 요약에 새로운 대화 내용을 통합하여 더욱 상세하고 풍부한 요약을 만들어라.
다음 원칙에 따라 요약을 업데이트하라:
- 기존 요약의 핵심 내용을 유지하면서, 새로운 대화의 정보를 빠짐없이 추가하라.
- 사용자 발언과 AI 응답의 세부사항을 모두 포함하여 전체 대화의 흐름과 맥락이 명확히 드러나게 하라.
- 단순히 내용을 더하는 것을 넘어, 두 대화가 어떻게 연결되는지 자연스럽게 서술하라.
- 최종 요약은 나중에 이 내용만 봐도 전체 대화의 흐름을 완벽하게 이해할 수 있을 정도로 상세해야 한다."""
        
        user_content = new_conversation[0]['content']
        ai_content = new_conversation[1]['content']
        
        prompt = f"""기존 요약: {current_summary}

새로운 대화:
사용자: {user_content}
AI: {ai_content}

기존 요약에 새로운 대화를 통합하여 업데이트된 요약을 작성해주세요."""
        
        return await self.ai_manager.call_ai_async_single(prompt, system_prompt)
    
    async def update_parent_summary(self, parent_node, child_node=None):
        """부모 노드의 요약을 자식 노드 변경사항에 맞춰 업데이트합니다."""
        # 모든 자식 노드의 요약을 수집
        child_summaries = []
        for child_id in parent_node.children_ids:
            child = self.memory_manager.get_node(child_id)
            if child and child.summary:
                child_summaries.append(child.summary)
        
        if child_summaries:
            # 자식 요약들을 결합하여 부모 노드 요약 업데이트
            combined_summary = await self.combine_child_summaries(child_summaries, parent_node.topic)
            self.memory_manager.update_node(parent_node.node_id, summary=combined_summary)
            
            if self.debug:
                print(f"부모 노드 '{parent_node.topic}' 요약 업데이트 완료")
        
        # 재귀적으로 상위 부모도 업데이트 (ROOT 제외)
        if parent_node.parent_id and parent_node.topic != "ROOT":
            grandparent_node = self.memory_manager.get_node(parent_node.parent_id)
            if grandparent_node:
                await self.update_parent_summary(grandparent_node, parent_node)
    
    def update_node_coordinates(self, node_id, start_index, end_index):
        """노드의 좌표를 업데이트합니다."""
        self.memory_manager.update_node(
            node_id,
            coordinates={"start": start_index, "end": end_index}
        )

    # === 동적 트리 구조 관리 유틸리티 메서드들 ===
    
    async def _evaluate_category_relevance(self, user_input, existing_categories):
        """기존 카테고리들과 사용자 입력의 관련성을 평가합니다."""
        if not existing_categories:
            return {}
        
        relevant_categories = {}
        
        # 병렬로 각 카테고리별 관련성 AI 판단
        tasks = []
        category_items = list(existing_categories.items())
        
        for category_name, category_info in category_items:
            task = self._check_category_relevance(user_input, category_name, category_info['summary'])
            tasks.append((category_name, category_info, task))
        
        # 병렬 실행
        results = await asyncio.gather(*[task for _, _, task in tasks], return_exceptions=True)
        
        # 결과 처리
        for i, (category_name, category_info, _) in enumerate(tasks):
            try:
                is_relevant = results[i]
                if not isinstance(is_relevant, Exception) and is_relevant:
                    relevant_categories[category_name] = category_info
            except Exception as e:
                if self.debug:
                    print(f">>>> [ERROR] 카테고리 {category_name} 관련성 판단 오류: {e}")
        
        return relevant_categories
    
    async def _check_category_relevance(self, user_input, category_name, category_summary):
        """특정 카테고리와 사용자 입력의 관련성을 판단합니다."""
        system_prompt = """사용자의 입력이 주어진 카테고리와 구체적으로 관련이 있는지 엄격하게 판단하라.

판단 기준:
1. 주제가 정확히 일치하거나 매우 밀접한 하위 주제인가?
2. 단순히 같은 분야(예: 과학)라는 이유만으로는 관련이 없다고 판단한다.
3. 구체적인 주제의 연관성이 있어야 한다.

예시:
- "지구 위성" 카테고리에 "달의 뒷면" 질문 → True (밀접한 관련)
- "지구 위성" 카테고리에 "물의 화학식" 질문 → False (과학이지만 별개 주제)
- "지구 위성" 카테고리에 "태양계 행성" 질문 → False (천문학이지만 위성과 직접 관련 없음)

관련이 있으면 "True", 없으면 "False"로만 답하라."""
        
        query = f"""사용자 입력: {user_input}
카테고리 이름: {category_name}
카테고리 요약: {category_summary}

위 사용자 입력이 해당 카테고리와 구체적으로 관련이 있는가?"""
        
        try:
            result = await self.ai_manager.call_ai_async_single(query, system_prompt)
            return result.strip().lower() == 'true'
        except Exception as e:
            if self.debug:
                print(f">>>> [ERROR] 카테고리 관련성 판단 오류: {e}")
            return False
    
    async def _generate_category_name(self, user_input):
        """사용자 입력을 기반으로 카테고리명을 생성합니다."""
        system_prompt = """사용자 입력을 분석하여 구체적이고 명확한 카테고리명을 생성하라.

원칙:
- 2-8자의 간결한 한국어로 작성
- 너무 포괄적이지 않고 구체적인 주제 표현
- 단순히 "과학", "학문" 같은 광범위한 용어 지양
- 구체적인 세부 분야명 선호

예시:
- "지구의 위성은?" → "천체 물리" 또는 "지구 위성"
- "물의 화학식은?" → "화학 기초" 또는 "분자 구조"  
- "피타고라스 정리는?" → "기하학" 또는 "수학 정리"
- "내 나이는 19살" → "개인 정보" 또는 "자기소개"

오직 카테고리명만 답변하라."""
        
        try:
            result = await self.ai_manager.call_ai_async_single(user_input, system_prompt)
            category_name = result.strip()[:20]  # 최대 20자 제한
            
            # 너무 포괄적인 이름들을 더 구체적으로 변경
            if category_name in ["과학", "학문", "지식", "공부"]:
                # 입력에서 키워드 추출하여 더 구체적으로 만들기
                if "물" in user_input or "화학" in user_input:
                    category_name = "화학 기초"
                elif "지구" in user_input or "달" in user_input or "태양" in user_input:
                    category_name = "천문학"
                elif "수학" in user_input or "정리" in user_input:
                    category_name = "수학"
                elif "빛" in user_input or "광합성" in user_input:
                    category_name = "생물학"
                else:
                    category_name = "과학 기초"
            
            return category_name
        except Exception as e:
            if self.debug:
                print(f">>>> [ERROR] 카테고리명 생성 오류: {e}")
            return "기타"
    
    async def _generate_category_summary(self, user_input):
        """사용자 입력을 기반으로 카테고리 요약을 생성합니다."""
        system_prompt = """사용자 입력을 분석하여 해당 카테고리의 요약을 생성하라.
- 1-2문장의 간결한 설명
- 카테고리가 포함할 내용의 범위를 명확히 표현
- 예: "음식과 요리에 관한 모든 대화", "개인 정보와 배경에 관한 내용" 등"""
        
        try:
            result = await self.ai_manager.call_ai_async_single(user_input, system_prompt)
            return result.strip()[:100]  # 최대 100자 제한
        except Exception as e:
            if self.debug:
                print(f">>>> [ERROR] 카테고리 요약 생성 오류: {e}")
            return "다양한 주제에 대한 대화"
    
    async def _find_category_node_id(self, category_name):
        """카테고리명으로 노드 ID를 찾습니다."""
        for node_id, node in self.memory_manager.memory_tree.items():
            if node.topic == category_name and node.coordinates.get("start") == -1:
                return node_id
        return None
    
    async def _select_best_category(self, relevant_categories, user_input):
        """여러 관련 카테고리 중 가장 적합한 것을 선택합니다."""
        if len(relevant_categories) == 1:
            return relevant_categories[0]
        
        # AI를 통한 최적 카테고리 선택
        system_prompt = """사용자 입력에 가장 적합한 카테고리를 선택하라.
카테고리명만 정확히 답하라."""
        
        categories_text = "\n".join([f"- {name}" for name in relevant_categories])
        query = f"""사용자 입력: {user_input}
가능한 카테고리들:
{categories_text}"""
        
        try:
            result = await self.ai_manager.call_ai_async_single(query, system_prompt)
            selected = result.strip()
            if selected in relevant_categories:
                return selected
            else:
                # AI 응답이 부정확한 경우 첫 번째 카테고리 선택
                return relevant_categories[0]
        except Exception as e:
            if self.debug:
                print(f">>>> [ERROR] 최적 카테고리 선택 오류: {e}")
            return relevant_categories[0]

    # === 동적 트리 구조 관리 메서드들 ===
    
    def _can_add_child_node(self, parent_id):
        """부모 노드에 자식을 추가할 수 있는지 깊이 제한을 확인합니다."""
        return self.memory_manager.can_insert_child(parent_id, self.max_depth)

        # 3. 관련성 순으로 정렬
        relevant_nodes.sort(key=lambda x: x['relevance'], reverse=True)
        
    async def search_relevant_memories(self, user_input):
        """사용자 입력과 관련된 기억을 계층적으로 검색합니다."""
        if self.debug:
            print(f"기억 검색 시작: '{user_input[:30]}{'...' if len(user_input) > 30 else ''}'")

        if not self.memory_manager.memory_tree:
            return ""

        try:
            relevant_conversations = await self._hierarchical_search(user_input)

            if self.short_debug:
                if relevant_conversations:
                    print(f"검색 결과: {len(relevant_conversations)}개 대화")
                else:
                    print("검색 결과: 없음")

            if relevant_conversations:
                limit = len(relevant_conversations) if self.top_search_n == 0 else self.top_search_n
                result_parts = []
                for conv_data in relevant_conversations[:limit]:
                    conv_idx = conv_data['index']
                    conv = conv_data['conversation']
                    
                    conversation_text = f"======{conv_idx}번 대화======"
                    for msg in conv:
                        role = "사용자" if msg.get('role') == 'user' else "AI"
                        content = msg.get('content', '')
                        conversation_text += f"\n{role}: {content}"
                    conversation_text += "\n=================="
                    result_parts.append(conversation_text)
                
                result = "\n\n".join(result_parts)
            else:
                result = ""
            
            if self.debug:
                if relevant_conversations:
                    limit = len(relevant_conversations) if self.top_search_n == 0 else min(self.top_search_n, len(relevant_conversations))
                    # 간단한 관련 노드 좌표 출력
                    node_list = []
                    for conv_data in relevant_conversations[:limit]:
                        conv_idx = conv_data['index']
                        node_topic = conv_data.get('node_topic', '알 수 없음')
                        node_list.append(f"대화 {conv_idx}번 ({node_topic})")
                    print(f">> [SEARCH] 관련 기억 노드: {', '.join(node_list)}")
                else:
                    print(">> [SEARCH] 관련 기억 없음")
            
            return result
        except Exception as e:
            if self.debug:
                import traceback
                print(f"!!!!!!!!!!! search_relevant_memories에서 오류 발생: {e}")
                traceback.print_exc()
            return "" # 오류 발생 시 빈 문자열 반환

    async def _search_within_candidates(self, user_input, candidate_nodes):
        """주어진 후보 노드들 내에서 관련 대화를 찾습니다."""
        all_conversations = []
        processed_indices = set()

        for node in candidate_nodes:
            # 리프 노드(대화가 있는 노드)만 처리
            if hasattr(node, 'conversation_indices') and node.conversation_indices:
                for conv_idx in node.conversation_indices:
                    if conv_idx not in processed_indices:
                        all_conversations.append({
                            'index': conv_idx,
                            'node_topic': node.topic,
                            'node_summary': node.summary
                        })
                        processed_indices.add(conv_idx)
        
        if not all_conversations:
            return []

        # AI를 통해 대화들의 관련성 평가 (병렬)
        relevance_map = await self._evaluate_conversations_relevance(user_input, all_conversations)

        # 관련 있는 대화만 필터링 및 실제 내용 로드
        final_conversations = []
        all_memory_cache = self.memory_manager.data_manager.load_json(ALL_MEMORY)
        for conv_info in all_conversations:
            if relevance_map.get(conv_info['index']):
                conv_idx = conv_info['index']
                if conv_idx < len(all_memory_cache):
                    final_conversations.append({
                        'index': conv_idx,
                        'conversation': all_memory_cache[conv_idx],
                        'node_topic': conv_info['node_topic']
                    })
        
        return sorted(final_conversations, key=lambda x: x['index'])

    async def _evaluate_conversations_relevance(self, user_input, conversation_infos):
        """여러 대화의 요약을 보고 사용자 입력과의 관련성을 병렬로 평가합니다."""
        queries = []
        system_prompt = """당신은 사용자의 질문 의도를 파악하고, 그 의도와 과거 대화 기록의 관련성을 판단하는 전문가입니다.
"True" 또는 "False"로만 답해야 합니다."""
        
        for info in conversation_infos:
            prompt = f"""# 목표: 사용자의 질문과 과거 대화 기록의 관련성을 판단하세요.

# 1. 사용자 질문 분석
사용자 질문: "{user_input}"
이 질문의 핵심 의도는 사용자가 과거에 자신에 대해 언급했던 '개인 정보' 또는 '자신의 생각/주장'을 찾는 것입니다.

# 2. 과거 대화 내용
- 대화 주제: {info['node_topic']}
- 대화 요약: {info['node_summary']}

# 3. 관련성 판단
'과거 대화 내용'이 사용자의 '개인 정보'나 '생각/주장'을 포함하고 있습니까?
판단 (True/False):"""
            queries.append(prompt)

        results = await self.ai_manager.call_ai_async_multiple(queries, system_prompt, label="대화 관련성 평가")

        relevance_map = {}
        for i, result in enumerate(results):
            conv_index = conversation_infos[i]['index']
            # AI가 생성한 불필요한 텍스트를 제거하고 True/False만 정확히 파싱
            relevance_map[conv_index] = 'true' in result.strip().lower()
        
        return relevance_map
        
    async def _hierarchical_search(self, user_input):
        """계층적 심층 탐색을 수행하여 관련 대화를 찾습니다. (수정된 로직)"""
        root_node = self.memory_manager.get_root_node()
        if not root_node or not root_node.children_ids:
            return []

        final_conversations = []
        processed_conversation_indices = set()

        # 탐색 큐: (node_id, depth) 튜플을 저장
        queue = [(child_id, 1) for child_id in root_node.children_ids]
        
        if self.debug:
            print(f"계층 탐색 시작 ({len(queue)}개 카테고리)")

        current_depth = 0
        while queue:
            # 현재 깊이의 노드들만 추출
            nodes_at_current_depth = [item for item in queue if item[1] == current_depth + 1]
            if not nodes_at_current_depth:
                break
            
            current_depth += 1
            # 다음 깊이로 넘어갈 노드들을 큐에서 제거
            queue = [item for item in queue if item[1] > current_depth]

            nodes_to_evaluate = [self.memory_manager.get_node(node_id) for node_id, _ in nodes_at_current_depth if self.memory_manager.get_node(node_id)]
            
            if not nodes_to_evaluate:
                continue

            if self.debug:
                print(f"깊이 {current_depth}: {len(nodes_to_evaluate)}개 노드 평가")

            relevant_nodes = await self._evaluate_nodes_relevance(user_input, nodes_to_evaluate)
            
            if self.debug:
                print(f"관련 노드: {len(relevant_nodes)}개")

            for node in relevant_nodes:
                # 자식 노드가 있으면 다음 탐색 큐에 추가 (부모 노드의 역할)
                if node.children_ids:
                    for child_id in node.children_ids:
                        child_node = self.memory_manager.get_node(child_id)
                        if child_node:
                            queue.append((child_id, current_depth + 1))
                # 자식 노드가 없는 리프 노드일 경우에만 대화 수집
                elif hasattr(node, 'conversation_indices') and node.conversation_indices:
                    if self.debug:
                        print(f"리프 노드: {len(node.conversation_indices)}개 대화")
                    for conv_idx in node.conversation_indices:
                        if conv_idx not in processed_conversation_indices:
                            try:
                                all_memory = self.memory_manager.data_manager.load_json(ALL_MEMORY)
                                if conv_idx < len(all_memory):
                                    conv = all_memory[conv_idx]
                                    final_conversations.append({
                                        'index': conv_idx,
                                        'conversation': conv,
                                        'node_topic': node.topic
                                    })
                                    processed_conversation_indices.add(conv_idx)
                            except Exception as e:
                                if self.debug:
                                    print(f"대화 로드 실패: {conv_idx}")
        
        if self.debug:
            print(f"\n>> [SEARCH-DEEP] 심층 탐색 완료. 총 {len(final_conversations)}개 관련 대화 발견.")
        
        # 중복 제거 및 정렬
        unique_conversations = {conv['index']: conv for conv in final_conversations}
        sorted_conversations = sorted(unique_conversations.values(), key=lambda x: x['index'])
        
        return sorted_conversations
    
    async def _evaluate_nodes_relevance(self, user_input, nodes):
        """노드들의 관련성을 병렬로 평가합니다."""
        if not nodes:
            return []
        
        # 병렬 평가를 위한 쿼리 생성
        queries = []
        node_info = []
        
        for node in nodes:
            query = f"""사용자 질문: "{user_input}"\n\n노드 정보:
주제: {node.topic}
요약: {node.summary}

이 노드가 사용자 질문과 관련이 있습니까? 관련이 있다면 "True", 없다면 "False"로 답하세요."""
            queries.append(query)
            node_info.append({
                'node': node,
                'topic': node.topic
            })
        
        system_prompt = """노드의 주제와 요약을 보고 사용자 질문과의 관련성을 판단하세요.
관련성이 있으면 "True", 없으면 "False"로만 답하세요.
부분적으로라도 관련이 있다면 True로 판단하세요."""
        
        if self.debug:
            # 간단한 노드 평가 시작 메시지
            print(f"노드 평가 시작 ({len(queries)}개)")
        
        # 병렬 AI 호출
        results = await self.ai_manager.call_ai_async_multiple(queries, system_prompt, label="노드 관련성 평가")
        
        # 결과 처리
        relevant_nodes = []
        for i, result in enumerate(results):
            is_relevant = result.strip().lower() in ['true', '참', 'yes']
            if is_relevant:
                relevant_nodes.append(node_info[i]['node'])
        
        if self.debug:
            # 간단한 결과 메시지
            for i, result in enumerate(results):
                node_topic = node_info[i]['topic']
                is_relevant = result.strip().lower() in ['true', '참', 'yes']
                print(f"'{node_topic}' 노드: {'True' if is_relevant else 'False'}")
        
        return relevant_nodes
    
    async def _generate_conversation_topic(self, user_input):
        """사용자 입력을 기반으로 대화의 구체적인 주제를 생성합니다."""
        system_prompt = """사용자의 발언을 분석하여 구체적이고 명확한 대화 주제를 생성하라.
주제는 간결하고 정확하게 핵심 내용을 담아야 합니다.
예시:
- "내 이름은 김철수이고 수학을 좋아한다" → "개인 소개"
- "사과의 영양소에 대해 궁금하다" → "사과 영양소"
- "양자역학의 불확정성 원리가 흥미롭다" → "양자역학 불확정성"
한국어로 2-4단어 정도의 간결한 주제를 생성하라."""
        
        try:
            prompt = f"사용자 발언: '{user_input}'"
            result = await self.ai_manager.call_ai_async_single(prompt, system_prompt)
            return result.strip()
        except Exception as e:
            if self.debug:
                print(f">>>> [ERROR] 대화 주제 생성 오류: {e}")
            # 기본값으로 입력의 처음 몇 단어 사용
            words = user_input.split()[:3]
            return " ".join(words) if words else "일반 대화"
    
    async def _generate_conversation_summary(self, conversation):
        """대화 내용을 기반으로 요약을 생성합니다."""
        system_prompt = """주어진 대화를 분석하여 핵심 내용을 요약하라.
중요한 정보는 유지하면서 1-2문장으로 간결하게 작성하라.
대화의 주요 주제와 결론을 포함해야 합니다."""
        
        try:
            user_content = conversation[0]['content']
            ai_content = conversation[1]['content'] if len(conversation) > 1 else ""
            
            prompt = f"사용자: {user_content}\nAI: {ai_content}"
            result = await self.ai_manager.call_ai_async_single(prompt, system_prompt)
            return result.strip()
        except Exception as e:
            if self.debug:
                print(f">>>> [ERROR] 대화 요약 생성 오류: {e}")
            return f"대화 요약: {conversation[0]['content'][:50]}..."
    
    async def _merge_to_similar_conversation(self, conversation, conversation_index, category_node_id, user_input):
        """K-거리 기반 유사도 검색으로 유사한 대화가 있는 노드에 병합합니다."""
        category_node = self.memory_manager.get_node(category_node_id)
        if not category_node:
            return None
        
        # 새로운 대화 노드 생성 (임시)
        temp_topic = await self._generate_conversation_topic(user_input)
        temp_summary = await self._generate_conversation_summary(conversation)
        
        temp_node = MemoryNode(
            topic=temp_topic,
            summary=temp_summary,
            parent_id=category_node_id,
            coordinates={"start": conversation_index, "end": conversation_index},
            conversation_indices=[conversation_index]
        )
        
        # K-거리 이내 노드들과의 유사도 비교
        similar_nodes = await self.k_distance_search.find_similar_nodes(temp_node)
        
        # 가장 유사한 노드 찾기 (유사도 0.7 이상)
        best_match = None
        best_similarity = 0.0
        
        for node, similarity in similar_nodes:
            if similarity >= 0.7 and node.parent_id == category_node_id:  # 같은 카테고리 내에서만
                if similarity > best_similarity:
                    best_similarity = similarity
                    best_match = node
        
        if best_match:
            # 유사한 노드가 있으면 병합
            if self.debug:
                print(f"K-거리 검색으로 유사 노드 발견: '{best_match.topic}' (유사도: {best_similarity:.2f})")
            
            # 대화 노드에만 conversation_indices 추가
            if best_match.coordinates["start"] != -1:  # 대화 노드인 경우만
                best_match.conversation_indices.append(conversation_index)
            
            await self._safe_save_tree()
            # 부모 노드 요약 업데이트
            await self.update_parent_summary(category_node)
            return best_match.node_id
        
        # 유사한 노드가 없으면 새로운 노드 생성
        if self.debug:
            print("K-거리 검색으로 유사 노드 없음, 새 노드 생성")
        
        self.memory_manager.add_node(temp_node, category_node_id)
        # 부모 노드 요약 업데이트
        await self.update_parent_summary(category_node)
        return temp_node.node_id
    
    async def _is_similar_topic_ai(self, user_input, existing_topic):
        """AI를 사용하여 두 주제가 유사한지 판단합니다."""
        system_prompt = """사용자 입력과 기존 주제가 같은 범주나 유사한 내용을 다루는지 판단하세요.
유사하다면 "True", 다르다면 "False"로만 답하세요."""
        
        prompt = f"""사용자 입력: "{user_input}"
기존 주제: "{existing_topic}"

이 둘이 유사한 주제를 다루고 있습니까?"""
        
        try:
            result = await self.ai_manager.call_ai_async_single(prompt, system_prompt)
            return result.strip().lower() in ['true', '참', 'yes']
        except Exception as e:
            if self.debug:
                print(f">>>> [ERROR] AI 주제 유사도 판단 오류: {e}")
            return False
    
    def _find_category_node_by_name(self, category_name):
        """카테고리 이름으로 노드를 찾습니다."""
        root_node = self.memory_manager.get_root_node()
        if not root_node:
            return None
        
        for child_id in root_node.children_ids:
            child_node = self.memory_manager.get_node(child_id)
            if child_node and child_node.topic == category_name:
                return child_node
        return None
    
    def _can_create_group_above(self, node_id):
        """노드 위에 그룹을 생성할 수 있는지 깊이를 검증합니다."""
        node_depth = self.memory_manager.get_node_depth(node_id)
        # 그룹 삽입 시 전체 서브트리가 +1 깊이 증가
        max_subtree_depth = self.memory_manager.get_subtree_max_depth(node_id)
        return max_subtree_depth + 1 <= self.max_depth
    
    async def _select_target_category_in_group(self, user_input, categories):
        """그룹 내에서 대화를 추가할 적절한 카테고리를 선택합니다."""
        system_prompt = """사용자 입력이 주어진 카테고리들 중 어느 것에 더 적합한지 판단하라.
첫 번째 카테고리명만 답변하라."""
        
        prompt = f"""사용자 입력: {user_input}

카테고리 옵션:
1. {categories[0]}
2. {categories[1]}

더 적합한 카테고리는?"""
        
        try:
            result = await self.ai_manager.call_ai_async_single(prompt, system_prompt)
            selected = result.strip()
            
            # 결과가 카테고리 중 하나와 일치하는지 확인
            for category in categories:
                if category in selected:
                    return category
            
            # 일치하지 않으면 첫 번째 반환
            return categories[0]
        except Exception as e:
            if self.debug:
                print(f">>>> [ERROR] 카테고리 선택 오류: {e}")
            return categories[0]
    
    async def _handle_depth_limit_with_merge(self, conversation, conversation_index, relevant_categories, user_input):
        """깊이 제한으로 그룹 생성이 불가능할 때 리프 병합을 시도합니다."""
        if self.debug:
            print(f">>>> [MERGE] 깊이 제한으로 리프 병합 시도")
        
        # 첫 번째 카테고리의 가장 유사한 리프 노드 찾기
        category_name = relevant_categories[0]
        category_node = self._find_category_node_by_name(category_name)
        
        if category_node:
            # 가장 유사한 기존 리프 찾기
            most_similar_leaf = await self._find_most_similar_leaf(category_node, user_input)
            
            if most_similar_leaf:
                # 기존 리프에 대화 인덱스 추가 (병합)
                if not hasattr(most_similar_leaf, 'conversation_indices'):
                    most_similar_leaf.conversation_indices = []
                
                # 대화 노드에만 conversation_indices 추가
                if most_similar_leaf.coordinates["start"] != -1:  # 대화 노드인 경우만
                    most_similar_leaf.conversation_indices.append(conversation_index)
                
                # 요약 업데이트
                most_similar_leaf.summary = await self._update_summary_with_merge(
                    most_similar_leaf.summary, conversation[0]['content'], conversation[1]['content']
                )
                
                # 부모 노드 요약 업데이트
                await self.update_parent_summary(category_node)
                
                if self.debug:
                    print(f">>>> [MERGE] 리프 '{most_similar_leaf.topic}'에 대화 병합 완료")
                return most_similar_leaf.node_id  # 병합된 노드 ID 반환
            else:
                # 유사한 리프가 없으면 새 리프 생성 (깊이 허용 시)
                if self.memory_manager.can_insert_child(category_node.node_id, self.max_depth):
                    node_id = await self._add_to_existing_category(conversation, conversation_index, category_name, user_input)
                    return node_id  # 새로 생성된 노드 ID 반환
        
        return None  # 병합이나 생성이 실패한 경우
    
    async def _find_most_similar_leaf(self, category_node, user_input):
        """카테고리 내에서 가장 유사한 리프 노드를 AI 기반으로 찾습니다."""
        best_leaf = None
        
        leaf_nodes = []
        for child_id in category_node.children_ids:
            child_node = self.memory_manager.get_node(child_id)
            if child_node and child_node.coordinates.get("start", -1) >= 0:  # 리프 노드
                leaf_nodes.append(child_node)
        
        if not leaf_nodes:
            return None
        
        if len(leaf_nodes) == 1:
            return leaf_nodes[0]
        
        # AI를 사용한 병렬 유사도 판단
        queries = []
        for node in leaf_nodes:
            query = f"""사용자 입력: "{user_input}"

기존 리프 노드:
주제: {node.topic}
요약: {node.summary}

이 리프 노드가 사용자 입력과 유사한 주제를 다루고 있습니까? 
유사하다면 "True", 아니라면 "False"로 답하세요."""
            queries.append(query)
        
        system_prompt = """리프 노드의 주제와 요약을 보고 사용자 입력과의 주제 유사성을 판단하세요.
같은 카테고리 내에서 병합 가능할 정도로 유사하면 "True", 다른 주제라면 "False"로 답하세요."""
        
        # 병렬 AI 호출
        results = await self.ai_manager.call_ai_async_multiple(
            queries, system_prompt
        )
        
        # 가장 유사한 노드 선택 (첫 번째 True 결과)
        for i, result in enumerate(results):
            if result.strip().lower() in ['true', '참', 'yes']:
                best_leaf = leaf_nodes[i]
                break
        
        return best_leaf
    
    async def _calculate_similarity_ai(self, text1, text2):
        """AI를 사용하여 두 텍스트의 유사도를 판단합니다."""
        system_prompt = """두 텍스트가 유사한 주제나 내용을 다루고 있는지 판단하세요.
유사하다면 "True", 다르다면 "False"로만 답하세요."""
        
        prompt = f"""텍스트 1: "{text1}"
텍스트 2: "{text2}"

이 두 텍스트가 유사한 주제를 다루고 있습니까?"""
        
        try:
            result = await self.ai_manager.call_ai_async_single(prompt, system_prompt)
            return result.strip().lower() in ['true', '참', 'yes']
        except Exception as e:
            if self.debug:
                print(f">>>> [ERROR] AI 유사도 판단 오류: {e}")
            return False
    
    async def _update_summary_with_merge(self, current_summary, new_user_content, new_ai_content):
        """병합 시 요약을 업데이트합니다."""
        system_prompt = """기존 요약에 새로운 대화를 통합하여 업데이트된 요약을 작성해주세요.
"여러 대화가 포함됨"이라는 표현을 자연스럽게 포함해주세요."""
        
        prompt = f"""기존 요약: {current_summary}

새로운 대화:
사용자: {new_user_content}
AI: {new_ai_content}"""
        
        try:
            result = await self.ai_manager.call_ai_async_single(prompt, system_prompt)
            return result.strip()
        except Exception as e:
            if self.debug:
                print(f">>>> [ERROR] 병합 요약 업데이트 오류: {e}")
            return f"{current_summary} (추가 대화 포함)"

    # ===== 새로운 노드 업데이트 시스템 =====

    async def update_node_summary_with_ai(self, node_id: str, conversation_index: int):
        """
        AI를 사용하여 단일 노드의 요약을 생성/업데이트합니다.
        새로운 대화가 추가되었을 때 해당 노드의 요약을 업데이트합니다.
        """
        node = self.memory_manager.get_node(node_id)
        if not node:
            return

        # 해당 노드가 포함하는 모든 대화 수집
        all_conversations = self._collect_node_conversations(node_id)

        if not all_conversations:
            return

        # AI를 사용하여 새로운 요약 생성
        system_prompt = """이 노드에 포함된 모든 대화 내용을 바탕으로,
        노드의 주제를 잘 대표하는 간결한 요약을 1-2문장으로 작성해주세요."""

        conversations_text = "\n\n".join([
            f"사용자: {conv[0]['content']}\nAI: {conv[1]['content']}"
            for conv in all_conversations
        ])

        prompt = f"""대화 내용들:
{conversations_text}

요약:"""

        try:
            new_summary = await self.ai_manager.call_ai_async_single(prompt, system_prompt)
            node.summary = new_summary.strip()
            if self.debug:
                print(f"노드 '{node.topic}' 요약 업데이트 완료")
        except Exception as e:
            if self.debug:
                print(f">>>> [ERROR] 노드 요약 생성 오류: {e}")

    def _collect_node_conversations(self, node_id: str) -> list:
        """노드와 그 자식 노드들이 포함하는 모든 대화를 수집합니다."""
        from .DataManager import DataManager
        all_conversations = []

        # all_memory.json 파일에서 모든 대화를 로드
        all_memory_data = DataManager.load_json(ALL_MEMORY)

        def collect_recursive(current_node_id: str):
            node = self.memory_manager.get_node(current_node_id)
            if not node:
                return

            # 현재 노드의 대화들 추가
            for conv_idx in node.conversation_indices:
                if 0 <= conv_idx < len(all_memory_data):
                    conversation = all_memory_data[conv_idx]
                    if conversation:
                        all_conversations.append(conversation)

            # 자식 노드들의 대화들 추가
            for child_id in node.children_ids:
                collect_recursive(child_id)

        collect_recursive(node_id)
        return all_conversations

    async def update_parent_nodes_simple(self, start_node_id: str):
        """
        부모 노드들을 자식 노드들의 요약을 결합하는 방식으로 업데이트합니다.
        AI 호출 없이 간단한 텍스트 결합으로 처리합니다.
        """
        current_node = self.memory_manager.get_node(start_node_id)

        while current_node and current_node.node_id != "ROOT":
            # 현재 노드의 자식 노드들의 요약을 결합
            child_summaries = []
            for child_id in current_node.children_ids:
                child_node = self.memory_manager.get_node(child_id)
                if child_node and child_node.summary:
                    child_summaries.append(child_node.summary)

            if child_summaries:
                # 자식 요약들을 결합하여 부모 노드 요약 업데이트
                combined_summary = await self.combine_child_summaries(child_summaries, current_node.topic)
                
                # 노드 업데이트를 통해 변경사항을 메모리 매니저에 저장
                self.memory_manager.update_node(current_node.node_id, summary=combined_summary)

                if self.debug:
                    print(f"부모 노드 '{current_node.topic}' 요약 업데이트 완료")

            # 부모 노드로 이동
            if current_node.parent_id:
                current_node = self.memory_manager.get_node(current_node.parent_id)
            else:
                break

    async def combine_child_summaries(self, child_summaries: list, parent_topic: str) -> str:
        """
        자식 노드들의 요약을 결합하여 부모 노드의 요약을 생성합니다.
        모든 자식 노드의 요약을 그대로 결합하여 최대한 자세한 요약을 생성합니다.
        결합된 요약이 너무 길면 AI를 사용하여 요약합니다.
        """
        if not child_summaries:
            return f"{parent_topic}에 대한 내용들입니다."

        # 모든 자식 요약을 그대로 결합
        valid_summaries = [summary.strip() for summary in child_summaries if summary.strip()]

        if not valid_summaries:
            return f"{parent_topic}에 대한 내용들입니다."

        # 결합된 요약 생성 - 모든 요약을 포함
        if len(valid_summaries) == 1:
            combined = valid_summaries[0]
        elif len(valid_summaries) == 2:
            combined = f"{valid_summaries[0]} 및 {valid_summaries[1]}"
        else:
            # 모든 요약을 순서대로 결합
            combined = " · ".join(valid_summaries)

        # 결합된 요약의 길이 확인 및 AI 요약 적용
        from config import get_config_value
        max_length = get_config_value('max_summary_length')

        if len(combined) > max_length:
            print(f"📝 [요약 시작] 부모 노드 요약이 {len(combined)}자 > {max_length}자 제한을 초과하여 AI 요약을 시작합니다...")

            # AI를 사용하여 긴 요약을 압축
            ai_summary_prompt = f"""
            다음은 '{parent_topic}'에 대한 여러 자식 노드들의 요약을 결합한 내용입니다:

            {combined}

            이 내용을 바탕으로 '{parent_topic}'의 전체 내용을 잘 대표하는 간결한 요약을 {max_length}자 이내로 작성해주세요.
            
            중요한 지시사항:
            - 사용자가 한 말, 키워드, 구체적인 용어, 고유명사, 숫자, 날짜 등을 중요도를 따지지 않고 모두 유지하라
            - 원래 내용의 핵심 의미와 세부사항을 최대한 보존하라
            - 요약하되 정보 손실을 최소화하라
            - 사용자의 질문, AI의 답변, 구체적인 사실 관계를 모두 포함하라
            - 전문 용어와 기술적 세부사항을 우선적으로 유지하라
            - 중요한 세부사항을 유지하면서도 불필요한 부분을 제거하여 핵심 내용만 포함하라
            """

            try:
                ai_summarized = await self.ai_manager.call_ai_async_single(ai_summary_prompt, "부모 노드 요약 생성")
                combined = ai_summarized.strip()
                print(f"✅ [요약 완료] 부모 노드 요약이 {len(combined)}자로 요약되었습니다.")

                if self.debug:
                    print(f"AI 요약 완료 (길이: {len(combined)})")

            except Exception as e:
                if self.debug:
                    print(f"AI 요약 실패, 원본 요약 사용: {e}")
                # AI 요약 실패시 원본 사용하되 길이 제한 적용
                combined = combined[:max_length] + "..." if len(combined) > max_length else combined

        return combined

    async def update_node_chain_after_save(self, saved_node_id: str, conversation_index: int):
        """
        대화 저장 후 노드 체인을 업데이트합니다.
        1. 저장된 노드의 요약을 AI로 업데이트
        2. 부모 노드들을 간단한 결합 방식으로 업데이트
        """
        # 1. 저장된 노드의 요약을 AI로 업데이트
        await self.update_node_summary_with_ai(saved_node_id, conversation_index)

        # 2. 부모 노드들을 간단한 결합 방식으로 업데이트
        await self.update_parent_nodes_simple(saved_node_id)

        # 3. 트리 저장
        self.memory_manager.save_tree()
