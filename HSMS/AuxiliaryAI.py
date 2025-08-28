import asyncio
import re
from config import (API_KEY, LOAD_API_KEYS, GEMINI_MODEL, CATEGORY_RELEVANCE_FINE, 
                   NEW_TOPIC_FINE, CONVERSATION_SEPARATION_FINE, GROUP_SIMILARITY_FINE, ALL_MEMORY)
from .AIManager import AIManager
from .MemoryNode import MemoryNode


class AuxiliaryAI:
    """보조 인공지능 - 계층적 기억 관리 시스템의 핵심 컨트롤러"""
    
    def __init__(self, memory_manager, debug=False, short_debug=False, max_depth=None, top_search_n=None):
        from config import get_config_value
        self.memory_manager = memory_manager
        self.ai_manager = AIManager(debug=debug, short_debug=short_debug)
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
        summary_prompt = f"""
        노드 주제: {node.topic}
        기존 요약: {node.summary}
        자식 노드 요약:
        {'; '.join(child_summaries)}
        이 노드와 자식 노드들의 내용을 바탕으로, 이 노드의 요약을 1-2문장으로 간결하게 생성하라.
        """

        # 3. AI 호출 (topic, summary)
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

        try:
            new_summary = await self.ai_manager.call_ai_async_single(summary_prompt, "요약 생성")
        except Exception as e:
            if self.debug:
                print(f"[ERROR] 요약 생성 실패: {e}")
            new_summary = node.summary

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

    """
    async def _process_conversation_with_dynamic_structure(self, conversation, conversation_index):
        \"\"\"
        동적 트리 구조를 고려하여 대화를 분류하고 저장한 뒤,
        마지막으로 상호작용한 리프 노드의 ID를 반환합니다.
        \"\"\"
        user_input = conversation[0]['content']
        
        # ... (기존 카테고리 관련성 검사 로직) ...
        
        # 3. 카테고리 수에 따른 동적 처리
        if len(relevant_categories) == 0:
            return await self._create_new_category_structure(conversation, conversation_index, user_input)
        elif len(relevant_categories) == 1:
            category_name = relevant_categories[0]
            return await self._add_to_existing_category(conversation, conversation_index, category_name, user_input)
        else:
            # 다중 카테고리 - 가장 관련성 높은 카테고리를 선택하여 처리
            best_category = await self._select_best_category(relevant_categories, user_input)
            return await self._add_to_existing_category(conversation, conversation_index, best_category, user_input)
    """

    """
    async def _create_new_category_structure(self, conversation, conversation_index, user_input):
        # ... (기존 로직) ...
        # 대화 노드 A1 생성
        # ...
        self.memory_manager.add_node(conversation_node, category_node.node_id)
        return conversation_node.node_id # 생성된 대화 노드 ID 반환
    """

    """
    async def _add_to_existing_category(self, conversation, conversation_index, category_name, user_input):
        # ... (기존 로직) ...
        # 깊이 초과 시 병합 또는 새 노드 추가
        if not self.memory_manager.can_insert_child(category_node_id, self.max_depth):
            return await self._merge_to_similar_conversation(conversation, conversation_index, category_node_id, user_input)
        
        # 새 대화 노드 생성
        # ...
        self.memory_manager.add_node(conversation_node, category_node_id)
        return conversation_node.node_id # 생성된 대화 노드 ID 반환
    """
    
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
                print("깊이 초과: 병합 정책 적용")
            # 가장 유사한 기존 카테고리에 병합
            node_id = await self._fallback_merge_to_similar_category(conversation, conversation_index, user_input)
            return node_id
        
        # AI를 통한 카테고리명과 요약을 병렬 생성
        category_name_task = self._generate_category_name(user_input)
        category_summary_task = self._generate_category_summary(user_input)
        category_name, category_summary = await asyncio.gather(category_name_task, category_summary_task)
        
        if self.debug:
            print(f"카테고리 생성: '{category_name}'")
        
        # 카테고리 노드 생성
        category_node = MemoryNode(
            topic=category_name,
            summary=category_summary,
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
    
    """
    async def _select_best_category(self, relevant_categories, user_input):
        \"\"\"가장 관련성 높은 카테고리를 선택합니다.\"\"\"
        if len(relevant_categories) == 1:
            return relevant_categories[0]
        
        # 첫 번째 카테고리 반환 (추후 AI 기반 선택 로직 추가 가능)
        return relevant_categories[0]
    """
    
    async def _add_to_existing_category(self, conversation, conversation_index, category_name, user_input):
        """기존 카테고리에 대화를 추가합니다."""
        category_node = None
        root_node = self.memory_manager.get_root_node()
        
        for child_id in root_node.children_ids:
            child_node = self.memory_manager.get_node(child_id)
            if child_node and child_node.topic == category_name:
                category_node = child_node
                break
        
        if category_node:
            await self._process_single_category(conversation, conversation_index, category_name)
    
    async def _create_group_structure(self, conversation, conversation_index, relevant_categories, user_input):
        """여러 카테고리를 위한 그룹 구조를 생성합니다."""
        if self.debug:
            print(f"그룹 생성 시작: {len(relevant_categories)}개 카테고리")
        
        # 두 카테고리 간의 유사도 판단
        if len(relevant_categories) >= 2:
            category_a = relevant_categories[0]
            category_b = relevant_categories[1]
            
            # 카테고리 노드 찾기
            category_a_node = self._find_category_node_by_name(category_a)
            category_b_node = self._find_category_node_by_name(category_b)
            
            if category_a_node and category_b_node:
                # AI로 유사도 판단
                should_group = await self._check_category_similarity(category_a_node, category_b_node)
                
                if should_group:
                    if self.debug:
                        print(f"그룹화 결정: '{category_a}' + '{category_b}'")
                    
                    # AB 그룹 생성
                    group_name = await self._generate_group_name_for_categories(category_a, category_b)
                    group_summary = await self._generate_group_summary_for_categories(category_a_node, category_b_node)
                    
                    # 깊이 검증
                    if self._can_create_group_above(category_a_node.node_id):
                        # A 카테고리 위에 AB 그룹 생성
                        group_node_id = self.memory_manager.insert_group_above(
                            category_a_node.node_id, group_name, group_summary
                        )
                        
                        if group_node_id:
                            # B 카테고리를 AB 그룹으로 이동
                            self.memory_manager.reparent_node(category_b_node.node_id, group_node_id)
                            
                            # 새 대화를 적절한 카테고리에 추가
                            target_category = await self._select_target_category_in_group(
                                user_input, [category_a, category_b]
                            )
                            node_id = await self._add_to_existing_category(conversation, conversation_index, target_category, user_input)
                            
                            if self.debug:
                                print(f">>>> [DYNAMIC] AB 그룹 '{group_name}' 생성 완료")
                                print(f">>>> [DYNAMIC] 대화를 '{target_category}' 카테고리에 추가")
                            return node_id
                    else:
                        if self.debug:
                            print("깊이 제한: 리프 병합 시도")
                        # 깊이 제한으로 그룹 생성 불가 시 리프 병합
                        node_id = await self._handle_depth_limit_with_merge(conversation, conversation_index, relevant_categories, user_input)
                        return node_id
        
        # 그룹화 불가능한 경우 기존 방식으로 처리
        if self.debug:
            print("그룹화 불가능: 첫 번째 카테고리에 추가")
        first_category = relevant_categories[0]
        node_id = await self._add_to_existing_category(conversation, conversation_index, first_category, user_input)
        return node_id
    
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
        """단일 카테고리에 대한 대화를 처리합니다."""
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
            return
        
        if self.debug:
            print(f">> 완료: '{category_name}' 카테고리 노드 발견 (ID: {category_node.node_id})")
        
        user_input = conversation[0]['content']
        
        if self.debug:
            print(f">> 검색중: 새로운 주제인지 AI로 판단 중...")
        
        # 새로운 주제인지 판단
        if await self._check_for_new_topic_async(category_node, user_input):
            # 새로운 노드 생성
            if self.debug:
                print(f">> 완료: 새로운 주제로 판단 - 새 노드 생성")
            new_node = await self._create_new_node_async(category_node, user_input, conversation, conversation_index)
            # 새로운 방식: conversation_indices에 대화 추가
            new_node.add_conversation(conversation_index)
            # 부모 카테고리에도 대화 추가
            category_node.add_conversation(conversation_index)
            await self._safe_save_tree()
            if self.debug:
                print(f"새 노드 생성: '{new_node.topic}'")
        else:
            # 기존 노드에 추가
            if self.debug:
                print("기존 노드에 추가")
            relevant_child = await self._find_relevant_child_node_async(category_node, user_input)
            if relevant_child:
                if self.debug:
                    print(f"대상 노드: '{relevant_child.topic}'")
                await self.update_node_and_parents(relevant_child, conversation, conversation_index)
                if self.debug:
                    print("노드 업데이트 완료")
            else:
                # 관련 하위 노드가 없으면 새로운 노드 생성
                if self.debug:
                    print("새 노드 생성")
                new_node = await self._create_new_node_async(category_node, user_input, conversation, conversation_index)
                # 새로운 방식: conversation_indices에 대화 추가
                new_node.add_conversation(conversation_index)
                # 부모 카테고리에도 대화 추가
                category_node.add_conversation(conversation_index)
                await self._safe_save_tree()
                if self.debug:
                    print(f"|| 새 노드 생성 완료:")
                    print(f">> [DEBUG]   노드 ID: {new_node.node_id}")
                    print(f">> [DEBUG]   주제: '{new_node.topic}'")
                    print(f">> [DEBUG]   부모: '{category_name}' 카테고리")
                    print(f">> [DEBUG]   대화 인덱스: {new_node.conversation_indices}")
        
        if self.debug:
            print(f">> [DEBUG] === '{category_name}' 카테고리 처리 완료 ===\n")
    
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
    
    async def _separate_conversation_by_categories(self, user_input, ai_response, categories):
        """대화 내용을 카테고리별로 분리합니다."""
        from config import CONVERSATION_SEPARATION_FINE
        
        # Few-shot 예제들을 시스템 프롬프트에 포함
        few_shot_examples = "\n\n예시:\n"
        for i, (example_input, expected_output) in enumerate(CONVERSATION_SEPARATION_FINE, 1):
            few_shot_examples += f"예시 {i}:\n{example_input}\n답변:\n{expected_output}\n\n"
        
        system_prompt = f"""대화 내용을 주제별로 분리하라.

사용자의 대화와 AI의 응답을 분석하여, 각 카테고리와 관련된 부분만을 추출하라.
한 대화에서 여러 주제가 다뤄질 수 있으므로, 각 카테고리에 해당하는 내용만 정확히 분리하라.

출력 형식:
카테고리명:
사용자: [해당 카테고리와 관련된 사용자 발언 부분]
AI: [해당 카테고리와 관련된 AI 응답 부분]

카테고리명:
사용자: [해당 카테고리와 관련된 사용자 발언 부분]  
AI: [해당 카테고리와 관련된 AI 응답 부분]

{few_shot_examples}"""
        
        categories_list = ", ".join(categories)
        prompt = f"""관련 카테고리들: {categories_list}

사용자 발언: {user_input}
AI 응답: {ai_response}

위 대화를 각 카테고리별로 관련된 부분만 분리하여 출력하라."""
        
        if self.debug:
            print(f"대화 분리 AI 호출: {len(categories)}개 카테고리")

        try:
            result = await self.ai_manager.call_ai_async_single(prompt, system_prompt)

            if self.debug:
                print("대화 분리 완료")
                print(f"=========================================>")
            
            # 결과 파싱 개선
            separated = {}
            current_category = None
            current_user = ""
            current_ai = ""
            
            lines = result.strip().split('\n')
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                    
                # 카테고리 시작 감지 (더 유연하게)
                for category in categories:
                    if line.startswith(category + ':') or line == category + ':':
                        # 이전 카테고리 저장
                        if current_category and (current_user or current_ai):
                            separated[current_category] = {
                                'user': current_user.strip(),
                                'ai': current_ai.strip()
                            }
                            if self.debug:
                                print(f"파싱완료: '{current_category}' -> 사용자: '{current_user.strip()}', AI: '{current_ai.strip()}'")
                        
                        # 새 카테고리 시작
                        current_category = category
                        current_user = ""
                        current_ai = ""
                        if self.debug:
                            print(f"새 카테고리 시작: '{current_category}'")
                        break
                else:
                    # 카테고리가 아닌 라인 처리
                    if line.startswith('사용자:'):
                        current_user = line[4:].strip()
                    elif line.startswith('AI:'):
                        current_ai = line[3:].strip()
            
            # 마지막 카테고리 저장
            if current_category and (current_user or current_ai):
                separated[current_category] = {
                    'user': current_user.strip(),
                    'ai': current_ai.strip()
                }
                if self.debug:
                    print(f"마지막 카테고리 저장: '{current_category}' -> 사용자: '{current_user.strip()}', AI: '{current_ai.strip()}'")
            
            # 분리되지 않은 카테고리는 원본 대화 사용
            for category in categories:
                if category not in separated:
                    separated[category] = {
                        'user': user_input,
                        'ai': ai_response
                    }
                    if self.debug:
                        print(f"원본 대화 사용: '{category}'")
            
            return separated
            
        except Exception as e:
            if self.debug:
                print(f"대화 분리 오류: {e}")
            # 오류 시 원본 대화를 모든 카테고리에 할당
            return {cat: {'user': user_input, 'ai': ai_response} for cat in categories}
    
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
        # 새로운 방식: conversation_indices에 대화 추가
        new_node.add_conversation(conversation_index)
        # 부모 카테고리에도 대화 추가
        category_node.add_conversation(conversation_index)
        await self._safe_save_tree()
        
        if self.debug:
            print(f"하위 노드 생성: '{new_node.topic}'")
    
    async def _generate_category_name_async(self, user_input):
        """AI를 사용하여 새로운 카테고리명을 생성합니다."""
        from config import CATEGORY_NAME_FINE
        
        # Few-shot 예제들과 규칙을 시스템 프롬프트에 명확히 포함
        few_shot_examples = "\n\n예시:\n"
        for i, (example_input, expected_output) in enumerate(CATEGORY_NAME_FINE, 1):
            few_shot_examples += f"예시 {i}:\n{example_input}\n답변: {expected_output}\n\n"

        system_prompt = f"""대화 내용을 분석하여 적절한 카테고리명을 생성하라.

사용자의 대화 내용을 분석하고, 이 대화가 속할 수 있는 가장 적절한 카테고리명을 생성하라.
카테고리명은 간결하고 포괄적이어야 하며, 2-8글자 정도로 작성하라.

중요한 규칙:
1. '카테고리:', '주제:' 등 접두사는 절대 붙이지 마라.
2. 특수문자나 기호(*, **, -, [], (), 등)는 절대 사용하지 마라.
3. 한글 또는 영어만 사용하라.
4. 단 하나의 카테고리명만 출력하라.
5. 간결하고 명확하게 작성하라.
6. 카테고리명에 설명, 접두사, 불필요한 문구를 추가하지 마라.

# 잘못된 예시 (금지!):
#   카테고리: 건강
#   주제: 건강
#   건강/의학
#   건강 (카테고리)
# 올바른 예시:
#   건강
#   물리학
#   요리

{few_shot_examples}"""
        
        prompt = f"사용자 대화: {user_input}\n\n이 대화에 적합한 카테고리명을 하나만 생성하라. 2-8글자로 간결하게 작성하고, 특수문자나 기호는 사용하지 마라."
        
        try:
            result = await self.ai_manager.call_ai_async_single(prompt, system_prompt)
            category_name = result.strip()
            
            # 특수문자 제거 및 정리
            import re
            # 대괄호나 기타 특수문자 제거
            category_name = re.sub(r'[\[\]*\-(){},".:;!?]', '', category_name)
            # 연속된 공백을 하나로 변환
            category_name = re.sub(r'\s+', ' ', category_name)
            category_name = category_name.strip()
            
            # 앞뒤 따옴표 제거
            category_name = category_name.strip('\'"')
            
            # 카테고리명이 너무 길거나 비어있으면 기본값 사용
            if not category_name or len(category_name) > 10:
                return "일반"
            
            return category_name
        except Exception as e:
            print(f"카테고리명 생성 중 오류: {e}")
            return "일반"
    
    async def _check_for_new_topic_async(self, parent_node, user_input):
        """새로운 주제인지 AI로 판단합니다."""
        if self.debug:
            print(f"새 주제 판단: '{parent_node.topic}' 카테고리")
        
        system_prompt = """새로운 대화가 기존 노드의 하위 주제인지, 완전히 새로운 주제인지 판단하라.
반드시 "True" (새로운 주제) 또는 "False" (기존 주제의 하위)로만 답하라."""
        
        prompt = f"부모 노드 주제: {parent_node.topic}\n새로운 대화: {user_input}"
        
        try:
            result = await self.ai_manager.call_ai_async_single(prompt, system_prompt, fine=NEW_TOPIC_FINE)
            is_new_topic = result.strip() == 'True'
            
            if self.debug:
                status = "새로운 주제" if is_new_topic else "기존 주제"
                print(f"판단 결과: {status}")
            
            return is_new_topic
        except Exception as e:
            if self.debug:
                print(f"새 주제 판단 오류: {e}")
            return True  # 오류 시 새 주제로 간주
    
    async def _find_relevant_child_node_async(self, parent_node, user_input):
        """부모 노드의 자식 노드 중 관련된 노드를 AI로 찾습니다."""
        if not parent_node.children_ids:
            return None
        
        child_nodes = []
        for child_id in parent_node.children_ids:
            child_node = self.memory_manager.get_node(child_id)
            if child_node and child_node.coordinates["start"] != -1:  # 카테고리가 아닌 실제 대화 노드
                child_nodes.append(child_node)
        
        if not child_nodes:
            return None
        
        # 각 자식 노드와의 관련성을 AI로 판단
        relevance_queries = []
        for node in child_nodes:
            query = f"사용자 질문: {user_input}\n기존 노드 주제: {node.topic}\n기존 노드 요약: {node.summary[:200]}"
            relevance_queries.append(query)
        
        system_prompt = """사용자 질문과 기존 노드의 관련성을 판단하라.
주제와 요약을 보고 사용자 질문과 관련이 있는지 판단하라.
"True" (관련 있음) 또는 "False" (관련 없음)로만 답하라."""
        
        try:
            results = await self.ai_manager.call_ai_async_multiple(
                relevance_queries, system_prompt, label="관련 자식 노드"
            )
            
            # 가장 관련성이 높은 노드 반환
            for i, result in enumerate(results):
                if result.strip() == 'True':
                    return child_nodes[i]
            
            return None
        except Exception as e:
            if self.debug:
                print(f"자식 노드 찾기 오류: {e}")
            return None
    
    async def _create_new_node_async(self, parent_node, user_input, conversation, conversation_index):
        """AI를 사용하여 새로운 노드를 비동기로 생성합니다."""
        user_content = conversation[0]['content']
        ai_content = conversation[1]['content']
        
        # AI 기반 주제 추출
        topic_system_prompt = """대화에서 핵심 주제를 추출하라.
사용자의 입력과 AI의 응답을 분석하여 간결하고 명확한 주제명을 생성하라.
주제명은 2-10글자 정도로 간단하고 구체적이어야 한다.

예시:
- 사과에 대한 대화 → "사과"
- SSD 작동 원리 → "SSD"
- 인류 역사 → "인류 역사"
- 학교 이야기 → "학교"

대화의 실제 내용과 맥락을 정확히 반영하는 주제명을 만들라."""
        
        topic_prompt = f"사용자: {user_content}\nAI: {ai_content}\n\n위 대화의 핵심 주제를 간결하게 추출하라."
        
        # 요약 생성 - AI 응답 유무에 따라 다른 처리
        if ai_content.strip():  # AI 응답이 있는 경우
            summary_system_prompt = """대화 내용을 상세하고 포괄적으로 요약하라.
다음 원칙에 따라 요약하라:
- 사용자가 말한 내용과 AI가 응답한 내용을 모두 포함하여, 대화의 전체적인 맥락이 드러나게 작성하라.
- 핵심 주제, 중요한 정보, 구체적인 세부사항을 빠짐없이 포함하라.
- 요약의 길이는 내용에 따라 자연스럽게 조절하며, 너무 짧게 줄이지 마라.
- 나중에 이 요약만 보고도 대화의 내용을 충분히 파악할 수 있도록 상세하게 작성하라."""
            summary_prompt = f"사용자: {user_content}\nAI: {ai_content}\n\n위 대화를 상세히 요약하라."
        else:  # AI 응답이 없는 경우 (record 모드)
            summary_system_prompt = """사용자가 제공한 정보를 상세하고 포괄적으로 요약하라.
다음 원칙에 따라 요약하라:
- 사용자가 말한 내용의 핵심 정보를 모두 포함하라.
- 중요한 정보, 구체적인 세부사항을 빠짐없이 포함하라.
- 정보의 맥락과 의미를 상세히 설명하라.
- 나중에 이 요약만 보고도 사용자가 어떤 정보를 제공했는지 충분히 파악할 수 있도록 작성하라."""
            summary_prompt = f"사용자: {user_content}\n\n위 사용자 발언의 내용을 상세히 요약하라."
        
        try:
            # 병렬로 주제와 요약 생성
            topic_task = self.ai_manager.call_ai_async_single(topic_prompt, topic_system_prompt)
            summary_task = self.ai_manager.call_ai_async_single(summary_prompt, summary_system_prompt)
            
            topic, summary = await asyncio.gather(topic_task, summary_task)
            
            # 주제가 적절하지 않으면 기본값 사용
            if not topic or len(topic.strip()) == 0 or len(topic.strip()) > 15:
                topic = "일반 대화"
            
            # 새 노드 생성
            new_node = MemoryNode(
                topic=topic.strip(),
                summary=summary,
                coordinates={"start": conversation_index, "end": conversation_index}
            )
            
            # 트리에 추가
            self.memory_manager.add_node(new_node, parent_node.node_id)
            
            return new_node
            
        except Exception as e:
            print(f"새 노드 생성 중 오류: {e}")
            # 오류 시 기본 노드 생성
            new_node = MemoryNode(
                topic="일반 대화",
                summary=f"사용자가 {user_content[:50]}...에 대해 이야기했습니다.",
                coordinates={"start": conversation_index, "end": conversation_index}
            )
            self.memory_manager.add_node(new_node, parent_node.node_id)
            return new_node
    
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
        
        new_summary = await self._generate_enhanced_summary_async(node.summary, user_content, ai_content)
        
        # 새로운 방식: conversation_indices에 대화 추가
        node.add_conversation(conversation_index)
        
        self.memory_manager.update_node(
            node.node_id,
            summary=new_summary
        )
        
        # 부모 카테고리에도 대화 추가
        if node.parent_id:
            parent_node = self.memory_manager.get_node(node.parent_id)
            if parent_node:
                parent_node.add_conversation(conversation_index)
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
    
    async def update_parent_summary(self, parent_node, child_node):
        """부모 노드의 요약을 자식 노드 변경사항에 맞춰 업데이트합니다."""
        # 카테고리 노드인 경우 요약을 변경하지 않음
        if parent_node.coordinates["start"] == -1 and parent_node.coordinates["end"] == -1:
            return
        
        system_prompt = """부모 노드의 요약을 업데이트하라.
중요한 규칙:
1. 부모 노드의 주제와 관련된 내용만 포함하라
2. 자식 노드의 주제와 무관한 내용은 절대 포함하지 마라
3. 부모 노드의 원래 주제 맥락을 유지하라
4. 간결하고 핵심적인 요약만 작성하라"""
        
        # 모든 자식 노드의 주제를 수집하여 맥락 제공
        child_topics = []
        for child_id in parent_node.children_ids:
            child = self.memory_manager.get_node(child_id)
            if child:
                child_topics.append(child.topic)
        
        prompt = f"""부모 노드 주제: {parent_node.topic}
부모 노드 기존 요약: {parent_node.summary}
자식 노드들: {', '.join(child_topics)}
업데이트된 자식 노드: {child_node.topic}

부모 노드 '{parent_node.topic}'의 주제와 직접 관련된 내용만으로 요약을 업데이트하라. 
다른 주제의 내용은 포함하지 마라."""
        
        updated_summary = await self._generate_enhanced_parent_summary_async(parent_node, child_node, child_topics)
        self.memory_manager.update_node(parent_node.node_id, summary=updated_summary)
        
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

    async def _generate_enhanced_summary_async(self, current_summary, user_content, ai_content):
        """Generate enhanced summary using multiple API keys for better quality"""
        if self.debug:
            print(f"|| [DEBUG] 향상된 요약 생성 - 다중 관점 사용")
        
        # Create different prompt variations for better summary generation
        base_content = f"""
        기존 요약: {current_summary}
        새로운 사용자 메시지: {user_content}
        새로운 AI 응답: {ai_content}
        """
        
        queries = [
            f"""
            {base_content}
            
            위의 기존 요약에 새로운 대화 내용을 자연스럽게 통합하여 완전한 요약을 작성해주세요.
            중요한 정보는 유지하고, 중복되는 내용은 정리해주세요.
            """,
            f"""
            {base_content}
            
            대화의 전체적인 맥락과 흐름을 고려하여 포괄적인 요약을 만들어주세요.
            핵심 주제와 중요한 세부사항을 균형있게 포함해주세요.
            """,
            f"""
            {base_content}
            
            이전 대화와 새로운 대화를 연결하여 일관성 있는 요약을 생성해주세요.
            주요 논점과 결론을 명확하게 표현해주세요.
            """
        ]
        
        system_prompt = "대화 내용을 정확하고 간결하게 요약하라. 핵심 정보를 놓치지 않으면서도 읽기 쉬운 요약을 작성하라."
        
        try:
            # Generate multiple summaries using different perspectives
            results = await self.ai_manager.call_ai_async_multiple(queries, system_prompt, label="향상된 요약 생성")
            
            if self.debug:
                print(f"|| [DEBUG] {len(results)}개의 요약 변형 생성 완료")
            
            # Select the best summary (longest one with content, or first valid one)
            best_summary = None
            for i, result in enumerate(results):
                if result and result.strip():
                    if best_summary is None or len(result.strip()) > len(best_summary.strip()):
                        best_summary = result.strip()
                        if self.debug:
                            print(f"|| [DEBUG] 더 나은 요약 발견 (변형 {i+1}, 길이: {len(best_summary)})")
            
            final_summary = best_summary if best_summary else current_summary
            if self.debug:
                print(f"|| [DEBUG] 최종 선택된 요약 길이: {len(final_summary)}")
            
            return final_summary
        except Exception as e:
            print(f"|| 오류: 향상된 요약 생성 중 오류: {e}")
            return current_summary

    async def _generate_enhanced_parent_summary_async(self, parent_node, child_node, child_topics):
        """Generate enhanced parent summary using multiple API keys for better quality"""
        if self.debug:
            print(f"|| [DEBUG] 향상된 부모 요약 생성 - 다중 관점 사용")
        
        base_content = f"""
        부모 노드 주제: {parent_node.topic}
        부모 노드 기존 요약: {parent_node.summary}
        자식 노드들: {', '.join(child_topics)}
        업데이트된 자식 노드: {child_node.topic}
        """
        
        queries = [
            f"""
            {base_content}
            
            부모 노드 '{parent_node.topic}'의 주제와 직접 관련된 내용만으로 요약을 업데이트하라.
            자식 노드의 변화를 반영하되, 부모 노드의 원래 주제 맥락을 유지하라.
            """,
            f"""
            {base_content}
            
            부모 노드의 전체적인 구조와 하위 주제들을 고려하여 포괄적인 요약을 만들어주세요.
            새로 추가된 자식 노드의 내용을 자연스럽게 통합하라.
            """,
            f"""
            {base_content}
            
            부모 노드의 핵심 주제에 집중하여 간결하고 명확한 요약을 작성해주세요.
            자식 노드와 무관한 내용은 절대 포함하지 마세요.
            """
        ]
        
        system_prompt = """계층적 메모리 구조에서 부모 노드의 요약을 업데이트하라.
다음 원칙을 따르라:
1. 부모 노드의 주제와 직접 관련된 내용만 포함
2. 자식 노드의 주제와 무관한 내용은 절대 포함하지 마라
3. 부모 노드의 원래 주제 맥락을 유지하라
4. 간결하고 핵심적인 요약만 작성하라"""
        
        try:
            # Generate multiple summaries using different perspectives
            results = await self.ai_manager.call_ai_async_multiple(queries, system_prompt, label="향상된 부모 요약 생성")
            
            if self.debug:
                print(f"|| [DEBUG] {len(results)}개의 부모 요약 변형 생성 완료")
            
            # Select the best summary (most relevant to parent topic)
            best_summary = None
            for i, result in enumerate(results):
                if result and result.strip():
                    # Simple heuristic: choose the one that mentions the parent topic most
                    parent_topic_mentions = result.lower().count(parent_node.topic.lower())
                    if best_summary is None or (
                        parent_topic_mentions > best_summary.lower().count(parent_node.topic.lower())
                    ):
                        best_summary = result.strip()
                        if self.debug:
                            print(f"|| [DEBUG] 더 나은 부모 요약 발견 (변형 {i+1}, 부모 주제 언급: {parent_topic_mentions}회)")
            
            final_summary = best_summary if best_summary else parent_node.summary
            if self.debug:
                print(f"|| [DEBUG] 최종 선택된 부모 요약 길이: {len(final_summary)}")
            
            return final_summary
        except Exception as e:
            print(f"|| 오류: 향상된 부모 요약 생성 중 오류: {e}")
            return parent_node.summary

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
        system_prompt = """사용자의 입력이 주어진 카테고리와 관련이 있는지 판단하라.
관련이 있으면 "True", 없으면 "False"로만 답하라."""
        
        query = f"""사용자 입력: {user_input}
카테고리 이름: {category_name}
카테고리 요약: {category_summary}"""
        
        try:
            result = await self.ai_manager.call_ai_async_single(query, system_prompt)
            return result.strip().lower() == 'true'
        except Exception as e:
            if self.debug:
                print(f">>>> [ERROR] 카테고리 관련성 판단 오류: {e}")
            return False
    
    async def _generate_category_name(self, user_input):
        """사용자 입력을 기반으로 카테고리명을 생성합니다."""
        system_prompt = """사용자 입력을 분석하여 적절한 카테고리명을 생성하라.
- 2-8자의 간결한 한국어로 작성
- 포괄적이면서도 구체적인 주제 표현
- 예: "음식", "반려동물", "취미활동" 등"""
        
        try:
            result = await self.ai_manager.call_ai_async_single(user_input, system_prompt)
            return result.strip()[:20]  # 최대 20자 제한
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
    
    async def _create_group_above_node(self, existing_node_id, group_topic=None, group_summary=None):
        """기존 노드 위에 그룹 노드를 삽입합니다."""
        existing_node = self.memory_manager.get_node(existing_node_id)
        if not existing_node:
            return None
        
        # 그룹 이름 자동 생성
        if not group_topic:
            group_topic = await self._generate_group_name([existing_node])
        
        if not group_summary:
            group_summary = f"{group_topic}에 관한 그룹화된 카테고리입니다."
        
        # 새 그룹 노드 생성
        group_node = MemoryNode(
            topic=group_topic,
            summary=group_summary,
            parent_id=existing_node.parent_id,
            coordinates={"start": -1, "end": -1}  # 카테고리 노드
        )
        
        # 기존 노드의 부모-자식 관계 업데이트
        if existing_node.parent_id:
            parent_node = self.memory_manager.get_node(existing_node.parent_id)
            if parent_node:
                # 부모의 자식 목록에서 기존 노드를 그룹 노드로 교체
                if existing_node_id in parent_node.children_ids:
                    parent_node.children_ids[parent_node.children_ids.index(existing_node_id)] = group_node.node_id
        
        # 그룹 노드를 기존 노드의 부모로 설정
        group_node.children_ids = [existing_node_id]
        existing_node.parent_id = group_node.node_id
        
        # 트리에 추가
        self.memory_manager.memory_tree[group_node.node_id] = group_node
        await self._safe_save_tree()
        
        if self.debug:
            print(f">>>> [DYNAMIC] 그룹 '{group_topic}' 생성 완료, 자식: '{existing_node.topic}'")
        
        return group_node.node_id
    
    async def _merge_similar_nodes(self, node_ids):
        """유사한 노드들을 병합합니다."""
        if len(node_ids) < 2:
            return None
        
        nodes = [self.memory_manager.get_node(node_id) for node_id in node_ids]
        nodes = [n for n in nodes if n]  # None 제거
        
        if len(nodes) < 2:
            return None
        
        # 대표 노드 선택 (가장 많은 대화를 가진 노드)
        main_node = max(nodes, key=lambda n: len(n.conversation_indices) if hasattr(n, 'conversation_indices') else 0)
        
        # 다른 노드들의 대화 인덱스를 대표 노드로 병합
        for node in nodes:
            if node.node_id != main_node.node_id:
                if hasattr(node, 'conversation_indices'):
                    main_node.conversation_indices.extend(node.conversation_indices)
                
                # 부모에서 병합되는 노드 제거
                if node.parent_id:
                    parent = self.memory_manager.get_node(node.parent_id)
                    if parent and node.node_id in parent.children_ids:
                        parent.children_ids.remove(node.node_id)
                
                # 트리에서 제거
                if node.node_id in self.memory_manager.memory_tree:
                    del self.memory_manager.memory_tree[node.node_id]
        
        # 대화 인덱스 중복 제거 및 정렬
        if hasattr(main_node, 'conversation_indices'):
            main_node.conversation_indices = sorted(list(set(main_node.conversation_indices)))
        
        # 요약 업데이트
        main_node.summary = await self._generate_merged_summary(nodes)
        
        await self._safe_save_tree()
        
        if self.debug:
            print(f">>>> [DYNAMIC] {len(nodes)}개 노드를 '{main_node.topic}'로 병합 완료")
        
        return main_node.node_id
    
    async def _generate_group_name(self, nodes):
        """노드들을 기반으로 그룹 이름을 생성합니다."""
        topics = [node.topic for node in nodes if node.topic != "ROOT"]
        
        if len(topics) <= 2:
            return " & ".join(topics)
        
        # AI를 통한 그룹명 생성
        system_prompt = """여러 주제를 포괄하는 짧고 명확한 그룹명을 생성하라.
IMPORTANT: 오직 그룹명만 답변하라. 설명이나 다른 텍스트는 포함하지 마라.
- 한글로 2-8자 이내의 단어
- 예: "과학", "음식", "언어", "경제", "철학"
- 카테고리명으로 적절한 핵심 단어"""
        
        try:
            topics_text = ", ".join(topics[:3])  # 최대 3개만
            query = f"주제들: {topics_text}"
            result = await self.ai_manager.call_ai_async_single(query, system_prompt)
            
            # AI 응답에서 실제 그룹명만 추출
            group_name = self._extract_clean_name(result.strip())
            return group_name
        except Exception as e:
            if self.debug:
                print(f">>>> [ERROR] 그룹명 생성 오류: {e}")
            return f"{topics[0]} 관련"
    
    def _extract_clean_name(self, ai_response):
        """AI 응답에서 깨끗한 이름만 추출합니다."""
        
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
        
        # 특수문자나 숫자, 따옴표 제거
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
    
    async def _generate_merged_summary(self, nodes):
        """병합된 노드들의 요약을 생성합니다."""
        summaries = [node.summary for node in nodes if node.summary]
        
        if not summaries:
            return "병합된 노드의 요약"
        
        if len(summaries) == 1:
            return summaries[0]
        
        # AI를 통한 통합 요약 생성
        system_prompt = """여러 요약을 하나로 통합하여 간결하고 포괄적인 요약을 생성하라.
중요한 정보는 유지하면서 중복은 제거하고, 1-2문장으로 작성하라."""
        
        try:
            summaries_text = " | ".join(summaries)
            query = f"다음 요약들을 통합해주세요: {summaries_text}"
            result = await self.ai_manager.call_ai_async_single(query, system_prompt)
            return result.strip()
        except Exception as e:
            if self.debug:
                print(f">>>> [ERROR] 통합 요약 생성 오류: {e}")
            return " / ".join(summaries[:2])  # 실패 시 간단 결합
    
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
                    print(f"===========> 검색 결과 <===========")
                    print(f"발견된 관련 대화: {len(relevant_conversations)}개")
                    print(f"반환할 대화: {limit}개")

                    # 각 대화의 좌표 정보 출력
                    print("\n[대화 좌표 정보]")
                    for i, conv_data in enumerate(relevant_conversations[:limit]):
                        conv_idx = conv_data['index']
                        node_topic = conv_data.get('node_topic', '알 수 없음')
                        print(f"  {i+1}. 대화 {conv_idx}번 - 노드: '{node_topic}'")

                    total_chars = sum(len(str(conv_data['conversation'])) for conv_data in relevant_conversations[:limit])
                    print(f"총 {total_chars}자의 기억 데이터 반환")
                    print(f"==================================>")
                else:
                    print("검색 완료: 관련 없음")
                    print(f"==================================>")
            
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
    
    async def _generate_category_summary(self, user_input):
        """사용자 입력을 기반으로 카테고리의 요약을 생성합니다."""
        system_prompt = """사용자의 발언을 분석하여 해당 카테고리의 요약 설명을 생성하라.
요약은 이 카테고리가 어떤 내용을 다루는지 명확하게 설명해야 한다.
1-2문장으로 간결하지만 포괄적으로 작성하라.
예시:
- "내 이름은 김철수이고 수학을 좋아한다" → "사용자의 기본 정보와 개인적 특성에 관한 내용"
- "사과의 영양소에 대해 궁금하다" → "과일의 영양 성분과 건강 효과에 관한 정보"
- "양자역학이 흥미롭다" → "물리학의 양자역학 분야에 대한 이론과 개념들"""
        
        try:
            prompt = f"사용자 발언: '{user_input}'"
            result = await self.ai_manager.call_ai_async_single(prompt, system_prompt)
            return result.strip()
        except Exception as e:
            if self.debug:
                print(f">>>> [ERROR] 카테고리 요약 생성 오류: {e}")
            return f"'{user_input[:20]}...'와 관련된 대화들을 관리하는 카테고리입니다."
    
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
    
    async def _evaluate_category_relevance(self, user_input, existing_categories):
        """사용자 입력과 기존 카테고리들의 관련성을 병렬로 평가합니다."""
        if not existing_categories:
            return []
        
        try:
            from config import CATEGORY_RELEVANCE_FINE
            
            # 병렬 처리를 위한 쿼리 생성
            queries = []
            category_info = []
            
            for category in existing_categories:
                # Few-shot 예제를 포함한 프롬프트 구성
                few_shot_examples = "\n\n예시:\n"
                for i, (example_input, expected_output) in enumerate(CATEGORY_RELEVANCE_FINE, 1):
                    few_shot_examples += f"예시 {i}:\n{example_input}\n답변:\n{expected_output}\n\n"
                
                query = f"""기존 카테고리들:
{category}: {category}에 대한 모든 대화를 관리하는 카테고리입니다

사용자 대화: {user_input}

위 대화가 각 카테고리와 관련이 있는지 판단하고, 다음 형식으로 답변하라:
{category}: True/False

{few_shot_examples}"""
                
                queries.append(query)
                category_info.append(category)
            
            system_prompt = """사용자 대화를 분석하여 각 카테고리와의 관련성을 판단하라.
부분적으로라도 관련이 있으면 True로 판단하고, 전혀 관련이 없으면 False로 판단하라.
정확히 요청된 형식으로만 답변하라."""
            
            if self.debug and len(queries) > 1:
                # 병렬 시작 메시지
                print(f"===========> AI 병렬 호출 시작 ===========>")
                print(f"호출 대상: 카테고리 관련성 평가")
                print(f"호출 수량: {len(queries)}개")
                for i, category in enumerate(category_info):
                    print(f"  {i+1}. 카테고리: '{category}'")
                print(f"=========================================>")
            
            # 병렬 AI 호출
            results = await self.ai_manager.call_ai_async_multiple(queries, system_prompt)
            
            # 결과 처리
            relevant_categories = []
            for i, result in enumerate(results):
                category = category_info[i]
                # 결과에서 True/False 추출
                if f"{category}: True" in result or result.strip().lower() == 'true':
                    relevant_categories.append(category)
            
            if self.debug and len(queries) > 1:
                # 병렬 완료 메시지
                print(f"===========> AI 병렬 호출 완료 ===========>")
                print(f"총 소요시간: 병렬 처리 완료")
                print(f"관련 카테고리 발견: {len(relevant_categories)}개")
                for category in relevant_categories:
                    print(f"  - '{category}'")
                print(f"=========================================>")
            
            return relevant_categories
            
        except Exception as e:
            if self.debug:
                print(f">>>> [ERROR] 카테고리 관련성 평가 오류: {e}")
            return []
    
    async def _find_category_node_id(self, category_name):
        """카테고리 이름으로 노드 ID를 찾습니다."""
        for node_id, node in self.memory_manager.memory_tree.items():
            if node.topic == category_name:
                return node_id
        return None
    
    async def _merge_to_similar_conversation(self, conversation, conversation_index, category_node_id, user_input):
        """유사한 대화가 있는 노드에 병합합니다."""
        category_node = self.memory_manager.get_node(category_node_id)
        if not category_node:
            return None
        
        # 자식 노드들 중에서 유사한 주제 찾기
        for child_id in category_node.children_ids:
            child_node = self.memory_manager.get_node(child_id)
            if child_node and await self._is_similar_topic_ai(user_input, child_node.topic):
                child_node.conversation_indices.append(conversation_index)
                await self._safe_save_tree()
                return child_id  # 병합된 노드 ID 반환
        
        # 유사한 노드가 없으면 새로운 노드 생성
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
        return conversation_node.node_id  # 새로 생성된 노드 ID 반환
    
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
    
    async def _fallback_merge_to_similar_category(self, conversation, conversation_index, user_input):
        """유사한 카테고리를 찾아서 병합합니다."""
        # 루트 노드의 자식들(카테고리들) 중에서 유사한 것 찾기
        root_node = self.memory_manager.get_root_node()
        if not root_node:
            return False
        
        for child_id in root_node.children_ids:
            child_node = self.memory_manager.get_node(child_id)
            if child_node and await self._is_similar_topic_ai(user_input, child_node.topic):
                # 이 카테고리에 추가
                node_id = await self._add_to_existing_category(conversation, conversation_index, child_node.topic, user_input)
                return node_id
        
        return None
    
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
    
    async def _check_category_similarity(self, category_a_node, category_b_node):
        """두 카테고리의 유사도를 AI로 판단합니다."""
        system_prompt = """두 카테고리가 하나의 그룹으로 묶일 만큼 유사한지 판단하라.
유사도 기준:
- 같은 상위 개념의 하위 분야들인가?
- 함께 다루어도 자연스러운 주제들인가?
- 사용자가 관련지어 생각할 만한 카테고리들인가?

반드시 "True" (그룹화 적합) 또는 "False" (그룹화 부적합)로만 답하라."""
        
        prompt = f"""카테고리 A: {category_a_node.topic}
카테고리 A 설명: {category_a_node.summary}

카테고리 B: {category_b_node.topic}  
카테고리 B 설명: {category_b_node.summary}

위 두 카테고리가 하나의 그룹으로 묶일 만큼 유사합니까?"""
        
        try:
            result = await self.ai_manager.call_ai_async_single(
                prompt, system_prompt, fine=GROUP_SIMILARITY_FINE
            )
            is_similar = result.strip().lower() == 'true'
            
            if self.debug:
                print(f">>>> [SIMILARITY] '{category_a_node.topic}' vs '{category_b_node.topic}': {is_similar}")
            
            return is_similar
        except Exception as e:
            if self.debug:
                print(f">>>> [ERROR] 유사도 판단 오류: {e}")
            return False
    
    async def _generate_group_name_for_categories(self, category_a, category_b):
        """두 카테고리를 위한 그룹명을 생성합니다."""
        system_prompt = """두 카테고리를 포괄하는 적절한 그룹명을 생성하라.
요구사항:
- 2-8자의 간결한 한국어
- 두 카테고리의 공통점을 반영
- 상위 개념으로 추상화
- 예: "학업", "취미", "예술", "운동" 등

오직 그룹명만 답변하라."""
        
        prompt = f"카테고리 1: {category_a}\n카테고리 2: {category_b}"
        
        try:
            result = await self.ai_manager.call_ai_async_single(prompt, system_prompt)
            group_name = result.strip()
            
            # 길이 제한 검증
            if len(group_name) > 8:
                group_name = group_name[:8]
            
            if self.debug:
                print(f">>>> [GROUP-NAME] 생성된 그룹명: '{group_name}'")
            
            return group_name
        except Exception as e:
            if self.debug:
                print(f">>>> [ERROR] 그룹명 생성 오류: {e}")
            return f"{category_a[:2]}{category_b[:2]}"  # 폴백
    
    async def _generate_group_summary_for_categories(self, category_a_node, category_b_node):
        """두 카테고리를 위한 그룹 요약을 생성합니다."""
        system_prompt = """두 카테고리를 포괄하는 그룹 요약을 작성하라.
요구사항:
- 두 카테고리의 공통점과 특징을 설명
- 50자 내외의 간결한 설명
- "에 관한 카테고리 그룹입니다" 형태로 마무리"""
        
        prompt = f"""카테고리 A: {category_a_node.topic}
설명: {category_a_node.summary}

카테고리 B: {category_b_node.topic}
설명: {category_b_node.summary}"""
        
        try:
            result = await self.ai_manager.call_ai_async_single(prompt, system_prompt)
            return result.strip()
        except Exception as e:
            if self.debug:
                print(f">>>> [ERROR] 그룹 요약 생성 오류: {e}")
            return f"{category_a_node.topic}과 {category_b_node.topic}에 관한 카테고리 그룹입니다."
    
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
                most_similar_leaf.conversation_indices.append(conversation_index)
                
                # 요약 업데이트
                most_similar_leaf.summary = await self._update_summary_with_merge(
                    most_similar_leaf.summary, conversation[0]['content'], conversation[1]['content']
                )
                
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
        all_conversations = []

        def collect_recursive(current_node_id: str):
            node = self.memory_manager.get_node(current_node_id)
            if not node:
                return

            # 현재 노드의 대화들 추가
            for conv_idx in node.conversation_indices:
                conversation = self.memory_manager.get_conversation_by_index(conv_idx)
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
            if self.debug:
                print(f"부모 요약이 너무 길어 AI 요약 적용 (길이: {len(combined)} > {max_length})")

            # AI를 사용하여 긴 요약을 압축
            ai_summary_prompt = f"""
            다음은 '{parent_topic}'에 대한 여러 자식 노드들의 요약을 결합한 내용입니다:

            {combined}

            이 내용을 바탕으로 '{parent_topic}'의 전체 내용을 잘 대표하는 간결한 요약을 {max_length}자 이내로 작성해주세요.
            중요한 세부사항을 유지하면서도 불필요한 부분을 제거하여 핵심 내용만 포함해주세요.
            """

            try:
                ai_summarized = await self.ai_manager.call_ai_async_single(ai_summary_prompt, "부모 노드 요약 생성")
                combined = ai_summarized.strip()

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
