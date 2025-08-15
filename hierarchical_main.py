import json
import os
import google.generativeai as genai
import concurrent.futures
import time
import uuid
import asyncio
import argparse
import random
from google.api_core.exceptions import ResourceExhausted
from config import *


class DataManager:
    """데이터 관리를 담당하는 클래스 - 파일 입출력 및 메모리 관리"""
    
    @staticmethod
    def load_json(file):
        if os.path.exists(file):
            with open(file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return []

    @staticmethod
    def save_json(file, data):
        folder = os.path.dirname(file)
        if folder and not os.path.exists(folder):
            os.makedirs(folder, exist_ok=True)
        with open(file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

    @staticmethod
    def history_str(buf):
        s = ''
        for it in buf:
            if isinstance(it, list):
                for sub in it:
                    s += f"{sub['role']}: {sub['content']}\n"
            elif isinstance(it, dict):
                s += f"{it['role']}: {it['content']}\n"
        return s


class MemoryNode:
    """계층적 기억 시스템의 개별 노드를 나타내는 클래스"""
    
    def __init__(self, node_id=None, topic=None, summary=None, parent_id=None, 
                 children_ids=None, coordinates=None, references=None):
        self.node_id = node_id or str(uuid.uuid4())
        self.topic = topic or ""
        self.summary = summary or ""
        self.parent_id = parent_id
        self.children_ids = children_ids or []
        self.coordinates = coordinates or {"start": 0, "end": 0}
        self.references = references or []  # 다른 노드에 대한 참조 저장
    
    def to_dict(self):
        return {
            'node_id': self.node_id,
            'topic': self.topic,
            'summary': self.summary,
            'parent_id': self.parent_id,
            'children_ids': self.children_ids,
            'coordinates': self.coordinates,
            'references': self.references
        }
    
    @classmethod
    def from_dict(cls, data):
        return cls(
            node_id=data.get('node_id'),
            topic=data.get('topic'),
            summary=data.get('summary'),
            parent_id=data.get('parent_id'),
            children_ids=data.get('children_ids', []),
            coordinates=data.get('coordinates', {"start": 0, "end": 0}),
            references=data.get('references', [])
        )


class MemoryManager:
    """계층적 기억 트리를 관리하는 클래스"""
    
    def __init__(self):
        self.data_manager = DataManager()
        self.memory_tree = {}  # node_id를 키로 하는 노드 딕셔너리
        self.root_node_id = None
        self.initialize_tree()
    
    def initialize_tree(self):
        """트리 구조를 초기화하거나 로드합니다."""
        if os.path.exists(HIERARCHICAL_MEMORY):
            tree_data = self.data_manager.load_json(HIERARCHICAL_MEMORY)
            if tree_data:
                # 기존 트리 로드
                self.memory_tree = {}
                for node_data in tree_data.get('nodes', []):
                    node = MemoryNode.from_dict(node_data)
                    self.memory_tree[node.node_id] = node
                self.root_node_id = tree_data.get('root_node_id')
            else:
                self._create_initial_tree()
        else:
            self._create_initial_tree()
    
    def _create_initial_tree(self):
        """초기 루트 노드를 생성합니다."""
        root_node = MemoryNode(
            topic="ROOT",
            summary="최상위 루트 노드"
        )
        self.memory_tree[root_node.node_id] = root_node
        self.root_node_id = root_node.node_id
        self.save_tree()
    
    def save_tree(self):
        """트리를 파일에 저장합니다."""
        tree_data = {
            'root_node_id': self.root_node_id,
            'nodes': [node.to_dict() for node in self.memory_tree.values()]
        }
        self.data_manager.save_json(HIERARCHICAL_MEMORY, tree_data)
    
    def get_node(self, node_id):
        """노드 ID로 노드를 가져옵니다."""
        return self.memory_tree.get(node_id)
    
    def get_root_node(self):
        """루트 노드를 가져옵니다."""
        return self.memory_tree.get(self.root_node_id)
    
    def add_node(self, node, parent_id=None):
        """새 노드를 트리에 추가합니다."""
        self.memory_tree[node.node_id] = node
        if parent_id and parent_id in self.memory_tree:
            parent_node = self.memory_tree[parent_id]
            if node.node_id not in parent_node.children_ids:
                parent_node.children_ids.append(node.node_id)
            node.parent_id = parent_id
        self.save_tree()
    
    def update_node(self, node_id, **kwargs):
        """노드 정보를 업데이트합니다."""
        if node_id in self.memory_tree:
            node = self.memory_tree[node_id]
            for key, value in kwargs.items():
                if hasattr(node, key):
                    setattr(node, key, value)
            self.save_tree()
    
    def get_tree_summary(self, max_depth=3):
        """트리 구조의 요약을 생성합니다."""
        if not self.root_node_id:
            return "빈 트리"
        
        def build_summary(node_id, depth=0, max_depth=max_depth):
            if depth > max_depth or node_id not in self.memory_tree:
                return ""
            
            node = self.memory_tree[node_id]
            indent = "  " * depth
            summary = f"{indent}- {node.topic}: {node.summary[:50]}...\n"
            
            for child_id in node.children_ids:
                if child_id in self.memory_tree:
                    summary += build_summary(child_id, depth + 1, max_depth)
            
            return summary
        
        return build_summary(self.root_node_id)
    
    def save_to_all_memory(self, conversation):
        """대화를 전체 기록에 저장합니다."""
        mem = self.data_manager.load_json(ALL_MEMORY)
        mem.append(conversation)
        self.data_manager.save_json(ALL_MEMORY, mem)
        return len(mem) - 1  # 저장된 대화의 인덱스 반환


class AIManager:
    """AI 호출을 관리하는 클래스 - 비동기 처리 지원"""
    
    @staticmethod
    def call_ai(prompt='테스트', system='지침', history=None, fine=None, api_key=None, retries=3):
        if api_key is None:
            api_key = API_KEY['API_1']

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(GEMINI_MODEL, system_instruction=system)

        if fine:
            ex = ''.join([f"user: {q}\nassistant: {a}\n" for q, a in fine])
            combined = f"{ex}user: {prompt}"
        else:
            his = DataManager.history_str(history if history is not None else [])
            combined = f"{his}user: {prompt}"

        attempt = 0
        while True:
            try:
                resp = model.start_chat(history=[]).send_message(combined)
                txt = resp._result.candidates[0].content.parts[0].text.strip()
                result = txt[9:].strip() if txt.lower().startswith('assistant:') else txt
                return result
            except ResourceExhausted:
                attempt += 1
                if attempt > retries:
                    return ''
                wait = 2 ** attempt
                time.sleep(wait)
            except Exception as e:
                print(f"AI 호출 중 오류 발생: {e}")
                return ''
    
    @staticmethod
    async def call_ai_async_single(prompt, system, history=None, fine=None, api_key=None, retries=3):
        """단일 AI 비동기 호출"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, 
            AIManager.call_ai, 
            prompt, system, history, fine, api_key, retries
        )
    
    @staticmethod
    async def call_ai_async_multiple(queries, system_prompt, history=None, fine=None):
        """여러 LOAD API 키를 사용한 병렬 비동기 호출"""
        if not LOAD_API_KEYS:
            # LOAD API 키가 없으면 기본 API 사용
            tasks = []
            for query in queries:
                task = AIManager.call_ai_async_single(
                    query, system_prompt, history, fine, API_KEY['API_1']
                )
                tasks.append(task)
            return await asyncio.gather(*tasks)
        
        # LOAD API 키들을 사용한 병렬 처리
        tasks = []
        for i, query in enumerate(queries):
            api_key = LOAD_API_KEYS[i % len(LOAD_API_KEYS)]  # 라운드 로빈 방식
            task = AIManager.call_ai_async_single(
                query, system_prompt, history, fine, api_key
            )
            tasks.append(task)
        
        return await asyncio.gather(*tasks)


class AuxiliaryAI:
    """보조 인공지능 - 계층적 기억 관리 시스템의 핵심 컨트롤러"""
    
    def __init__(self, memory_manager):
        self.memory_manager = memory_manager
        self.ai_manager = AIManager()
        self.load_ai = LoadAI(memory_manager)
    
    def handle_conversation(self, conversation):
        """새로운 대화를 처리하고 적절한 노드에 저장합니다."""
        # 1. 전체 기록에 저장
        conversation_index = self.memory_manager.save_to_all_memory(conversation)
        
        # 2. 사용자 입력 분석
        user_input = conversation[0]['content']
        
        # 3. 관련 노드 찾기
        relevant_node = self.find_relevant_node(user_input)
        
        # 4. 새로운 주제인지 판단
        if self.check_for_new_topic(relevant_node, user_input):
            # 새로운 노드 생성
            new_node = self.create_new_node(relevant_node, user_input, conversation, conversation_index)
            self.update_node_coordinates(new_node.node_id, conversation_index, conversation_index)
        else:
            # 기존 노드에 추가
            self.update_node_and_parents(relevant_node, conversation, conversation_index)
    
    def find_relevant_node(self, user_input):
        """사용자 입력과 가장 관련 있는 노드를 찾습니다."""
        tree_summary = self.memory_manager.get_tree_summary()
        
        # 먼저 상위 카테고리 존재 여부 확인
        category_node = self.find_or_create_category_node(user_input)
        if category_node:
            return category_node
        
        system_prompt = """당신은 사용자의 입력을 분석하여 기존 트리에서 가장 적절한 노드를 찾는 전문가입니다.
트리 구조를 분석하고 사용자 입력과 가장 관련 있는 노드의 주제명을 정확히 반환하세요.
만약 관련된 노드가 없다면 'root'를 반환하세요."""
        
        prompt = f"사용자 입력: {user_input}\n\n트리 구조 요약:\n{tree_summary}\n\n가장 관련 있는 노드의 주제명을 반환하세요."
        
        result = self.ai_manager.call_ai(prompt=prompt, system=system_prompt, fine=FIND_NODE_FINE)
        
        # 결과를 바탕으로 실제 노드 찾기
        target_topic = result.strip()
        for node in self.memory_manager.memory_tree.values():
            if node.topic == target_topic:
                return node
        
        # 찾지 못했다면 루트 노드 반환
        return self.memory_manager.get_root_node()
    
    def find_or_create_category_node(self, user_input):
        """사용자 입력이 특정 카테고리에 속하는지 확인하고, 필요시 카테고리 노드를 생성합니다."""
        # 과일 관련 키워드 체크
        fruit_keywords = ['사과', '포도', '딸기', '바나나', '오렌지', '수박', '참외', '복숭아', '배', '감', '귤']
        animal_keywords = ['개', '고양이', '강아지', '새', '물고기', '토끼', '햄스터', '거북이', '앵무새']
        food_keywords = ['음식', '요리', '밥', '국', '찌개', '볶음', '튀김', '구이', '면', '빵', '라면', '파스타']
        subject_keywords = ['수학', '영어', '국어', '과학', '사회', '체육', '음악', '미술', '역사', '물리', '화학', '생물', '지리']
        
        user_lower = user_input.lower()
        
        # 과일 카테고리 체크
        if any(keyword in user_input for keyword in fruit_keywords):
            return self.get_or_create_category_node('과일', '과일에 대한 모든 대화를 관리하는 카테고리입니다.')
        
        # 동물 카테고리 체크
        if any(keyword in user_input for keyword in animal_keywords):
            return self.get_or_create_category_node('동물', '동물에 대한 모든 대화를 관리하는 카테고리입니다.')
        
        # 음식 카테고리 체크
        if any(keyword in user_input for keyword in food_keywords):
            return self.get_or_create_category_node('음식', '음식에 대한 모든 대화를 관리하는 카테고리입니다.')
        
        # 과목 카테고리 체크
        if any(keyword in user_input for keyword in subject_keywords) or '과목' in user_input or '공부' in user_input:
            return self.get_or_create_category_node('과목', '학교 과목과 학습에 대한 모든 대화를 관리하는 카테고리입니다.')
        
        return None
    
    def get_or_create_category_node(self, category_name, category_description):
        """카테고리 노드가 존재하면 반환하고, 없으면 생성합니다."""
        # 기존 카테고리 노드 찾기
        for node in self.memory_manager.memory_tree.values():
            if node.topic == category_name:
                return node
        
        # 카테고리 노드가 없으면 생성
        root_node = self.memory_manager.get_root_node()
        category_node = MemoryNode(
            topic=category_name,
            summary=category_description,
            coordinates={"start": -1, "end": -1}  # 카테고리 노드는 특정 대화를 가리키지 않음
        )
        
        self.memory_manager.add_node(category_node, root_node.node_id)
        return category_node
    
    def check_for_new_topic(self, parent_node, user_input):
        """새로운 주제인지 판단합니다."""
        # 카테고리 노드인 경우 더 세밀한 판단
        if parent_node.topic in ['과일', '동물', '음식']:
            return self.check_for_new_subtopic_in_category(parent_node, user_input)
        
        system_prompt = """당신은 새로운 대화가 기존 노드의 하위 주제인지, 완전히 새로운 주제인지 판단하는 전문가입니다.
반드시 "True" (새로운 주제) 또는 "False" (기존 주제의 하위)로만 답하세요."""
        
        prompt = f"부모 노드 주제: {parent_node.topic}\n새로운 대화: {user_input}"
        
        result = self.ai_manager.call_ai(prompt=prompt, system=system_prompt, fine=NEW_TOPIC_FINE)
        return result.strip() == 'True'
    
    def check_for_new_subtopic_in_category(self, category_node, user_input):
        """카테고리 노드 하에서 새로운 하위 주제인지 판단합니다."""
        # 이미 존재하는 자식 노드들 확인
        existing_subtopics = []
        for child_id in category_node.children_ids:
            child_node = self.memory_manager.get_node(child_id)
            if child_node:
                existing_subtopics.append(child_node.topic)
        
        # 과일 카테고리인 경우
        if category_node.topic == '과일':
            fruit_keywords = {
                '사과': ['사과'],
                '포도': ['포도'],
                '딸기': ['딸기'],
                '바나나': ['바나나'],
                '오렌지': ['오렌지'],
                '수박': ['수박'],
                '참외': ['참외'],
                '복숭아': ['복숭아'],
                '배': ['배'],
                '감': ['감'],
                '귤': ['귤']
            }
            
            for fruit_name, keywords in fruit_keywords.items():
                if any(keyword in user_input for keyword in keywords):
                    # 이미 해당 과일 노드가 존재하는지 확인
                    if fruit_name in existing_subtopics:
                        return False  # 기존 노드에 추가
                    else:
                        return True   # 새 노드 생성
        
        # 동물 카테고리인 경우
        elif category_node.topic == '동물':
            animal_keywords = {
                '개': ['개', '강아지'],
                '고양이': ['고양이'],
                '새': ['새', '앵무새'],
                '물고기': ['물고기'],
                '토끼': ['토끼'],
                '햄스터': ['햄스터'],
                '거북이': ['거북이']
            }
            
            for animal_name, keywords in animal_keywords.items():
                if any(keyword in user_input for keyword in keywords):
                    if animal_name in existing_subtopics:
                        return False
                    else:
                        return True
        
        # 과목 카테고리인 경우
        elif category_node.topic == '과목':
            subject_keywords = {
                '수학': ['수학'],
                '영어': ['영어'],
                '국어': ['국어'],
                '과학': ['과학', '물리', '화학', '생물'],
                '사회': ['사회', '역사', '지리'],
                '체육': ['체육'],
                '음악': ['음악'],
                '미술': ['미술']
            }
            
            for subject_name, keywords in subject_keywords.items():
                if any(keyword in user_input for keyword in keywords):
                    if subject_name in existing_subtopics:
                        return False
                    else:
                        return True
        
        # 기본적으로 새 주제로 판단
        return True
    
    def create_new_node(self, parent_node, user_input, conversation, conversation_index):
        """새로운 노드를 생성합니다."""
        # 키워드 기반 주제 추출 (빠른 처리)
        topic = self._extract_specific_topic(user_input)
        
        if not topic:
            # AI 기반 주제 추출 (백업)
            system_prompt = """당신은 대화에서 핵심 주제를 추출하는 전문가입니다.
사용자의 입력과 AI의 응답을 분석하여 간결하고 명확한 주제명을 생성하세요.
주제명은 2-10글자 정도로 간단해야 합니다."""
            
            user_content = conversation[0]['content']
            ai_content = conversation[1]['content']
            prompt = f"사용자: {user_content}\nAI: {ai_content}\n\n위 대화의 핵심 주제를 간결하게 추출하세요."
            topic = self.ai_manager.call_ai(prompt=prompt, system=system_prompt)
        
        # 요약 생성 (인라인)
        system_prompt = """당신은 대화 내용을 정확하고 포괄적으로 요약하는 전문가입니다.
다음 원칙에 따라 요약하세요:

1. 사용자가 말한 내용과 AI가 응답한 내용을 모두 포함
2. 핵심 주제, 중요한 정보, 구체적인 세부사항을 놓치지 않기
3. 대화의 맥락과 흐름을 유지
4. 요약문에는 따옴표("), 백슬래시(\), 작은따옴표(')를 사용하지 않기
5. 간결하면서도 완전한 정보를 담기

형식: "사용자가 [사용자 내용 요약]에 대해 이야기했고, AI는 [AI 응답 요약]로 답변했다."
"""
        
        user_content = conversation[0]['content']
        ai_content = conversation[1]['content']
        prompt = f"사용자: {user_content}\nAI: {ai_content}\n\n위 대화를 요약해주세요."
        summary = self.ai_manager.call_ai(prompt=prompt, system=system_prompt)
        
        # 새 노드 생성
        new_node = MemoryNode(
            topic=topic,
            summary=summary,
            coordinates={"start": conversation_index, "end": conversation_index}
        )
        
        # 트리에 추가
        self.memory_manager.add_node(new_node, parent_node.node_id)
        
        return new_node
    
    def _extract_specific_topic(self, user_input):
        """키워드 기반으로 구체적인 주제를 추출합니다."""
        # 과일 키워드 매핑
        fruit_keywords = {
            '사과': ['사과'],
            '포도': ['포도'],
            '딸기': ['딸기'],
            '바나나': ['바나나'],
            '오렌지': ['오렌지'],
            '수박': ['수박'],
            '참외': ['참외'],
            '복숭아': ['복숭아'],
            '배': ['배'],
            '감': ['감'],
            '귤': ['귤']
        }
        
        # 동물 키워드 매핑
        animal_keywords = {
            '개': ['개', '강아지'],
            '고양이': ['고양이'],
            '새': ['새', '앵무새'],
            '물고기': ['물고기'],
            '토끼': ['토끼'],
            '햄스터': ['햄스터'],
            '거북이': ['거북이']
        }
        
        # 과목 키워드 매핑
        subject_keywords = {
            '수학': ['수학'],
            '영어': ['영어'],
            '국어': ['국어'],
            '과학': ['과학', '물리', '화학', '생물'],
            '사회': ['사회', '역사', '지리'],
            '체육': ['체육'],
            '음악': ['음악'],
            '미술': ['미술']
        }
        
        # 기타 키워드
        other_keywords = {
            '학교': ['학교', '고등학교', '중학교', '초등학교'],
            '친구': ['친구', '베프', '절친'],
            '취미': ['취미', '독서', '운동', '게임', '영화']
        }
        
        # 과일 체크
        for topic, keywords in fruit_keywords.items():
            if any(keyword in user_input for keyword in keywords):
                return topic
        
        # 동물 체크
        for topic, keywords in animal_keywords.items():
            if any(keyword in user_input for keyword in keywords):
                return topic
        
        # 과목 체크
        for topic, keywords in subject_keywords.items():
            if any(keyword in user_input for keyword in keywords):
                return topic
        
        # 기타 체크
        for topic, keywords in other_keywords.items():
            if any(keyword in user_input for keyword in keywords):
                return topic
        
        # 기타 체크
        for topic, keywords in other_keywords.items():
            if any(keyword in user_input for keyword in keywords):
                return topic
        
        return None
    
    def update_node_and_parents(self, node, conversation, conversation_index):
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
        
        new_summary = self.ai_manager.call_ai(prompt=prompt, system=system_prompt)
        
        # 좌표 업데이트
        new_coordinates = {
            "start": node.coordinates["start"],
            "end": conversation_index
        }
        
        self.memory_manager.update_node(
            node.node_id,
            summary=new_summary,
            coordinates=new_coordinates
        )
        
        # 부모 노드들 재귀적으로 업데이트
        if node.parent_id:
            parent_node = self.memory_manager.get_node(node.parent_id)
            if parent_node:
                self.update_parent_summary(parent_node, node)
    
    def update_summary(self, current_summary, new_conversation):
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
        
        return self.ai_manager.call_ai(prompt=prompt, system=system_prompt)
    
    def update_parent_summary(self, parent_node, child_node):
        """부모 노드의 요약을 자식 노드 변경사항에 맞춰 업데이트합니다."""
        # 카테고리 노드인 경우 요약을 변경하지 않음
        if parent_node.coordinates["start"] == -1 and parent_node.coordinates["end"] == -1:
            # 카테고리 노드는 고정된 설명을 유지
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
        
        updated_summary = self.ai_manager.call_ai(prompt=prompt, system=system_prompt)
        self.memory_manager.update_node(parent_node.node_id, summary=updated_summary)
        
        # 재귀적으로 상위 부모도 업데이트 (ROOT 제외)
        if parent_node.parent_id and parent_node.topic != "ROOT":
            grandparent_node = self.memory_manager.get_node(parent_node.parent_id)
            if grandparent_node and grandparent_node.topic != "ROOT":
                self.update_parent_summary(grandparent_node, parent_node)
    
    def update_node_coordinates(self, node_id, start_index, end_index):
        """노드의 좌표를 업데이트합니다."""
        self.memory_manager.update_node(
            node_id,
            coordinates={"start": start_index, "end": end_index}
        )


class LoadAI:
    """로드 인공지능 - 트리 구조에서 관련 정보를 검색 (레거시 호환용)"""
    
    def __init__(self, memory_manager):
        self.memory_manager = memory_manager
        self.ai_manager = AIManager()
    
    def search_tree(self, query):
        """트리에서 쿼리와 관련된 노드들을 찾습니다. (레거시 호환용)"""
        # 이 함수는 이제 MainAI에서 직접 처리되므로 단순화
        return None


class MainAI:
    """메인 인공지능 - 사용자와 직접 대화하는 주체"""
    
    def __init__(self):
        self.memory_manager = MemoryManager()
        self.auxiliary_ai = AuxiliaryAI(self.memory_manager)
        self.ai_manager = AIManager()
    
    async def chat_async(self, user_input):
        """사용자와 채팅합니다 (비동기 버전)."""
        if not user_input or user_input.strip() == 'False':
            return 'NONE'
        
        # 과거 기억이 필요한지 간단히 판단 (키워드 기반)
        memory_keywords = ['저번', '이전', '전에', '아까', '말했', '했다', '언급', '소개', '정보', '모두', '뭐라고', '어떤', '무엇']
        needs_memory = any(keyword in user_input for keyword in memory_keywords)
        
        relevant_memories = None
        if needs_memory:
            # 관련 기억 비동기 검색
            print("트리 검색 시작 (비동기 처리)")
            all_nodes = list(self.memory_manager.memory_tree.values())
            
            # 비동기 병렬 검색
            relevant_nodes = await self._check_nodes_relevance_async(user_input, all_nodes)
            
            if relevant_nodes:
                print(f"관련 노드 {len(relevant_nodes)}개 발견")
                relevant_memories = self._extract_conversation_data(relevant_nodes)
        
        # 통합된 응답 생성
        if relevant_memories:
            system_prompt = """과거 대화 내용을 참고하여 정확하고 간결하게 답변하세요.
1-2문장으로 핵심만 간단히 응답하세요."""
            response = self.ai_manager.call_ai(prompt=user_input, system=system_prompt, history=relevant_memories)
        else:
            system_prompt = """1-2문장으로 간단하고 명확하게 응답하세요."""
            response = self.ai_manager.call_ai(prompt=user_input, system=system_prompt)
        
        # 대화를 기억 시스템에 저장
        conversation = [
            {'role': 'user', 'content': user_input},
            {'role': 'assistant', 'content': response}
        ]
        self.auxiliary_ai.handle_conversation(conversation)
        
        return response
    
    def chat(self, user_input):
        """사용자와 채팅합니다 (동기 래퍼)."""
        return asyncio.run(self.chat_async(user_input))
    
    async def _check_nodes_relevance_async(self, query, nodes):
        """여러 노드의 관련성을 비동기로 병렬 체크합니다."""
        system_prompt = """당신은 사용자의 질문과 노드의 관련성을 판단하는 전문가입니다.
반드시 "True" 또는 "False"만 출력하세요."""
        
        # 각 노드에 대한 쿼리 생성
        queries = []
        for node in nodes:
            prompt = f"사용자 질문: {query}\n노드 주제: {node.topic}\n노드 요약: {node.summary}\n\n위 질문과 노드가 관련이 있는지 판단하세요."
            queries.append(prompt)
        
        print(f"  비동기 병렬 검색 시작: {len(nodes)}개 노드 동시 처리")
        
        # 비동기 병렬 처리
        results = await AIManager.call_ai_async_multiple(
            queries, system_prompt, fine=ISSAMEFINE
        )
        
        # 결과 처리 및 관련 노드 수집
        relevant_nodes = []
        for i, (node, result) in enumerate(zip(nodes, results)):
            is_relevant = result.strip() == 'True'
            if is_relevant:
                print(f"  ✓ 관련 노드 발견: {node.topic}")
                relevant_nodes.append(node)
            else:
                print(f"  ✗ 관련성 없음: {node.topic}")
        
        return relevant_nodes
    
    def _check_node_relevance(self, query, node):
        """특정 노드가 쿼리와 관련 있는지 확인합니다. (단일 노드용)"""
        print(f"  검색 중: {node.topic} (부모: {node.parent_id or 'ROOT'})")
        
        system_prompt = """당신은 사용자의 질문과 노드의 관련성을 판단하는 전문가입니다.
반드시 "True" 또는 "False"만 출력하세요."""
        
        prompt = f"사용자 질문: {query}\n노드 주제: {node.topic}\n노드 요약: {node.summary}\n\n위 질문과 노드가 관련이 있는지 판단하세요."
        
        result = self.ai_manager.call_ai(prompt=prompt, system=system_prompt, fine=ISSAMEFINE)
        is_relevant = result.strip() == 'True'
        
        if is_relevant:
            print(f"  ✓ 관련 노드 발견: {node.topic}")
        else:
            print(f"  ✗ 관련성 없음: {node.topic}")
        
        return is_relevant
    
    def _extract_conversation_data(self, nodes):
        """관련 노드들에서 대화 데이터를 추출합니다."""
        all_memory = self.memory_manager.data_manager.load_json(ALL_MEMORY)
        conversation_data = []
        
        print(f"  데이터 추출 중: {len(nodes)}개 노드에서 대화 내용 수집")
        
        for node in nodes:
            start_idx = node.coordinates["start"]
            end_idx = node.coordinates["end"]
            
            print(f"  - {node.topic}: 대화 인덱스 {start_idx}~{end_idx}")
            
            # 좌표 범위의 대화들을 추출
            if start_idx >= 0 and end_idx >= 0:  # 유효한 좌표인 경우만
                for i in range(start_idx, min(end_idx + 1, len(all_memory))):
                    if i < len(all_memory):
                        conversation_data.extend(all_memory[i])
                        print(f"    추출된 대화 {i}: {len(all_memory[i])}개 메시지")
        
        print(f"  총 추출된 메시지: {len(conversation_data)}개")
        return conversation_data

    def get_tree_status(self):
        """현재 트리 상태를 반환합니다."""
        return {
            'total_nodes': len(self.memory_manager.memory_tree),
            'tree_summary': self.memory_manager.get_tree_summary(),
            'root_node_id': self.memory_manager.root_node_id
        }
def parse_arguments():
    """명령줄 인수를 파싱합니다."""
    parser = argparse.ArgumentParser(description='계층적 의미 기억 시스템')
    parser.add_argument(
        '--mode', 
        choices=['test', 'chat'], 
        default='chat',
        help='실행 모드: test (기존 질문들로 테스트) 또는 chat (대화형 모드)'
    )
    parser.add_argument(
        '--api-info',
        action='store_true',
        help='사용 가능한 API 키 정보 표시'
    )
    parser.add_argument(
        '--tree',
        action='store_true',
        help='현재 트리 구조를 도식화하여 표시'
    )
    return parser.parse_args()

def show_api_info():
    """API 키 정보를 표시합니다."""
    print("=== API 키 정보 ===")
    print(f"메인 API 키들: {len([k for k in API_KEY.values() if k])}")
    print(f"LOAD API 키들: {len(LOAD_API_KEYS)}")
    if LOAD_API_KEYS:
        print("비동기 병렬 검색 사용 가능 ✓")
    else:
        print("비동기 병렬 검색 불가능 (LOAD API 키 없음)")
    print("=" * 20)

def show_tree_structure():
    """현재 트리 구조를 도식화하여 표시합니다."""
    memory_manager = MemoryManager()
    
    if not memory_manager.memory_tree:
        print("=== 트리 구조 ===")
        print("트리가 비어있습니다.")
        print("=" * 50)
        return
    
    print("=== 계층적 기억 트리 구조 ===")
    print(f"총 노드 수: {len(memory_manager.memory_tree)}")
    print()
    
    def build_tree_visualization(node_id, depth=0, is_last=True, prefix=""):
        """트리를 시각적으로 구성합니다."""
        if node_id not in memory_manager.memory_tree:
            return ""
        
        node = memory_manager.memory_tree[node_id]
        
        # 트리 브랜치 문자 결정
        if depth == 0:
            tree_char = "🌳 "
            new_prefix = ""
        else:
            tree_char = "└── " if is_last else "├── "
            new_prefix = prefix + ("    " if is_last else "│   ")
        
        # 노드 정보 구성
        node_info = f"{node.topic}"
        if node.coordinates["start"] >= 0:
            coord_info = f" (대화: {node.coordinates['start']}~{node.coordinates['end']})"
        else:
            coord_info = " (카테고리)"
        
        # 요약 미리보기 (50자 제한)
        summary_preview = node.summary[:50] + "..." if len(node.summary) > 50 else node.summary
        
        result = f"{prefix}{tree_char}{node_info}{coord_info}\n"
        if summary_preview and node.topic != "ROOT":
            result += f"{new_prefix}💬 {summary_preview}\n"
        
        # 자식 노드들 처리
        children_ids = node.children_ids
        for i, child_id in enumerate(children_ids):
            is_last_child = (i == len(children_ids) - 1)
            result += build_tree_visualization(child_id, depth + 1, is_last_child, new_prefix)
        
        return result
    
    # 루트부터 시작하여 전체 트리 구성
    tree_visual = build_tree_visualization(memory_manager.root_node_id)
    print(tree_visual)
    
    # 통계 정보
    print("=" * 50)
    print("📊 트리 통계:")
    
    # 카테고리별 노드 수 계산
    categories = {}
    conversation_nodes = 0
    
    for node in memory_manager.memory_tree.values():
        if node.coordinates["start"] == -1:  # 카테고리 노드
            categories[node.topic] = len(node.children_ids)
        elif node.coordinates["start"] >= 0:  # 대화 노드
            conversation_nodes += 1
    
    print(f"- 총 노드 수: {len(memory_manager.memory_tree)}")
    print(f"- 대화 기록 노드: {conversation_nodes}")
    print(f"- 카테고리 노드: {len(categories)}")
    
    if categories:
        print("\n📁 카테고리별 하위 노드:")
        for category, count in categories.items():
            if category != "ROOT":
                print(f"  - {category}: {count}개")
    
    print("=" * 50)

async def run_test_mode():
    """테스트 모드로 실행합니다."""
    print("=== 계층적 의미 기억 시스템 시작 (테스트 모드) ===")
    main_ai_instance = MainAI()
    
    # 테스트 질문들 - 더 다양한 시나리오 추가
    test_questions = [
        # 개인 정보 시리즈
        "내 이름은 서재민이다.",
        "내가 다니는 고등학교는 대건고등학교이다.",
        "내가 좋아하는 과목은 수학이다.",
        "내 취미는 독서이다.",
        "가장 친한 친구는 김철수이다.",
        
        # 과일 카테고리 시리즈
        "사과에 대해서 궁금하다",
        "사과의 씨에는 독이 있는가?",
        "나는 사과에 대해서 부정적으로 생각한다.",
        "포도에 대해서 궁금하다.",
        "포도의 씨에는 독이 있는가?",
        "나는 포도에 대해서 부정적으로 생각한다. 왜냐하면 포도는 한 송이이지만 알맹이 모두 맛이 다르기 때문이다.",
        "딸기는 어떤 맛인가요?",
        "바나나의 영양가는?",
        "오렌지 비타민C 함량이 궁금해",
        
        # 동물 카테고리 시리즈
        "고양이는 어떤 성격의 동물인가요?",
        "강아지 훈련 방법이 궁금해요",
        "토끼는 어떤 먹이를 먹나요?",
        "새의 종류에는 뭐가 있나요?",
        
        # 음식 카테고리 시리즈
        "김치찌개 레시피 알려줘",
        "라면 맛있게 끓이는 법",
        "파스타 만드는 방법",
        
        # 학습 카테고리 시리즈
        "영어 공부 방법이 궁금해",
        "과학 실험 재미있는 것들",
        "역사 공부하는 팁",
        
        # 기억 검색 테스트 시리즈 (비동기 병렬 검색 테스트)
        "저번에 내 이름이 뭐라고 했지?",
        "저번에 나에 대한 소개를 했는데, 나에 대한 정보를 모두 말해봐.",
        "내가 사과를 싫어하는 이유는?",
        "저번에 내가 포도를 싫어하는 이유를 말했다. 그 내용이 무엇인가?",
        "내가 좋아하는 과목이 뭐였지?",
        "내 친구 이름이 뭐였나?",
        "과일 중에서 내가 부정적으로 생각하는 것들은?",
        "내가 언급한 동물들 모두 말해봐",
        "지금까지 내가 물어본 음식 관련 질문들은?"
    ]

    for i, question in enumerate(test_questions):
        print(f"\n--- 질문 {i+1} ---")
        print(f"Q: {question}")
        
        start_time = time.time()
        response = await main_ai_instance.chat_async(question)
        end_time = time.time()
        
        print(f"A: {response}")
        print(f"처리 시간: {end_time - start_time:.2f}초")
        
        # 트리 상태 출력 (간단한 정보만)
        if i < 15:  # 처음 15개 질문에 대해서만 노드 수 표시
            status = main_ai_instance.get_tree_status()
            print(f"트리 노드 수: {status['total_nodes']}")
        
        # 일부 질문에서는 더 자세한 트리 구조 표시
        if i == 4 or i == 11 or i == 18:  # 개인정보, 과일, 동물 카테고리 완성 시점
            print("\n현재 트리 구조:")
            status = main_ai_instance.get_tree_status()
            print(status['tree_summary'])
    
    print("\n=== 최종 트리 구조 ===")
    final_status = main_ai_instance.get_tree_status()
    print(f"총 노드 수: {final_status['total_nodes']}")
    print(f"트리 구조:\n{final_status['tree_summary']}")

async def run_chat_mode():
    """대화형 모드로 실행합니다."""
    print("=== 계층적 의미 기억 시스템 시작 (대화형 모드) ===")
    main_ai_instance = MainAI()
    
    print("\n=== 대화형 모드 (종료하려면 'exit' 입력) ===")
    while True:
        user_input = input("\n사용자: ")
        if user_input.lower() in ['exit', 'quit', '종료', '그만']:
            print("AI: 대화를 종료합니다.")
            break
        
        start_time = time.time()
        response = await main_ai_instance.chat_async(user_input)
        end_time = time.time()
        
        print(f"AI: {response}")
        print(f"(처리 시간: {end_time - start_time:.2f}초)")

def main_ai(prompt='False'):
    """메인 AI 인스턴스를 생성하고 대화를 처리합니다."""
    main_ai_instance = MainAI()
    return main_ai_instance.chat(prompt)


if __name__ == '__main__':
    args = parse_arguments()
    
    if args.api_info:
        show_api_info()
    
    if args.tree:
        show_tree_structure()
    
    # tree나 api_info만 요청한 경우 종료
    if args.tree or args.api_info:
        if not (args.mode in ['test', 'chat']):
            exit(0)
    
    if args.mode == 'test':
        asyncio.run(run_test_mode())
    elif args.mode == 'chat':
        asyncio.run(run_chat_mode())
