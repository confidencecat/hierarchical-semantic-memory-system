import json
import os
import google.generativeai as genai
import concurrent.futures
import time
import uuid
import asyncio
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
    
    def __init__(self, memory_manager, debug=False):
        self.memory_manager = memory_manager
        self.ai_manager = AIManager()
        self.load_ai = LoadAI(memory_manager)
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
            print(f"\n🐛 [DEBUG] === AI 분류 시작 ===")
            print(f"🐛 [DEBUG] 사용자 입력: {user_input[:50]}...")
            print(f"🐛 [DEBUG] 대화 인덱스: {conversation_index}")
        
        # 1. 기존 카테고리들과의 관련성 검사 (비동기 병렬)
        existing_categories = await self._get_existing_categories()
        
        if self.debug:
            print(f"🐛 [DEBUG] 기존 카테고리 수: {len(existing_categories)}")
            if existing_categories:
                print(f"🐛 [DEBUG] 기존 카테고리들: {list(existing_categories.keys())}")
        
        if existing_categories:
            # 2. 기존 카테고리들과의 관련성을 AI로 판단
            if self.debug:
                print(f"🐛 [DEBUG] 카테고리 관련성 검사 시작...")
            category_relevance = await self._check_category_relevance_async(user_input, existing_categories)
            
            if self.debug:
                print(f"🐛 [DEBUG] 카테고리 관련성 결과: {category_relevance}")
            
            # 3. 관련된 카테고리가 있으면 해당 카테고리별로 대화 내용 분리
            if any(category_relevance.values()):
                if self.debug:
                    relevant_cats = [cat for cat, rel in category_relevance.items() if rel]
                    print(f"🐛 [DEBUG] 관련 카테고리 발견: {relevant_cats}")
                await self._process_multiple_categories(conversation, conversation_index, category_relevance, existing_categories)
            else:
                # 4. 기존 카테고리와 관련 없으면 새 카테고리 생성
                if self.debug:
                    print(f"🐛 [DEBUG] 기존 카테고리와 관련 없음 - 새 카테고리 생성")
                await self._create_new_category_and_node(conversation, conversation_index)
        else:
            # 기존 카테고리가 없으면 새 카테고리 생성
            if self.debug:
                print(f"🐛 [DEBUG] 기존 카테고리 없음 - 첫 번째 카테고리 생성")
            await self._create_new_category_and_node(conversation, conversation_index)
        
        if self.debug:
            print(f"🐛 [DEBUG] === AI 분류 완료 ===")
            print(f"🐛 [DEBUG] 📊 최종 저장 결과 요약:")
            
            # 현재 트리에서 최근 업데이트된 노드들 찾기
            recent_nodes = []
            for node in self.memory_manager.memory_tree.values():
                if hasattr(node, 'coordinates') and node.coordinates.get('end') == conversation_index:
                    recent_nodes.append(node)
            
            if recent_nodes:
                print(f"🐛 [DEBUG] 대화가 저장된 노드 수: {len(recent_nodes)}")
                for i, node in enumerate(recent_nodes, 1):
                    # 부모 노드 찾기 (카테고리)
                    parent_category = "ROOT"
                    for parent_node in self.memory_manager.memory_tree.values():
                        if node.node_id in parent_node.children_ids:
                            parent_category = parent_node.topic
                            break
                    
                    print(f"🐛 [DEBUG] {i}. 카테고리: '{parent_category}' → 노드: '{node.topic}' (ID: {node.node_id})")
            else:
                print(f"🐛 [DEBUG] ⚠️  새로 저장된 노드가 없음 (기존 노드에 추가되었을 수 있음)")
            
            print(f"🐛 [DEBUG] === 전체 처리 완료 ===\n")
    
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
        """기존 카테고리들과 사용자 입력의 관련성을 AI로 비동기 판단합니다."""
        system_prompt = """당신은 사용자의 대화 내용이 기존 카테고리와 관련이 있는지 판단하는 전문가입니다.

사용자의 대화를 분석하고, 각 카테고리와의 관련성을 정확히 판단하세요.
단순히 단어가 포함되어 있다고 관련이 있는 것이 아니라, 실제 대화의 주제와 내용을 고려해야 합니다.

출력 형식:
카테고리명: True/False
카테고리명: True/False
...

예시:
과일: True
동물: False
과목: False"""
        
        # 카테고리별 관련성 검사 쿼리 생성
        category_info = "\n".join([f"{name}: {desc}" for name, desc in categories.items()])
        
        prompt = f"""기존 카테고리들:
{category_info}

사용자 대화: {user_input}

위 대화가 각 카테고리와 관련이 있는지 판단하고, 다음 형식으로 답변하세요:
{chr(10).join([f"{name}: True/False" for name in categories.keys()])}"""
        
        if self.debug:
            print(f"🐛 [DEBUG] === AI 카테고리 관련성 판단 요청 ===")
            print(f"🐛 [DEBUG] 판단할 카테고리 수: {len(categories)}")
            for name, desc in categories.items():
                print(f"🐛 [DEBUG]   '{name}': {desc}")
            print(f"🐛 [DEBUG] AI 관련성 판단 요청 중...")
        
        try:
            result = await self.ai_manager.call_ai_async_single(prompt, system_prompt, fine=CATEGORY_RELEVANCE_FINE)
            
            if self.debug:
                print(f"🐛 [DEBUG] AI 관련성 판단 결과:")
                print(f"🐛 [DEBUG] {result}")
                print(f"🐛 [DEBUG] === 관련성 결과 파싱 ===")
            
            # 결과 파싱
            relevance = {}
            for line in result.strip().split('\n'):
                if ':' in line:
                    category, value = line.split(':', 1)
                    category = category.strip()
                    value = value.strip().lower()
                    if category in categories:
                        relevance[category] = value in ['true', '참', 'yes']
                        if self.debug:
                            status = "✅ 관련있음" if relevance[category] else "❌ 관련없음"
                            print(f"🐛 [DEBUG] '{category}': {status}")
            
            if self.debug:
                print(f"🐛 [DEBUG] === 최종 관련성 결과 ===")
                relevant_count = sum(relevance.values())
                print(f"🐛 [DEBUG] 관련된 카테고리 수: {relevant_count}/{len(categories)}")
            
            return relevance
        except Exception as e:
            print(f"❌ 카테고리 관련성 검사 중 오류: {e}")
            return {cat: False for cat in categories.keys()}
    
    async def _process_multiple_categories(self, conversation, conversation_index, category_relevance, categories):
        """여러 카테고리에 관련된 대화를 적절히 분리하여 처리합니다."""
        user_input = conversation[0]['content']
        ai_response = conversation[1]['content']
        
        # 관련된 카테고리들 필터링
        relevant_categories = [cat for cat, is_relevant in category_relevance.items() if is_relevant]
        
        if self.debug:
            print(f"🐛 [DEBUG] === 다중 카테고리 처리 시작 ===")
            print(f"🐛 [DEBUG] 관련 카테고리 수: {len(relevant_categories)}")
            print(f"🐛 [DEBUG] 관련 카테고리들: {relevant_categories}")
        
        if len(relevant_categories) == 1:
            # 단일 카테고리인 경우
            if self.debug:
                print(f"🐛 [DEBUG] 단일 카테고리 처리: '{relevant_categories[0]}'")
            await self._process_single_category(conversation, conversation_index, relevant_categories[0])
        else:
            # 다중 카테고리인 경우 - 대화 내용을 분리
            if self.debug:
                print(f"🐛 [DEBUG] 다중 카테고리 대화 분리 시작...")
                print(f"🐛 [DEBUG] 원본 대화를 {len(relevant_categories)}개 카테고리로 분리:")
                for i, cat in enumerate(relevant_categories, 1):
                    print(f"🐛 [DEBUG]   {i}. '{cat}' 카테고리")
            await self._process_multi_category_conversation(conversation, conversation_index, relevant_categories)
    
    async def _process_single_category(self, conversation, conversation_index, category_name):
        """단일 카테고리에 대한 대화를 처리합니다."""
        if self.debug:
            print(f"🐛 [DEBUG] === '{category_name}' 카테고리 처리 시작 ===")
            print(f"🐛 [DEBUG] 처리할 대화:")
            print(f"🐛 [DEBUG]   사용자: {conversation[0]['content']}")
            print(f"🐛 [DEBUG]   AI: {conversation[1]['content']}")
        
        # 카테고리 노드 찾기
        category_node = None
        for node in self.memory_manager.memory_tree.values():
            if node.topic == category_name and node.coordinates["start"] == -1:
                category_node = node
                break
        
        if not category_node:
            if self.debug:
                print(f"🐛 [DEBUG] ❌ '{category_name}' 카테고리 노드를 찾을 수 없음")
            return
        
        if self.debug:
            print(f"🐛 [DEBUG] ✅ '{category_name}' 카테고리 노드 발견 (ID: {category_node.node_id})")
        
        user_input = conversation[0]['content']
        
        if self.debug:
            print(f"🐛 [DEBUG] 새로운 주제인지 AI로 판단 중...")
        
        # 새로운 주제인지 판단
        if await self._check_for_new_topic_async(category_node, user_input):
            # 새로운 노드 생성
            if self.debug:
                print(f"🐛 [DEBUG] ✅ 새로운 주제로 판단 - 새 노드 생성")
            new_node = await self._create_new_node_async(category_node, user_input, conversation, conversation_index)
            self.update_node_coordinates(new_node.node_id, conversation_index, conversation_index)
            if self.debug:
                print(f"🐛 [DEBUG] 📝 새 노드 생성 완료:")
                print(f"🐛 [DEBUG]   노드 ID: {new_node.node_id}")
                print(f"🐛 [DEBUG]   주제: '{new_node.topic}'")
                print(f"🐛 [DEBUG]   부모: '{category_name}' 카테고리")
                print(f"🐛 [DEBUG]   좌표: {new_node.coordinates}")
        else:
            # 기존 노드에 추가
            if self.debug:
                print(f"🐛 [DEBUG] ❌ 기존 주제로 판단 - 기존 노드에 추가")
            relevant_child = await self._find_relevant_child_node_async(category_node, user_input)
            if relevant_child:
                if self.debug:
                    print(f"🐛 [DEBUG] 📝 기존 노드에 추가:")
                    print(f"🐛 [DEBUG]   대상 노드 ID: {relevant_child.node_id}")
                    print(f"🐛 [DEBUG]   노드 주제: '{relevant_child.topic}'")
                self.update_node_and_parents(relevant_child, conversation, conversation_index)
                if self.debug:
                    print(f"🐛 [DEBUG] ✅ 노드 업데이트 완료")
            else:
                if self.debug:
                    print(f"🐛 [DEBUG] ❌ 관련 하위 노드를 찾을 수 없음")
        
        if self.debug:
            print(f"🐛 [DEBUG] === '{category_name}' 카테고리 처리 완료 ===\n")
    
    async def _process_multi_category_conversation(self, conversation, conversation_index, relevant_categories):
        """다중 카테고리에 걸친 대화를 분리하여 처리합니다."""
        user_input = conversation[0]['content']
        ai_response = conversation[1]['content']
        
        if self.debug:
            print(f"🐛 [DEBUG] === 대화 내용 분리 시작 ===")
            print(f"🐛 [DEBUG] 분리할 카테고리: {relevant_categories}")
            print(f"🐛 [DEBUG] 원본 사용자 입력: {user_input}")
            print(f"🐛 [DEBUG] 원본 AI 응답: {ai_response}")
        
        # 각 카테고리별로 관련된 대화 내용 분리
        separated_content = await self._separate_conversation_by_categories(user_input, ai_response, relevant_categories)
        
        if self.debug:
            print(f"🐛 [DEBUG] === 분리 결과 ===")
            for category, content_parts in separated_content.items():
                print(f"🐛 [DEBUG] 카테고리 '{category}':")
                print(f"🐛 [DEBUG]   사용자: {content_parts['user']}")
                print(f"🐛 [DEBUG]   AI: {content_parts['ai']}")
        
        # 분리된 내용을 각 카테고리에 저장
        for category, content_parts in separated_content.items():
            if content_parts['user'] and content_parts['ai']:
                if self.debug:
                    print(f"🐛 [DEBUG] '{category}' 카테고리에 분리된 대화 저장 중...")
                # 분리된 대화로 새로운 conversation 객체 생성
                separated_conversation = [
                    {"role": "user", "content": content_parts['user']},
                    {"role": "assistant", "content": content_parts['ai']}
                ]
                await self._process_single_category(separated_conversation, conversation_index, category)
    
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
            print(f"🐛 [DEBUG] === AI에게 대화 분리 요청 ===")
            print(f"🐛 [DEBUG] 분리 대상 카테고리: {categories_list}")
            print(f"🐛 [DEBUG] AI 분리 요청 시작...")
        
        try:
            result = await self.ai_manager.call_ai_async_single(prompt, system_prompt, fine=CONVERSATION_SEPARATION_FINE)
            
            if self.debug:
                print(f"🐛 [DEBUG] AI 분리 결과:")
                print(f"🐛 [DEBUG] {result}")
                print(f"🐛 [DEBUG] === 분리 결과 파싱 시작 ===")
            
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
                            print(f"🐛 [DEBUG] 파싱완료 - '{current_category}': 사용자='{current_user}', AI='{current_ai}'")
                    # 새 카테고리 시작
                    current_category = line[:-1]
                    current_user = ""
                    current_ai = ""
                    if self.debug:
                        print(f"🐛 [DEBUG] 새 카테고리 시작: '{current_category}'")
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
            print(f"대화 분리 중 오류: {e}")
            # 오류 시 원본 대화를 모든 카테고리에 할당
            return {cat: {'user': user_input, 'ai': ai_response} for cat in categories}
    
    async def _create_new_category_and_node(self, conversation, conversation_index):
        """새로운 카테고리와 노드를 생성합니다."""
        user_input = conversation[0]['content']
        
        if self.debug:
            print(f"🐛 [DEBUG] 새 카테고리 생성 시작...")
        
        # AI로 새 카테고리명 생성
        category_name = await self._generate_category_name_async(user_input)
        
        if self.debug:
            print(f"🐛 [DEBUG] 생성된 카테고리명: '{category_name}'")
        
        # 새 카테고리 노드 생성
        root_node = self.memory_manager.get_root_node()
        category_node = MemoryNode(
            topic=category_name,
            summary=f"{category_name}에 대한 모든 대화를 관리하는 카테고리입니다.",
            coordinates={"start": -1, "end": -1}
        )
        
        self.memory_manager.add_node(category_node, root_node.node_id)
        
        if self.debug:
            print(f"🐛 [DEBUG] 카테고리 노드 생성 완료 (ID: {category_node.node_id})")
        
        # 카테고리 하위에 실제 대화 노드 생성
        new_node = await self._create_new_node_async(category_node, user_input, conversation, conversation_index)
        self.update_node_coordinates(new_node.node_id, conversation_index, conversation_index)
        
        if self.debug:
            print(f"🐛 [DEBUG] 하위 노드 생성 완료 (ID: {new_node.node_id}, 주제: '{new_node.topic}')")
    
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
            print(f"🐛 [DEBUG] AI에게 새 주제 여부 판단 요청:")
            print(f"🐛 [DEBUG]   부모 카테고리: '{parent_node.topic}'")
            print(f"🐛 [DEBUG]   사용자 입력: {user_input[:100]}{'...' if len(user_input) > 100 else ''}")
        
        system_prompt = """당신은 새로운 대화가 기존 노드의 하위 주제인지, 완전히 새로운 주제인지 판단하는 전문가입니다.
반드시 "True" (새로운 주제) 또는 "False" (기존 주제의 하위)로만 답하세요."""
        
        prompt = f"부모 노드 주제: {parent_node.topic}\n새로운 대화: {user_input}"
        
        try:
            result = await self.ai_manager.call_ai_async_single(prompt, system_prompt, fine=NEW_TOPIC_FINE)
            is_new_topic = result.strip() == 'True'
            
            if self.debug:
                status = "✅ 새로운 주제" if is_new_topic else "❌ 기존 주제"
                print(f"🐛 [DEBUG] AI 판단 결과: {status} (응답: '{result.strip()}')")
            
            return is_new_topic
        except Exception as e:
            if self.debug:
                print(f"🐛 [DEBUG] ❌ 새 주제 판단 중 오류: {e} - 기본값으로 새 주제 처리")
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
                relevance_queries, system_prompt, fine=ISSAMEFINE
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
    
    def find_relevant_node(self, user_input):
        """사용자 입력과 가장 관련 있는 노드를 찾습니다. (레거시 호환용 - 새 시스템에서는 사용 안함)"""
        # 새로운 AI 기반 시스템에서는 이 함수를 사용하지 않음
        return self.memory_manager.get_root_node()
    
    def find_or_create_category_node(self, user_input):
        """레거시 호환용 - 새 AI 시스템에서는 사용하지 않음"""
        return None
    
    def get_or_create_category_node(self, category_name, category_description):
        """레거시 호환용 - 새 AI 시스템에서는 사용하지 않음"""
        return None
    
    def check_for_new_topic(self, parent_node, user_input):
        """레거시 호환용 - 새 AI 시스템에서는 사용하지 않음"""
        return True
    
    def check_for_new_subtopic_in_category(self, category_node, user_input):
        """레거시 호환용 - 새 AI 시스템에서는 사용하지 않음"""
        return True
    
    def create_new_node(self, parent_node, user_input, conversation, conversation_index):
        """레거시 호환용 - 새 AI 시스템에서는 사용하지 않음"""
        # 간단한 기본 노드 생성
        new_node = MemoryNode(
            topic="일반 대화",
            summary="레거시 호환용 노드",
            coordinates={"start": conversation_index, "end": conversation_index}
        )
        self.memory_manager.add_node(new_node, parent_node.node_id)
        return new_node
        
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
        """레거시 호환용 - AI 기반 시스템에서는 사용하지 않음"""
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
            if grandparent_node:
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
