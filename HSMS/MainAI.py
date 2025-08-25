import asyncio
from config import (API_KEY, LOAD_API_KEYS, GEMINI_MODEL, MEMORY_SEARCH_FINE, ALL_MEMORY)
from .MemoryManager import MemoryManager
from .AuxiliaryAI import AuxiliaryAI
from .AIManager import AIManager


class MainAI:
    """메인 인공지능 - 사용자와 직접 대화하는 주체"""
    
    def __init__(self, force_search=False, force_record=False, debug=False, max_depth=4, top_search_n=0, no_record=False):
        self.debug = debug
        self.memory_manager = MemoryManager(debug=self.debug)
        self.auxiliary_ai = AuxiliaryAI(self.memory_manager, debug=self.debug, max_depth=max_depth, top_search_n=top_search_n)
        self.ai_manager = AIManager(debug=self.debug)
        
        self.force_search = force_search
        self.force_record = force_record
        self.no_record = no_record
        self.max_depth = max_depth
        self.top_search_n = top_search_n
        
        if self.force_search and self.force_record:
            raise ValueError("--force-search와 --force-record는 동시에 사용할 수 없습니다.")
        if self.force_record and self.no_record:
            raise ValueError("--force-record와 --no-record는 동시에 사용할 수 없습니다.")

    def set_max_depth(self, new_depth):
        """최대 트리 깊이를 동적으로 설정합니다."""
        self.max_depth = new_depth
        self.auxiliary_ai.max_depth = new_depth
        if self.debug:
            print(f">> [CONFIG] max_depth가 {new_depth}로 변경되었습니다.")

    def set_debug_mode(self, is_debug):
        """디버그 모드를 동적으로 설정합니다."""
        self.debug = is_debug
        self.memory_manager.debug = is_debug
        self.auxiliary_ai.debug = is_debug
        self.ai_manager.debug = is_debug
        print(f">> [CONFIG] 디버그 모드가 {'ON' if is_debug else 'OFF'}으로 설정되었습니다.")
    
    async def chat_async(self, user_input):
        """사용자와 채팅합니다 (비동기 버전)."""
        if self.debug:
            print(f"\n=============================================================")
            print(f"| [MAIN] 대화 시작")
            print(f"| 입력: '{user_input[:50]}{'...' if len(user_input) > 50 else ''}'")
        
        # force_record 모드인 경우 AI 응답 없이 기록만 수행
        if self.force_record:
            if self.debug:
                print(f"| 모드: 기록 전용")
                print(f"=============================================================")
                print("+- [RECORD-ONLY] 기록 전용 모드 실행")
            
            # AI 응답 없는 대화 생성
            conversation = [
                {"role": "user", "content": user_input},
                {"role": "assistant", "content": ""}  # 빈 응답
            ]
            
            # 기억 시스템에만 저장
            await self.auxiliary_ai.handle_conversation(conversation)
            
            if self.debug:
                print("+- [RECORD-ONLY] 기록 전용 모드 완료")
            
            return ""  # 빈 응답 반환
        
        # 디버그 모드 활성화시 구분선 표시
        if self.debug:
            print(f"| 모드: {'강제 검색' if self.force_search else '일반 대화'}")
            print(f"=============================================================")
        
        # 1. 기억 필요 여부 확인 (AI 기반 판단)
        if self.force_search:
            need_memory = True
            if self.debug:
                print("+- [MEMORY-SEARCH] 기억 검색 단계 (강제 모드)")
        else:
            need_memory = await self._needs_memory_search_async(user_input)
            if self.debug:
                print(f"+- [MEMORY-SEARCH] 기억 검색 단계")
                print(f"|  필요 여부: {'예' if need_memory else '아니오'}")
        
        # 2. 기억 검색 (필요한 경우만)
        relevant_data = ""
        if need_memory:
            relevant_data = await self.auxiliary_ai.search_relevant_memories(user_input)
        
        if self.debug:
            print(f"+- [MEMORY-SEARCH] 기억 검색 완료")
            print()
            print("+- [RESPONSE] 응답 생성 단계")
        
        # 3. 응답 생성 (기억 데이터 포함)
        if relevant_data:
            system_prompt = """사용자와 자연스럽게 대화하라. 
과거 기억을 바탕으로 정확하고 도움이 되는 답변을 제공하라.
답변은 간결하고 친근하게 1-2문장으로 작성하라.
절대로 이모티콘을 사용하지 마라."""
            
            prompt = f"""{relevant_data}

사용자 질문: {user_input}"""
            
            if self.debug:
                print(f"|  유형: 기억 기반 응답")
        else:
            system_prompt = """사용자와 자연스럽게 대화하라. 
정확하고 도움이 되는 답변을 제공하라.
답변은 간결하고 친근하게 1-2문장으로 작성하라.
절대로 이모티콘을 사용하지 마라."""
            prompt = user_input
            
            if self.debug:
                print(f"|  유형: 일반 응답")
        
        # 4. AI 응답 생성
        response = await self.ai_manager.call_ai_async_single(
            prompt, system_prompt
        )
        
        if self.debug:
            response_preview = response[:100].replace('\n', ' ')
            print(f"|  응답 완료: {len(response)}자 (미리보기: {response_preview}...)")
            print(f"+- [RESPONSE] 응답 생성 완료")
            print()
            print("=============================================================")
            print("+- [CONVERSATION-STORAGE] 대화 저장 단계")
        
        # 5. 대화를 기억 시스템에 저장 (비동기 처리, no_record=False일 때만)
        if not self.no_record:
            conversation = [
                {"role": "user", "content": user_input},
                {"role": "assistant", "content": response}
            ]
            
            # handle_conversation을 await로 호출
            await self.auxiliary_ai.handle_conversation(conversation)
            
            if self.debug:
                print(f"+- [CONVERSATION-STORAGE] 대화 저장 완료")
                print("=============================================================")
        elif self.debug:
            print(f"+- [CONVERSATION-STORAGE] 대화 저장을 건너뛰었습니다 (--no-record).")
            print("=============================================================")
        
        return response
    
    def chat(self, user_input):
        """동기 버전의 채팅 함수"""
        return asyncio.run(self.chat_async(user_input))
    
    async def _needs_memory_search_async(self, user_input):
        """AI를 사용하여 해당 입력이 과거 기억을 참조해야 하는지 판단합니다."""
        system_prompt = """사용자의 발언이 과거 대화(기억)를 참고해야 하는지 판단하라.
다음 규칙을 따르라:
- 사용자가 과거에 했던 말, 이전 대화의 맥락을 직접 묻거나 참조하는 경우에는 "True"를 출력하라.
- 단순 정보 요청, 일반 지식 질문, 또는 지금 즉시 대답 가능한 질문은 "False"를 출력하라.
- 출력은 반드시 "True" 또는 "False"로만 하라."""
        
        prompt = f"사용자 발언: '{user_input}'"
        
        if self.debug:
            print(f"│  기억 필요성 판단중...")
        
        result = await self.ai_manager.call_ai_async_single(
            prompt, system_prompt, fine=MEMORY_SEARCH_FINE
        )
        
        return result.strip().lower() == 'true'
    
    def get_tree_status(self):
        """트리 상태 정보를 반환합니다."""
        if not self.memory_manager.memory_tree:
            return {
                'total_nodes': 0,
                'category_count': 0,
                'total_conversations': 0,
                'tree_summary': "빈 트리"
            }
        
        total_nodes = len(self.memory_manager.memory_tree)
        root_node = self.memory_manager.get_root_node()
        
        if not root_node:
            return {
                'total_nodes': total_nodes,
                'category_count': 0,
                'total_conversations': 0,
                'tree_summary': f"총 {total_nodes}개 노드 (루트 없음)"
            }
        
        # 카테고리 노드 수 계산 (루트의 직접 자식들)
        category_count = len(root_node.children_ids)
        
        # 전체 대화 수 계산
        try:
            all_memory = self.memory_manager.data_manager.load_json(ALL_MEMORY)
            total_conversations = len(all_memory)
        except:
            total_conversations = 0
        
        # 트리 요약 생성
        tree_summary = self.memory_manager.get_tree_summary(max_depth=3)
        
        return {
            'total_nodes': total_nodes,
            'category_count': category_count,
            'total_conversations': total_conversations,
            'tree_summary': tree_summary
        }
