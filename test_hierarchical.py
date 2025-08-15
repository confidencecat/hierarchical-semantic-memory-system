#!/usr/bin/env python3
"""
계층적 의미 기억 시스템 테스트 스크립트
"""

from hierarchical_main import MainAI, MemoryManager, AuxiliaryAI

def test_hierarchical_structure():
    """계층적 구조 테스트"""
    # 시스템 초기화
    memory_manager = MemoryManager()
    auxiliary_ai = AuxiliaryAI(memory_manager)
    
    print("=== 계층적 구조 테스트 시작 ===\n")
    
    # 과일 관련 테스트
    test_cases = [
        "딸기는 어떤 과일인가요?",
        "딸기의 영양가는?",
        "바나나에 대해 궁금해요",
        "바나나 칼로리는?",
        "오렌지 비타민C가 많나요?",
        "수박은 언제 먹는게 좋나요?",
        
        # 동물 관련 테스트
        "고양이는 어떤 동물인가요?",
        "고양이 사료는 뭘 주나요?",
        "강아지 훈련법이 궁금해요",
        
        # 음식 관련 테스트  
        "김치찌개 만드는 법",
        "라면 끓이는 방법",
        
        # 학교 관련 테스트
        "영어 공부법이 궁금해요",
        "과학 실험 재미있어요"
    ]
    
    for i, query in enumerate(test_cases, 1):
        print(f"--- 테스트 {i} ---")
        print(f"Q: {query}")
        
        conversation = [
            {'role': 'user', 'content': query},
            {'role': 'assistant', 'content': f"{query}에 대한 답변입니다."}
        ]
        
        # 대화 처리
        auxiliary_ai.handle_conversation(conversation)
        
        # 현재 트리 구조 출력
        tree_summary = memory_manager.get_tree_summary(max_depth=2)
        node_count = len(memory_manager.memory_tree)
        print(f"트리 노드 수: {node_count}")
        print()
    
    # 최종 트리 구조 출력
    print("=== 최종 계층적 트리 구조 ===")
    final_tree = memory_manager.get_tree_summary(max_depth=3)
    print(final_tree)

if __name__ == "__main__":
    test_hierarchical_structure()
