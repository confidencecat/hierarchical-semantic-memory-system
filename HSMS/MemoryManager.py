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
        """새 노드를 트리에 추가합니다."""
        if self.debug:
            print(f"    ┌─ [MEMORY] 노드 추가")
            print(f"    │  노드 ID: {node.node_id}")
            print(f"    │  토픽: {node.topic}")
            print(f"    │  부모 ID: {parent_id}")
        
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
