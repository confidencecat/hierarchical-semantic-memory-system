from .AIManager import AIManager


class LoadAI:
    """로드 인공지능 - 트리 구조에서 관련 정보를 검색 (레거시 호환용)"""
    
    def __init__(self, memory_manager):
        self.memory_manager = memory_manager
        self.ai_manager = AIManager()
    
    def search_tree(self, query):
        """트리에서 쿼리와 관련된 노드들을 찾습니다. (레거시 호환용)"""
        # 이 함수는 이제 MainAI에서 직접 처리되므로 단순화
        return None
