import os
from config import HIERARCHICAL_MEMORY, ALL_MEMORY
from .DataManager import DataManager
from .MemoryNode import MemoryNode


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
