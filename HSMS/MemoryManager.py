import os
from config import HIERARCHICAL_MEMORY, ALL_MEMORY
from .DataManager import DataManager
from .MemoryNode import MemoryNode


class MemoryManager:
    """계층적 기억 트리를 관리하는 클래스"""
    
    def __init__(self, debug=False):
        self.debug = debug
        self.data_manager = DataManager()
        self.memory_tree = {}  # node_id를 키로 하는 노드 딕셔너리
        self.root_node_id = None
        self.initialize_tree()
    
    def initialize_tree(self):
        """트리 구조를 초기화하거나 로드합니다."""
        if self.debug:
            print("  ┌─ [MEMORY] 트리 초기화 시작")
        
        if os.path.exists(HIERARCHICAL_MEMORY):
            tree_data = self.data_manager.load_json(HIERARCHICAL_MEMORY)
            if tree_data:
                # 기존 트리 로드
                self.memory_tree = {}
                for node_data in tree_data.get('nodes', []):
                    node = MemoryNode.from_dict(node_data)
                    self.memory_tree[node.node_id] = node
                self.root_node_id = tree_data.get('root_node_id')
                
                if self.debug:
                    print(f"  │  기존 트리 로드: {len(self.memory_tree)}개 노드")
                    print(f"  │  루트 노드: {self.root_node_id}")
                    print(f"  └─ 트리 로드 완료")
            else:
                if self.debug:
                    print("  │  빈 트리 파일 감지")
                self._create_initial_tree()
        else:
            if self.debug:
                print("  │  트리 파일 없음")
            self._create_initial_tree()
    
    def _create_initial_tree(self):
        """초기 루트 노드를 생성합니다."""
        if self.debug:
            print("  ┌─ [MEMORY] 새 트리 생성")
        
        root_node = MemoryNode(
            topic="ROOT",
            summary="최상위 루트 노드"
        )
        self.memory_tree[root_node.node_id] = root_node
        self.root_node_id = root_node.node_id
        
        if self.debug:
            print(f"  │  루트 노드 생성: {root_node.node_id}")
            print(f"  └─ 새 트리 생성 완료")
        
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
        """새 노드를 트리에 추가합니다. fanout_limit을 사전에 체크합니다."""
        if self.debug:
            print(f"    ┌─ [MEMORY] 노드 추가")
            print(f"    │  노드 ID: {node.node_id}")
            print(f"    │  토픽: {node.topic}")
            print(f"    │  부모 ID: {parent_id}")
        
        # fanout_limit 사전 체크
        if parent_id and parent_id in self.memory_tree:
            parent_node = self.memory_tree[parent_id]
            from config import get_config_value
            fanout_limit = get_config_value('fanout_limit')
            
            # 추가하려는 노드가 fanout_limit을 초과하게 만드는지 체크
            if len(parent_node.children_ids) >= fanout_limit:
                if self.debug:
                    print(f"    │  ⚠️  fanout_limit 초과 위험: {len(parent_node.children_ids)} >= {fanout_limit}")
                    print(f"    └─ 노드 추가 거부 - fanout_limit 보호")
                return False  # 추가 거부
        
        self.memory_tree[node.node_id] = node
        if parent_id and parent_id in self.memory_tree:
            parent_node = self.memory_tree[parent_id]
            if node.node_id not in parent_node.children_ids:
                parent_node.children_ids.append(node.node_id)
            node.parent_id = parent_id
            
            if self.debug:
                print(f"    │  부모-자식 관계 설정 완료")
        
        if self.debug:
            print(f"    └─ 노드 추가 완료")
        
        self.save_tree()
        return True  # 추가 성공
    
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
        if self.debug:
            print(f"  ┌─ [MEMORY] 전체 기록 저장")
            print(f"  │  대화 길이: {len(conversation)}개 메시지")
        
        mem = self.data_manager.load_json(ALL_MEMORY)
        mem.append(conversation)
        self.data_manager.save_json(ALL_MEMORY, mem)
        
        if self.debug:
            print(f"  │  저장된 인덱스: {len(mem) - 1}")
            print(f"  │  총 대화 수: {len(mem)}개")
            print(f"  └─ 전체 기록 저장 완료")
        
        return len(mem) - 1  # 저장된 대화의 인덱스 반환

    def get_node_depth(self, node_id):
        """특정 노드의 깊이를 계산합니다 (루트 = 0)."""
        depth = 0
        current_node = self.get_node(node_id)
        while current_node and current_node.parent_id is not None:
            depth += 1
            current_node = self.get_node(current_node.parent_id)
            if not current_node or current_node.topic == "ROOT":
                break
        return depth

    def get_subtree_max_depth(self, node_id):
        """해당 노드를 포함한 서브트리에서 최장 깊이를 계산합니다 (루트 기준)."""
        base_depth = self.get_node_depth(node_id)
        
        def get_max_depth_recursive(current_node_id, current_depth):
            node = self.get_node(current_node_id)
            if not node or not node.children_ids:
                return current_depth
            
            max_child_depth = current_depth
            for child_id in node.children_ids:
                child_depth = get_max_depth_recursive(child_id, current_depth + 1)
                max_child_depth = max(max_child_depth, child_depth)
            
            return max_child_depth
        
        return get_max_depth_recursive(node_id, base_depth)

    def can_insert_child(self, parent_id, max_depth):
        """부모 노드에 자식을 추가할 수 있는지 깊이 제한을 확인합니다."""
        parent_depth = self.get_node_depth(parent_id)
        return parent_depth + 1 <= max_depth

    def get_all_children_ids(self, node_id):
        """특정 노드 아래의 모든 자손 노드 ID를 재귀적으로 가져옵니다."""
        children_ids = []
        node = self.get_node(node_id)
        if not node:
            return []

        for child_id in node.children_ids:
            children_ids.append(child_id)
            children_ids.extend(self.get_all_children_ids(child_id))
        
        return children_ids
    
    def validate_tree_integrity(self):
        """트리 무결성을 검증합니다."""
        if not self.memory_tree:
            return True, []
        
        issues = []
        
        # 1. 루트 노드 존재 확인
        if self.root_node_id not in self.memory_tree:
            issues.append(f"루트 노드 {self.root_node_id}가 존재하지 않습니다.")
        
        # 2. 각 노드의 부모-자식 관계 검증
        for node_id, node in self.memory_tree.items():
            # 자식 노드들이 실제로 존재하는지 확인
            for child_id in node.children_ids:
                if child_id not in self.memory_tree:
                    issues.append(f"노드 {node_id}의 자식 {child_id}가 존재하지 않습니다.")
                else:
                    child_node = self.memory_tree[child_id]
                    if child_node.parent_id != node_id:
                        issues.append(f"부모-자식 관계 불일치: {node_id} -> {child_id}")
            
            # 부모 노드가 실제로 존재하는지 확인 (루트 제외)
            if node_id != self.root_node_id:
                if node.parent_id not in self.memory_tree:
                    issues.append(f"노드 {node_id}의 부모 {node.parent_id}가 존재하지 않습니다.")
        
        return len(issues) == 0, issues
    
    def insert_group_above(self, existing_child_id, group_topic, group_summary):
        """기존 자식 노드 위에 그룹 노드를 삽입합니다."""
        existing_node = self.get_node(existing_child_id)
        if not existing_node:
            return None
        
        old_parent_id = existing_node.parent_id
        old_parent = self.get_node(old_parent_id)
        if not old_parent:
            return None
        
        # 새 그룹 노드 생성
        group_node = MemoryNode(
            topic=group_topic,
            summary=group_summary,
            parent_id=old_parent_id,
            coordinates={"start": -1, "end": -1}  # 카테고리/그룹 노드
        )
        
        # 그룹 노드를 트리에 추가
        self.memory_tree[group_node.node_id] = group_node
        
        # 기존 부모의 자식 목록에서 기존 노드를 제거하고 그룹 노드 추가
        if existing_child_id in old_parent.children_ids:
            old_parent.children_ids.remove(existing_child_id)
        old_parent.children_ids.append(group_node.node_id)
        
        # 기존 노드의 부모를 그룹 노드로 변경
        existing_node.parent_id = group_node.node_id
        group_node.children_ids.append(existing_child_id)
        
        return group_node.node_id
    
    def reparent_node(self, node_id, new_parent_id):
        """노드를 다른 부모로 재배치합니다."""
        node = self.get_node(node_id)
        new_parent = self.get_node(new_parent_id)
        
        if not node or not new_parent or node_id == self.root_node_id:
            return False
        
        old_parent_id = node.parent_id
        old_parent = self.get_node(old_parent_id)
        
        # 기존 부모에서 제거
        if old_parent and node_id in old_parent.children_ids:
            old_parent.children_ids.remove(node_id)
        
        # 새 부모에 추가
        node.parent_id = new_parent_id
        new_parent.children_ids.append(node_id)
        
        return True
    
    def replace_child(self, parent_id, old_child_id, new_child_id):
        """부모의 자식을 교체합니다."""
        parent = self.get_node(parent_id)
        if not parent or old_child_id not in parent.children_ids:
            return False
        
        # 자식 목록에서 교체
        child_index = parent.children_ids.index(old_child_id)
        parent.children_ids[child_index] = new_child_id
        
        # 새 자식의 부모 설정
        new_child = self.get_node(new_child_id)
        if new_child:
            new_child.parent_id = parent_id
        
        return True
    
    def create_category_node(self, topic, summary, parent_id):
        """카테고리 노드를 생성합니다."""
        node = MemoryNode(
            topic=topic,
            summary=summary,
            parent_id=parent_id,
            coordinates={"start": -1, "end": -1}  # 카테고리 표시
        )
        return node
    
    def create_conversation_node(self, topic, summary, parent_id, conversation_index):
        """대화 노드(리프)를 생성합니다."""
        node = MemoryNode(
            topic=topic,
            summary=summary,
            parent_id=parent_id,
            coordinates={"start": conversation_index, "end": conversation_index}
        )
        node.conversation_indices = [conversation_index]
        return node
    
    def merge_leaf_nodes(self, main_node_id, *other_node_ids):
        """여러 리프 노드를 하나로 병합합니다."""
        main_node = self.get_node(main_node_id)
        if not main_node:
            return False
        
        for other_id in other_node_ids:
            other_node = self.get_node(other_id)
            if not other_node:
                continue
            
            # 대화 인덱스 병합
            if hasattr(other_node, 'conversation_indices'):
                if not hasattr(main_node, 'conversation_indices'):
                    main_node.conversation_indices = []
                main_node.conversation_indices.extend(other_node.conversation_indices)
            
            # 부모에서 other_node 제거
            parent = self.get_node(other_node.parent_id)
            if parent and other_id in parent.children_ids:
                parent.children_ids.remove(other_id)
            
            # 트리에서 제거
            del self.memory_tree[other_id]
        
        # 중복 제거 및 정렬
        if hasattr(main_node, 'conversation_indices'):
            main_node.conversation_indices = sorted(list(set(main_node.conversation_indices)))
        
        return True
    
    def can_add_child_with_constraints(self, parent_id, config_manager):
        """트리 구조 제약을 고려하여 자식을 추가할 수 있는지 확인합니다."""
        parent_node = self.get_node(parent_id)
        if not parent_node:
            return False, "부모 노드가 존재하지 않습니다."
        
        # 팬아웃 제한 확인
        fanout_limit = config_manager.get('fanout_limit', 5)
        current_children_count = len(parent_node.children_ids)
        if current_children_count >= fanout_limit:
            return False, f"팬아웃 제한 초과: 현재 {current_children_count}개, 제한 {fanout_limit}개"
        
        # 최대 깊이 제한 확인
        max_depth = config_manager.get('max_depth', 5)
        parent_depth = self.get_node_depth(parent_id)
        if parent_depth + 1 > max_depth:
            return False, f"최대 깊이 초과: 현재 깊이 {parent_depth}, 최대 깊이 {max_depth}"
        
        return True, "제약 조건을 만족합니다."

    def calculate_node_distance(self, node_id1, node_id2):
        """두 노드 간의 최단 거리를 계산합니다 (간선 수 기반)."""
        if node_id1 == node_id2:
            return 0
        
        # BFS를 사용하여 최단 경로 찾기
        visited = set()
        queue = [(node_id1, 0)]  # (node_id, distance)
        
        while queue:
            current_id, distance = queue.pop(0)
            
            if current_id in visited:
                continue
            visited.add(current_id)
            
            if current_id == node_id2:
                return distance
            
            # 인접 노드 탐색 (부모와 자식)
            current_node = self.get_node(current_id)
            if not current_node:
                continue
            
            # 부모 노드
            if current_node.parent_id and current_node.parent_id not in visited:
                queue.append((current_node.parent_id, distance + 1))
            
            # 자식 노드들
            for child_id in current_node.children_ids:
                if child_id not in visited:
                    queue.append((child_id, distance + 1))
        
        # 경로가 없는 경우 (서로 다른 서브트리에 있는 경우)
        return float('inf')

    def get_nodes_within_k_distance(self, target_node_id, k):
        """특정 노드로부터 K-거리 이내의 모든 노드를 수집합니다."""
        nearby_nodes = []
        visited = set()
        queue = [(target_node_id, 0)]  # (node_id, distance)
        
        while queue:
            current_id, distance = queue.pop(0)
            
            if current_id in visited or distance > k:
                continue
            
            visited.add(current_id)
            current_node = self.get_node(current_id)
            
            if current_node and current_id != target_node_id:
                nearby_nodes.append(current_node)
            
            if distance < k:
                # 부모 방향 탐색
                if current_node and current_node.parent_id:
                    queue.append((current_node.parent_id, distance + 1))
                
                # 자식 방향 탐색
                if current_node:
                    for child_id in current_node.children_ids:
                        queue.append((child_id, distance + 1))
                
                # 형제 노드 탐색 (같은 부모를 가진 노드들)
                if current_node and current_node.parent_id:
                    parent_node = self.get_node(current_node.parent_id)
                    if parent_node:
                        for sibling_id in parent_node.children_ids:
                            if sibling_id != current_id:
                                queue.append((sibling_id, distance + 1))
        
        return nearby_nodes
