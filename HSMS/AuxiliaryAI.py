import asyncio
from config import *
from .AIManager import AIManager
from .MemoryNode import MemoryNode


class AuxiliaryAI:
    """보조 인공지능 - 계층적 기억 관리 시스템의 핵심 컨트롤러"""
    
    def __init__(self, memory_manager, debug=False):
        self.memory_manager = memory_manager
        self.ai_manager = AIManager()
        self.debug = debug  # 디버그 모드 활성화 여부
    
    async def handle_conversation(self, conversation):
        """새로운 대화를 처리하고 적절한 노드에 저장합니다."""
        # 1. 전체 기록에 저장
        conversation_index = self.memory_manager.save_to_all_memory(conversation)
        
        # 2. 사용자 입력 분석
        user_input = conversation[0]['content']
        
        # 3. AI 기반 다중 카테고리 분류 및 처리
        try:
            loop = asyncio.get_running_loop()
            # 디버그 모드일 때는 await로 완료를 기다림
            if self.debug:
                await self._process_conversation_with_ai_classification(conversation, conversation_index)
            else:
                # 일반 모드일 때는 백그라운드 실행
                task = loop.create_task(self._process_conversation_with_ai_classification(conversation, conversation_index))
        except RuntimeError:
            # 이벤트 루프가 없으면 새로 생성
            await self._process_conversation_with_ai_classification(conversation, conversation_index)
    
    async def _process_conversation_with_ai_classification(self, conversation, conversation_index):
        """AI를 사용하여 대화를 분류하고 적절한 노드들에 저장합니다."""
        user_input = conversation[0]['content']
        
        if self.debug:
            print(f"\n>> [AUX] AI 분류 시작")
            print(f">>>> [AUX] 입력: '{user_input[:40]}{'...' if len(user_input) > 40 else ''}'")
            print(f">>>> [AUX] 대화 인덱스: {conversation_index}")
        
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
                    print(f">>>> [AUX] 관련 카테고리: {relevant_cats}")
                else:
                    print(f">>>> [AUX] 관련 카테고리 없음")
            
            # 3. 관련된 카테고리가 있으면 해당 카테고리별로 대화 내용 분리
            if any(category_relevance.values()):
                await self._process_multiple_categories(conversation, conversation_index, category_relevance, existing_categories)
            else:
                # 4. 기존 카테고리와 관련 없으면 새 카테고리 생성
                if self.debug:
                    print(f">>>> [AUX] 새 카테고리 생성 필요")
                await self._create_new_category_and_node(conversation, conversation_index)
        else:
            # 기존 카테고리가 없으면 새 카테고리 생성
            if self.debug:
                print(f">>>> [AUX] 첫 번째 카테고리 생성")
            await self._create_new_category_and_node(conversation, conversation_index)
        
        if self.debug:
            print(f">> [AUX] AI 분류 완료")
            
            # 저장 결과 요약
            recent_nodes = []
            for node in self.memory_manager.memory_tree.values():
                if hasattr(node, 'coordinates'):
                    if (node.coordinates.get('start') == conversation_index and 
                        node.coordinates.get('end') == conversation_index):
                        recent_nodes.append(node)
            
            if recent_nodes:
                print(f">> [AUX] 생성된 노드: {len(recent_nodes)}개")
                for node in recent_nodes[:3]:  # 최대 3개만 표시
                    print(f">>>> [AUX]   - '{node.topic}' ({node.coordinates.get('start')}-{node.coordinates.get('end')})")
                if len(recent_nodes) > 3:
                    print(f">>>> [AUX]   ... 외 {len(recent_nodes)-3}개")
    
    async def _get_existing_categories(self):
        """기존에 존재하는 카테고리 노드들을 가져옵니다."""
        categories = {}
        root_node = self.memory_manager.get_root_node()
        
        if not root_node:
            return categories
        
        for child_id in root_node.children_ids:
            child_node = self.memory_manager.get_node(child_id)
            if child_node and child_node.coordinates["start"] == -1:  # 카테고리 노드
                categories[child_node.topic] = child_node.summary
        
        return categories
    
    async def _check_category_relevance_async(self, user_input, categories):
        """기존 카테고리들과 사용자 입력의 관련성을 AI로 비동기 병렬 판단합니다."""
        system_prompt = """당신은 사용자의 대화 내용이 특정 카테고리와 관련이 있는지 판단하는 전문가입니다.

사용자의 대화를 분석하고, 주어진 카테고리와의 관련성을 정확히 판단하세요.
단순히 단어가 포함되어 있다고 관련이 있는 것이 아니라, 실제 대화의 주제와 내용을 고려해야 합니다.

반드시 "True" (관련 있음) 또는 "False" (관련 없음)로만 답하세요."""
        
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
            print(f">> [CATEGORY] 카테고리 관련성 판단 ({len(categories)}개)")
            for name, desc in categories.items():
                print(f">>>> [CATEGORY]   '{name}': {desc[:30]}...")
            print(f">> [CATEGORY] AI 병렬 판단 시작...")
        
        try:
            # 여러 API 키를 사용한 병렬 처리
            results = await self.ai_manager.call_ai_async_multiple(
                queries, system_prompt, fine=CATEGORY_RELEVANCE_FINE
            )
            
            if self.debug:
                print(f">> [CATEGORY] 병렬 판단 완료")
            
            # 결과 파싱
            relevance = {}
            for i, result in enumerate(results):
                category_name = category_names[i]
                value = result.strip().lower()
                relevance[category_name] = value in ['true', '참', 'yes']
                if self.debug and relevance[category_name]:
                    print(f">>>> [CATEGORY] 관련: '{category_name}'")
            
            if self.debug:
                relevant_count = sum(relevance.values())
                print(f">> [CATEGORY] 최종 결과: {relevant_count}/{len(categories)}개 관련")
            
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
                print(f">> [DEBUG] 단일 카테고리 처리: '{relevant_categories[0]}'")
            await self._process_single_category(conversation, conversation_index, relevant_categories[0])
        else:
            # 다중 카테고리인 경우 - 대화 내용을 분리
            if self.debug:
                print(f">> [DEBUG] 다중 카테고리 대화 분리 시작...")
                print(f">> [DEBUG] 원본 대화를 {len(relevant_categories)}개 카테고리로 분리:")
                for i, cat in enumerate(relevant_categories, 1):
                    print(f">> [DEBUG]   {i}. '{cat}' 카테고리")
            await self._process_multi_category_conversation(conversation, conversation_index, relevant_categories)
    
    async def _process_single_category(self, conversation, conversation_index, category_name):
        """단일 카테고리에 대한 대화를 처리합니다."""
        if self.debug:
            print(f">> [DEBUG] === '{category_name}' 카테고리 처리 시작 ===")
            print(f">> [DEBUG] 처리할 대화:")
            print(f">> [DEBUG]   사용자: {conversation[0]['content']}")
            print(f">> [DEBUG]   AI: {conversation[1]['content']}")
        
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
            self.memory_manager.save_tree()
            if self.debug:
                print(f">> 새 노드 생성 완료:")
                print(f">> [DEBUG]   노드 ID: {new_node.node_id}")
                print(f">> [DEBUG]   주제: '{new_node.topic}'")
                print(f">> [DEBUG]   부모: '{category_name}' 카테고리")
                print(f">> [DEBUG]   대화 인덱스: {new_node.conversation_indices}")
        else:
            # 기존 노드에 추가
            if self.debug:
                print(f">> 기존 주제로 판단 - 기존 노드 또는 새 노드에 추가")
            relevant_child = await self._find_relevant_child_node_async(category_node, user_input)
            if relevant_child:
                if self.debug:
                    print(f"|| 기존 노드에 추가:")
                    print(f">> [DEBUG]   대상 노드 ID: {relevant_child.node_id}")
                    print(f">> [DEBUG]   노드 주제: '{relevant_child.topic}'")
                await self.update_node_and_parents(relevant_child, conversation, conversation_index)
                if self.debug:
                    print(f">> 완료: 노드 업데이트 완료")
            else:
                # 관련 하위 노드가 없으면 새로운 노드 생성
                if self.debug:
                    print(f"|| 해결: 관련 하위 노드를 찾을 수 없음 - 새 노드 생성")
                new_node = await self._create_new_node_async(category_node, user_input, conversation, conversation_index)
                # 새로운 방식: conversation_indices에 대화 추가
                new_node.add_conversation(conversation_index)
                # 부모 카테고리에도 대화 추가
                category_node.add_conversation(conversation_index)
                self.memory_manager.save_tree()
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
            print(f">> [DEBUG] === 대화 내용 분리 시작 ===")
            print(f">> [DEBUG] 분리할 카테고리: {relevant_categories}")
            print(f">> [DEBUG] 원본 사용자 입력: {user_input}")
            print(f">> [DEBUG] 원본 AI 응답: {ai_response}")
        
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
        system_prompt = """당신은 대화 내용을 주제별로 분리하는 전문가입니다.

사용자의 대화와 AI의 응답을 분석하여, 각 카테고리와 관련된 부분만을 추출하세요.
한 대화에서 여러 주제가 다뤄질 수 있으므로, 각 카테고리에 해당하는 내용만 정확히 분리하세요.

출력 형식:
카테고리명:
사용자: [해당 카테고리와 관련된 사용자 발언 부분]
AI: [해당 카테고리와 관련된 AI 응답 부분]

카테고리명:
사용자: [해당 카테고리와 관련된 사용자 발언 부분]
AI: [해당 카테고리와 관련된 AI 응답 부분]
..."""
        
        categories_list = ", ".join(categories)
        prompt = f"""관련 카테고리들: {categories_list}

사용자 발언: {user_input}
AI 응답: {ai_response}

위 대화를 각 카테고리별로 관련된 부분만 분리하여 출력하세요."""
        
        if self.debug:
            print(f">> [DEBUG] === AI에게 대화 분리 요청 ===")
            print(f">> [DEBUG] 분리 대상 카테고리: {categories_list}")
            print(f"|| 요청중: AI 분리 요청 시작...")
        
        try:
            result = await self.ai_manager.call_ai_async_single(prompt, system_prompt, fine=CONVERSATION_SEPARATION_FINE)
            
            if self.debug:
                print(f">> [DEBUG] AI 분리 결과:")
                print(f">> [DEBUG]\n{result}")
                print(f">> [DEBUG] === 분리 결과 파싱 시작 ===")
            
            # 결과 파싱
            separated = {}
            current_category = None
            current_user = ""
            current_ai = ""
            
            for line in result.strip().split('\n'):
                line = line.strip()
                if line.endswith(':') and line[:-1] in categories:
                    # 이전 카테고리 저장
                    if current_category:
                        separated[current_category] = {
                            'user': current_user,
                            'ai': current_ai
                        }
                        if self.debug:
                            print(f"|| 파싱완료: '{current_category}': 사용자='{current_user}', AI='{current_ai}'")
                    # 새 카테고리 시작
                    current_category = line[:-1]
                    current_user = ""
                    current_ai = ""
                    if self.debug:
                        print(f">> [DEBUG] 새 카테고리 시작: '{current_category}'")
                elif line.startswith('사용자:'):
                    current_user = line[4:].strip()
                elif line.startswith('AI:'):
                    current_ai = line[3:].strip()
            
            # 마지막 카테고리 저장
            if current_category:
                separated[current_category] = {
                    'user': current_user,
                    'ai': current_ai
                }
            
            return separated
        except Exception as e:
            print(f"|| 오류: 대화 분리 중 오류: {e}")
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
            print(f">> 완료: 카테고리 노드 생성 완료 (ID: {category_node.node_id})")
        
        # 카테고리 하위에 실제 대화 노드 생성
        new_node = await self._create_new_node_async(category_node, user_input, conversation, conversation_index)
        # 새로운 방식: conversation_indices에 대화 추가
        new_node.add_conversation(conversation_index)
        # 부모 카테고리에도 대화 추가
        category_node.add_conversation(conversation_index)
        self.memory_manager.save_tree()
        
        if self.debug:
            print(f">> 완료: 하위 노드 생성 완료 (ID: {new_node.node_id}, 주제: '{new_node.topic}')")
            print(f">>>> [DEBUG] 카테고리 대화 목록: {category_node.conversation_indices}")
            print(f">>>> [DEBUG] 노드 대화 목록: {new_node.conversation_indices}")
    
    async def _generate_category_name_async(self, user_input):
        """AI를 사용하여 새로운 카테고리명을 생성합니다."""
        system_prompt = """당신은 대화 내용을 분석하여 적절한 카테고리명을 생성하는 전문가입니다.

사용자의 대화 내용을 분석하고, 이 대화가 속할 수 있는 가장 적절한 카테고리명을 생성하세요.
카테고리명은 간결하고 포괄적이어야 하며, 2-8글자 정도로 작성하세요.

예시:
- 컴퓨터, SSD에 대한 대화 → "기술"
- 인류 역사에 대한 대화 → "역사"
- 게임에 대한 대화 → "게임"
- 여행 이야기 → "여행"

단 하나의 카테고리명만 출력하세요."""
        
        prompt = f"사용자 대화: {user_input}\n\n이 대화에 적합한 카테고리명을 생성하세요."
        
        try:
            result = await self.ai_manager.call_ai_async_single(prompt, system_prompt)
            category_name = result.strip()
            
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
            print(f"|| 요청중: AI에게 새 주제 여부 판단 요청:")
            print(f">> [DEBUG]   부모 카테고리: '{parent_node.topic}'")
            print(f">> [DEBUG]   사용자 입력: {user_input[:100]}{'...' if len(user_input) > 100 else ''}")
        
        system_prompt = """당신은 새로운 대화가 기존 노드의 하위 주제인지, 완전히 새로운 주제인지 판단하는 전문가입니다.
반드시 "True" (새로운 주제) 또는 "False" (기존 주제의 하위)로만 답하세요."""
        
        prompt = f"부모 노드 주제: {parent_node.topic}\n새로운 대화: {user_input}"
        
        try:
            result = await self.ai_manager.call_ai_async_single(prompt, system_prompt, fine=NEW_TOPIC_FINE)
            is_new_topic = result.strip() == 'True'
            
            if self.debug:
                status = "|| 새로운 주제" if is_new_topic else "|| 기존 주제"
                print(f">> [DEBUG] AI 판단 결과: {status} (응답: '{result.strip()}')")
            
            return is_new_topic
        except Exception as e:
            if self.debug:
                print(f"|| 오류: 새 주제 판단 중 오류: {e} - 기본값으로 새 주제 처리")
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
        
        system_prompt = """당신은 사용자 질문과 기존 노드의 관련성을 판단하는 전문가입니다.
주제와 요약을 보고 사용자 질문과 관련이 있는지 판단하세요.
"True" (관련 있음) 또는 "False" (관련 없음)로만 답하세요."""
        
        try:
            results = await self.ai_manager.call_ai_async_multiple(
                relevance_queries, system_prompt
            )
            
            # 가장 관련성이 높은 노드 반환
            for i, result in enumerate(results):
                if result.strip() == 'True':
                    return child_nodes[i]
            
            return None
        except Exception as e:
            print(f"관련 자식 노드 찾기 중 오류: {e}")
            return None
    
    async def _create_new_node_async(self, parent_node, user_input, conversation, conversation_index):
        """AI를 사용하여 새로운 노드를 비동기로 생성합니다."""
        user_content = conversation[0]['content']
        ai_content = conversation[1]['content']
        
        # AI 기반 주제 추출
        topic_system_prompt = """당신은 대화에서 핵심 주제를 추출하는 전문가입니다.
사용자의 입력과 AI의 응답을 분석하여 간결하고 명확한 주제명을 생성하세요.
주제명은 2-10글자 정도로 간단하고 구체적이어야 합니다.

예시:
- 사과에 대한 대화 → "사과"
- SSD 작동 원리 → "SSD"
- 인류 역사 → "인류 역사"
- 학교 이야기 → "학교"

대화의 실제 내용과 맥락을 정확히 반영하는 주제명을 만드세요."""
        
        topic_prompt = f"사용자: {user_content}\nAI: {ai_content}\n\n위 대화의 핵심 주제를 간결하게 추출하세요."
        
        # 요약 생성
        summary_system_prompt = """당신은 대화 내용을 정확하고 포괄적으로 요약하는 전문가입니다.
다음 원칙에 따라 요약하세요:

1. 사용자가 말한 내용과 AI가 응답한 내용을 모두 포함
2. 핵심 주제, 중요한 정보, 구체적인 세부사항을 놓치지 않기
3. 대화의 맥락과 흐름을 유지
4. 요약문에는 따옴표("), 백슬래시(\), 작은따옴표(')를 사용하지 않기
5. 간결하면서도 완전한 정보를 담기

형식: "사용자가 [사용자 내용 요약]에 대해 이야기했고, AI는 [AI 응답 요약]로 답변했다."
"""
        
        summary_prompt = f"사용자: {user_content}\nAI: {ai_content}\n\n위 대화를 요약해주세요."
        
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
        system_prompt = """당신은 기존 대화 요약에 새로운 대화 내용을 통합하는 전문가입니다.
다음 원칙에 따라 요약을 업데이트하세요:

1. 기존 요약의 내용을 유지하면서 새로운 내용을 자연스럽게 통합
2. 사용자 발언과 AI 응답을 모두 포함
3. 중복되는 내용은 간결하게 정리
4. 새로운 정보나 주제 전개를 명확히 반영
5. 요약문에는 따옴표("), 백슬래시(\), 작은따옴표(')를 사용하지 않기

최종 요약은 전체 대화 흐름을 이해할 수 있도록 작성하세요.
"""
        
        user_content = conversation[0]['content']
        ai_content = conversation[1]['content']
        
        prompt = f"""기존 요약: {node.summary}

새로운 대화:
사용자: {user_content}
AI: {ai_content}

기존 요약에 새로운 대화를 통합하여 업데이트된 요약을 작성해주세요."""
        
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
        system_prompt = """당신은 기존 대화 요약에 새로운 대화 내용을 통합하는 전문가입니다.
다음 원칙에 따라 요약을 업데이트하세요:

1. 기존 요약의 내용을 유지하면서 새로운 내용을 자연스럽게 통합
2. 사용자 발언과 AI 응답을 모두 포함
3. 중복되는 내용은 간결하게 정리
4. 새로운 정보나 주제 전개를 명확히 반영
5. 요약문에는 따옴표("), 백슬래시(\), 작은따옴표(')를 사용하지 않기

최종 요약은 전체 대화 흐름을 이해할 수 있도록 작성하세요.
"""
        
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
        
        system_prompt = """당신은 부모 노드의 요약을 업데이트하는 전문가입니다.
중요한 규칙:
1. 부모 노드의 주제와 관련된 내용만 포함하세요
2. 자식 노드의 주제와 무관한 내용은 절대 포함하지 마세요
3. 부모 노드의 원래 주제 맥락을 유지하세요
4. 간결하고 핵심적인 요약만 작성하세요"""
        
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

부모 노드 '{parent_node.topic}'의 주제와 직접 관련된 내용만으로 요약을 업데이트하세요. 
다른 주제의 내용은 포함하지 마세요."""
        
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
        
        system_prompt = "당신은 대화 내용을 정확하고 간결하게 요약하는 전문가입니다. 핵심 정보를 놓치지 않으면서도 읽기 쉬운 요약을 작성해주세요."
        
        try:
            # Generate multiple summaries using different perspectives
            results = await self.ai_manager.call_ai_async_multiple(queries, system_prompt)
            
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
            
            부모 노드 '{parent_node.topic}'의 주제와 직접 관련된 내용만으로 요약을 업데이트하세요.
            자식 노드의 변화를 반영하되, 부모 노드의 원래 주제 맥락을 유지하세요.
            """,
            f"""
            {base_content}
            
            부모 노드의 전체적인 구조와 하위 주제들을 고려하여 포괄적인 요약을 만들어주세요.
            새로 추가된 자식 노드의 내용을 자연스럽게 통합하세요.
            """,
            f"""
            {base_content}
            
            부모 노드의 핵심 주제에 집중하여 간결하고 명확한 요약을 작성해주세요.
            자식 노드와 무관한 내용은 절대 포함하지 마세요.
            """
        ]
        
        system_prompt = """당신은 계층적 메모리 구조에서 부모 노드의 요약을 업데이트하는 전문가입니다.
다음 원칙을 따르세요:
1. 부모 노드의 주제와 직접 관련된 내용만 포함
2. 자식 노드의 주제와 무관한 내용은 절대 포함하지 마세요
3. 부모 노드의 원래 주제 맥락을 유지하세요
4. 간결하고 핵심적인 요약만 작성하세요"""
        
        try:
            # Generate multiple summaries using different perspectives
            results = await self.ai_manager.call_ai_async_multiple(queries, system_prompt)
            
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
