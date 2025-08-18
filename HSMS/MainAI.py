import asyncio
from config import *
from .MemoryManager import MemoryManager
from .AuxiliaryAI import AuxiliaryAI
from .AIManager import AIManager


class MainAI:
    """메인 인공지능 - 사용자와 직접 대화하는 주체"""
    
    def __init__(self, force_search=False, debug=False):
        self.memory_manager = MemoryManager()
        self.auxiliary_ai = AuxiliaryAI(self.memory_manager, debug=debug)
        self.ai_manager = AIManager()
        self.force_search = force_search  # 모든 대화에서 기억 호출 강제 여부
        self.debug = debug  # 디버그 모드 활성화 여부
    
    async def chat_async(self, user_input):
        """사용자와 채팅합니다 (비동기 버전)."""
        if self.debug:
            print(f"\n>> [MAIN] 대화 시작: '{user_input[:30]}{'...' if len(user_input) > 30 else ''}'")
        
        # 1. 기억 필요 여부 확인 (AI 기반 판단)
        if self.force_search:
            need_memory = True
            if self.debug:
                print(f">>>> [MAIN] 강제 검색 모드 활성화")
        else:
            need_memory = await self._needs_memory_search_async(user_input)
        
        if self.debug:
            status = "필요" if need_memory else "불필요"
            print(f">>>> [MAIN] 메모리 검색 {status}")
        
        if need_memory:
            # 2. 비동기 병렬 트리 검색
            relevant_data = await self._search_memory_async(user_input)
            
            if self.debug:
                if relevant_data:
                    print(f">>>> [MAIN] 관련 기억 발견: {len(relevant_data)}자 (미리보기: {relevant_data[:50]}...)")
                else:
                    print(f">>>> [MAIN] 관련 기억 없음")
            
            # 3. 응답 생성 (기억 데이터 포함)
            if relevant_data:
                system_prompt = """당신은 사용자와 자연스럽게 대화하는 AI입니다. 
과거 기억을 바탕으로 정확하고 도움이 되는 답변을 제공하세요.
답변은 간결하고 친근하게 1-2문장으로 작성하세요.
절대로 이모티콘을 사용하지 마세요."""
                
                prompt = f"""과거 기억: {relevant_data}

사용자 질문: {user_input}

과거 기억을 참고하여 답변해주세요."""
                
                if self.debug:
                    print(f">> [MAIN] 기억 기반 응답 생성 중...")
            else:
                system_prompt = """당신은 사용자와 자연스럽게 대화하는 AI입니다. 
정확하고 도움이 되는 답변을 제공하세요.
답변은 간결하고 친근하게 1-2문장으로 작성하세요.
절대로 이모티콘을 사용하지 마세요."""
                prompt = user_input
                
                if self.debug:
                    print(f">> [MAIN] 일반 응답 생성 중...")
        else:
            # 기억 검색 없이 단순 응답
            system_prompt = """당신은 사용자와 자연스럽게 대화하는 AI입니다. 
정확하고 도움이 되는 답변을 제공하세요.
답변은 간결하고 친근하게 1-2문장으로 작성하세요.
절대로 이모티콘을 사용하지 마세요."""
            prompt = user_input
            
            if self.debug:
                print(f">> [MAIN] 일반 응답 생성 중...")
        
        # 4. AI 응답 생성
        response = await self.ai_manager.call_ai_async_single(
            prompt, system_prompt
        )
        
        if self.debug:
            print(f">>>> [MAIN] 응답 완료: '{response[:30]}{'...' if len(response) > 30 else ''}'")
        
        # 5. 대화를 기억 시스템에 저장 (비동기 처리)
        conversation = [
            {"role": "user", "content": user_input},
            {"role": "assistant", "content": response}
        ]
        
        if self.debug:
            print(f">> [MAIN] 기억 시스템 저장 시작...")
        
        # handle_conversation을 await로 호출
        await self.auxiliary_ai.handle_conversation(conversation)
        
        if self.debug:
            print(f">> [MAIN] 대화 처리 완료\n")
        
        return response
    
    def chat(self, user_input):
        """동기 버전의 채팅 함수"""
        return asyncio.run(self.chat_async(user_input))
    
    async def _needs_memory_search_async(self, user_input):
        """AI를 사용하여 해당 입력이 과거 기억을 참조해야 하는지 판단합니다."""
        system_prompt = """당신은 사용자의 발언이 과거 대화(기억)를 참고해야 하는지 판단하는 전문가입니다.
다음 규칙을 따르세요:
- 사용자가 과거에 했던 말, 이전 대화의 맥락을 직접 묻거나 참조하는 경우에는 "True"를 출력하세요.
- 단순 정보 요청, 일반 지식 질문, 또는 지금 즉시 대답 가능한 질문은 "False"를 출력하세요.
- 출력은 반드시 "True" 또는 "False"로만 하세요."""
        
        try:
            result = await self.ai_manager.call_ai_async_single(
                user_input,
                system_prompt,
                fine=MEMORY_SEARCH_FINE
            )
            if self.debug:
                print(f">>>> [MEMORY] AI 판단 결과: {result.strip()}")
            return result.strip().lower() == 'true'
        except Exception as e:
            if self.debug:
                print(f"|||| [ERROR] 기억 필요성 판단 오류: {e}")
            return False
    
    async def _search_memory_async(self, query):
        """비동기 병렬 방식으로 기억을 검색합니다."""
        if not self.memory_manager.memory_tree:
            if self.debug:
                print(f">>>> [SEARCH] 메모리 트리가 비어있음")
            return ""
        
        # 모든 노드에 대해 관련성 검사
        nodes = list(self.memory_manager.memory_tree.values())
        
        if not nodes:
            if self.debug:
                print(f">>>> [SEARCH] 검색할 노드가 없음")
            return ""
        
        if self.debug:
            print(f">> [SEARCH] {len(nodes)}개 노드에서 검색 시작...")
        
        # 병렬 관련성 검사
        relevant_nodes = await self._check_nodes_relevance_async(query, nodes)
        
        if not relevant_nodes:
            if self.debug:
                print(f">>>> [SEARCH] 관련 노드를 찾지 못함")
            return ""
        
        if self.debug:
            print(f">>>> [SEARCH] {len(relevant_nodes)}개 관련 노드 발견, 대화 데이터 추출 중...")
        
        # 관련 노드들에서 대화 데이터 추출
        conversation_data = self._extract_conversation_data(relevant_nodes)
        
        if self.debug:
            print(f">> [SEARCH] 검색 완료: {len(conversation_data)}자 데이터 추출")
        
        return conversation_data
    
    async def _check_nodes_relevance_async(self, query, nodes):
        """모든 노드의 관련성을 비동기 병렬로 검사합니다."""
        system_prompt = """당신은 사용자 질문과 기억 노드의 관련성을 판단하는 전문가입니다.
주제와 요약을 보고 사용자 질문과 관련이 있는지 판단하세요.
"True" (관련 있음) 또는 "False" (관련 없음)로만 답하세요."""
        
        # 각 노드에 대한 관련성 검사 쿼리 생성
        queries = []
        for node in nodes:
            node_query = f"사용자 질문: {query}\n노드 주제: {node.topic}\n노드 요약: {node.summary[:200]}"
            queries.append(node_query)
        
        if self.debug:
            print(f">>>> [RELEVANCE] {len(nodes)}개 노드 관련성 병렬 검사 중...")
        
        # 병렬 AI 호출
        results = await self.ai_manager.call_ai_async_multiple(
            queries, system_prompt
        )
        
        # 관련 있는 노드들만 필터링
        relevant_nodes = []
        for i, result in enumerate(results):
            if result and result.strip().lower() == 'true':
                relevant_nodes.append(nodes[i])
                if self.debug:
                    print(f">>>> [RELEVANCE] 관련 노드: '{nodes[i].topic}'")
        
        if self.debug:
            print(f">> [RELEVANCE] 관련성 검사 완료: {len(relevant_nodes)}/{len(nodes)}개 노드 관련")
        
        return relevant_nodes
    
    def _extract_conversation_data(self, nodes):
        """관련 노드들에서 실제 대화 데이터를 추출합니다."""
        all_memory = self.memory_manager.data_manager.load_json(ALL_MEMORY)
        
        if not all_memory:
            return ""
        
        conversation_indices = set()
        
        # 각 노드의 conversation_indices에서 대화 인덱스 추출
        for node in nodes:
            if self.debug:
                print(f">>>> [MEMORY] 노드 '{node.topic}': {len(node.conversation_indices)}개 대화")
            
            # 새로운 방식: conversation_indices 직접 사용
            for idx in node.conversation_indices:
                if 0 <= idx < len(all_memory):
                    conversation_indices.add(idx)
                elif self.debug:
                    print(f">>>> [MEMORY] 경고: 유효하지 않은 대화 인덱스 {idx} (최대: {len(all_memory)-1})")
        
        if self.debug:
            print(f">>>> [MEMORY] 총 {len(conversation_indices)}개 대화 추출됨")
        
        # 인덱스 정렬하여 대화 순서 유지
        sorted_indices = sorted(conversation_indices)
        
        # 해당 대화들을 문자열로 변환
        conversation_texts = []
        for idx in sorted_indices:
            if idx < len(all_memory):
                conv = all_memory[idx]
                if len(conv) >= 2:
                    user_msg = conv[0]['content']
                    ai_msg = conv[1]['content']
                    conversation_texts.append(f"[대화 {idx}]\n사용자: {user_msg}\nAI: {ai_msg}")
        
        if self.debug:
            print(f">>>> [MEMORY] 최종 {len(conversation_texts)}개 대화 텍스트 생성")
        
        return "\n\n".join(conversation_texts)

    def get_tree_status(self):
        """현재 트리 상태를 반환합니다."""
        return {
            'total_nodes': len(self.memory_manager.memory_tree),
            'tree_summary': self.memory_manager.get_tree_summary(),
            'root_node_id': self.memory_manager.root_node_id
        }
