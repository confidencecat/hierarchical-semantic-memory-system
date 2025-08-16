import uuid


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
