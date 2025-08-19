import uuid


class MemoryNode:
    """계층적 기억 시스템의 개별 노드를 나타내는 클래스"""
    
    def __init__(self, node_id=None, topic=None, summary=None, parent_id=None, 
                 children_ids=None, coordinates=None, references=None, conversation_indices=None):
        self.node_id = node_id or str(uuid.uuid4())
        self.topic = topic or ""
        self.summary = summary or ""
        self.parent_id = parent_id
        self.children_ids = children_ids or []
        # 하위 호환성을 위해 coordinates 유지하되 사용하지 않음
        self.coordinates = coordinates or {"start": 0, "end": 0}
        self.references = references or []  # 다른 노드에 대한 참조 저장
        # 새로운 방식: 실제 관련 대화 인덱스들만 저장
        self.conversation_indices = conversation_indices or []
    
    def add_conversation(self, conversation_index):
        """대화 인덱스를 노드에 추가 (중복 방지)"""
        if not isinstance(conversation_index, int) or conversation_index < 0:
            raise ValueError(f"Invalid conversation_index: {conversation_index}")
        
        if conversation_index not in self.conversation_indices:
            self.conversation_indices.append(conversation_index)
            self.conversation_indices.sort()  # 정렬 유지
    
    def remove_conversation(self, conversation_index):
        """대화 인덱스를 노드에서 제거"""
        if not isinstance(conversation_index, int):
            raise ValueError(f"Invalid conversation_index: {conversation_index}")
            
        if conversation_index in self.conversation_indices:
            self.conversation_indices.remove(conversation_index)
    
    def get_conversation_count(self):
        """이 노드가 가진 대화 수 반환"""
        return len(self.conversation_indices)
    
    def to_dict(self):
        return {
            'node_id': self.node_id,
            'topic': self.topic,
            'summary': self.summary,
            'parent_id': self.parent_id,
            'children_ids': self.children_ids,
            'coordinates': self.coordinates,  # 하위 호환성
            'references': self.references,
            'conversation_indices': self.conversation_indices  # 새로운 방식
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
            references=data.get('references', []),
            conversation_indices=data.get('conversation_indices', [])  # 새로운 필드
        )
