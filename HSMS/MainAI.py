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
        # 1. 기억 필요 여부 확인 (키워드 기반 빠른 판단)
        need_memory = self._needs_memory_search(user_input) or self.force_search
        
        if self.debug:
            print(f"🐛 [DEBUG] 기억 검색 필요: {need_memory}")
            print(f"🐛 [DEBUG] 강제 검색 모드: {self.force_search}")
        
        if need_memory:
            # 2. 비동기 병렬 트리 검색
            if self.debug:
                print(f"🐛 [DEBUG] 메모리 검색 시작...")
            relevant_data = await self._search_memory_async(user_input)
            
            if self.debug:
                if relevant_data:
                    print(f"🐛 [DEBUG] 검색 결과: {len(relevant_data)} 글자의 관련 데이터 발견")
                    print(f"🐛 [DEBUG] 데이터 미리보기: {relevant_data[:100]}...")
                else:
                    print(f"🐛 [DEBUG] 검색 결과: 관련 데이터 없음")
            
            # 3. 응답 생성 (기억 데이터 포함)
            if relevant_data:
                system_prompt = """당신은 사용자와 자연스럽게 대화하는 AI입니다. 
과거 기억을 바탕으로 정확하고 도움이 되는 답변을 제공하세요.
답변은 간결하고 친근하게 1-2문장으로 작성하세요."""
                
                prompt = f"""과거 기억: {relevant_data}

사용자 질문: {user_input}

과거 기억을 참고하여 답변해주세요."""
            else:
                system_prompt = """당신은 사용자와 자연스럽게 대화하는 AI입니다. 
정확하고 도움이 되는 답변을 제공하세요.
답변은 간결하고 친근하게 1-2문장으로 작성하세요."""
                prompt = user_input
        else:
            # 기억 검색 없이 단순 응답
            system_prompt = """당신은 사용자와 자연스럽게 대화하는 AI입니다. 
정확하고 도움이 되는 답변을 제공하세요.
답변은 간결하고 친근하게 1-2문장으로 작성하세요."""
            prompt = user_input
        
        # 4. AI 응답 생성
        response = await self.ai_manager.call_ai_async_single(
            prompt, system_prompt
        )
        
        # 5. 대화를 기억 시스템에 저장 (비동기 처리)
        conversation = [
            {"role": "user", "content": user_input},
            {"role": "assistant", "content": response}
        ]
        # handle_conversation을 await로 호출
        await self.auxiliary_ai.handle_conversation(conversation)
        
        return response
    
    def chat(self, user_input):
        """동기 버전의 채팅 함수"""
        return asyncio.run(self.chat_async(user_input))
    
    def _needs_memory_search(self, user_input):
        """기억 검색이 필요한지 키워드 기반으로 빠르게 판단합니다."""
        memory_keywords = [
            '저번', '이전', '전에', '예전', '과거', '했었', '말했', '얘기했', 
            '기억', '알려줬', '추천', '뭐였', '무엇이었', '어떤것', '내가', 
            '우리가', '그때', '언제', '누구', '어디', '왜', '어떻게'
        ]
        
        # fine-tuning 데이터를 사용한 AI 기반 판단
        system_prompt = """당신은 사용자의 질문이 과거 기억을 필요로 하는지 판단하는 전문가입니다.
"True" (기억 필요) 또는 "False" (기억 불필요)로만 답하세요."""
        
        result = self.ai_manager.call_ai(
            prompt=user_input,
            system=system_prompt,
            fine=JUDGEFINE
        )
        
        return result.strip() == 'True'
    
    async def _search_memory_async(self, query):
        """비동기 병렬 방식으로 기억을 검색합니다."""
        if not self.memory_manager.memory_tree:
            return ""
        
        # 모든 노드에 대해 관련성 검사
        nodes = list(self.memory_manager.memory_tree.values())
        
        if not nodes:
            return ""
        
        # 병렬 관련성 검사
        relevant_nodes = await self._check_nodes_relevance_async(query, nodes)
        
        if not relevant_nodes:
            return ""
        
        # 관련 노드들에서 대화 데이터 추출
        conversation_data = self._extract_conversation_data(relevant_nodes)
        
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
        
        # 진행 상황 표시
        print(f"🔍 {len(nodes)}개 노드 검색 중...")
        
        # 병렬 AI 호출
        results = await self.ai_manager.call_ai_async_multiple(
            queries, system_prompt, fine=ISSAMEFINE
        )
        
        # 관련 있는 노드들만 필터링
        relevant_nodes = []
        for i, result in enumerate(results):
            if result.strip() == 'True':
                relevant_nodes.append(nodes[i])
        
        print(f"✅ {len(relevant_nodes)}개 관련 노드 발견")
        return relevant_nodes
    
    def _check_node_relevance(self, query, node):
        """단일 노드의 관련성을 검사합니다 (동기 버전)."""
        system_prompt = """당신은 사용자 질문과 기억 노드의 관련성을 판단하는 전문가입니다.
주제와 요약을 보고 사용자 질문과 관련이 있는지 판단하세요.
"True" (관련 있음) 또는 "False" (관련 없음)로만 답하세요."""
        
        prompt = f"사용자 질문: {query}\n노드 주제: {node.topic}\n노드 요약: {node.summary[:200]}"
        
        result = self.ai_manager.call_ai(
            prompt=prompt, 
            system=system_prompt, 
            fine=ISSAMEFINE
        )
        
        return result.strip() == 'True'
    
    def _extract_conversation_data(self, nodes):
        """관련 노드들에서 실제 대화 데이터를 추출합니다."""
        all_memory = self.memory_manager.data_manager.load_json(ALL_MEMORY)
        
        if not all_memory:
            return ""
        
        conversation_indices = set()
        
        # 각 노드의 좌표에서 대화 인덱스 추출
        for node in nodes:
            start = node.coordinates.get("start", 0)
            end = node.coordinates.get("end", 0)
            
            # 카테고리 노드는 제외
            if start == -1 or end == -1:
                continue
            
            # 해당 범위의 모든 인덱스 추가
            for i in range(start, min(end + 1, len(all_memory))):
                conversation_indices.add(i)
        
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
                    conversation_texts.append(f"사용자: {user_msg}\nAI: {ai_msg}")
        
        return "\n\n".join(conversation_texts)

    def get_tree_status(self):
        """현재 트리 상태를 반환합니다."""
        return {
            'total_nodes': len(self.memory_manager.memory_tree),
            'tree_summary': self.memory_manager.get_tree_summary(),
            'root_node_id': self.memory_manager.root_node_id
        }
