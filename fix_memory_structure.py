#!/usr/bin/env python3
"""
메모리 구조 수정 스크립트
- 카테고리 노드에서 conversation_indices 제거
- 잘못된 좌표를 가진 노드들 수정
- 부모 노드 요약 재생성
"""

import json
import asyncio
from HSMS.MemoryManager import MemoryManager
from HSMS.AuxiliaryAI import AuxiliaryAI
from HSMS.DataManager import DataManager
from HSMS.ConfigManager import ConfigManager

async def fix_memory_structure():
    """메모리 구조를 수정합니다."""
    print("=== 메모리 구조 수정 시작 ===")
    
    # 설정 및 매니저 초기화
    config_manager = ConfigManager()
    data_manager = DataManager()
    memory_manager = MemoryManager()
    aux_ai = AuxiliaryAI(memory_manager, debug=True)
    
    # 메모리 로드 (이미 initialize_tree에서 자동으로 로드됨)
    # memory_manager.initialize_tree()  # 이미 __init__에서 호출됨
    
    print(f"로드된 노드 수: {len(memory_manager.memory_tree)}")
    
    # 1. 카테고리 노드에서 conversation_indices 제거
    print("\n1. 카테고리 노드 정리 중...")
    category_nodes_fixed = 0
    talk_nodes_found = 0
    
    for node_id, node in memory_manager.memory_tree.items():
        if node.coordinates["start"] == -1 and node.coordinates["end"] == -1:
            # 카테고리 노드
            if hasattr(node, 'conversation_indices') and node.conversation_indices:
                print(f"  카테고리 노드 '{node.topic}' ({node_id[:8]}...)에서 {len(node.conversation_indices)}개 대화 제거")
                node.conversation_indices = []
                category_nodes_fixed += 1
        else:
            # 대화 노드
            talk_nodes_found += 1
            if not hasattr(node, 'conversation_indices'):
                node.conversation_indices = []
    
    print(f"  수정된 카테고리 노드: {category_nodes_fixed}개")
    print(f"  발견된 대화 노드: {talk_nodes_found}개")
    
    # 2. 잘못된 좌표를 가진 노드들 확인
    print("\n2. 노드 좌표 검증 중...")
    coordinate_issues = 0
    
    for node_id, node in memory_manager.memory_tree.items():
        if node.topic == "ROOT":
            continue
            
        # 대화를 가지고 있는데 카테고리 좌표인 경우
        if (hasattr(node, 'conversation_indices') and 
            len(node.conversation_indices) > 0 and 
            node.coordinates["start"] == -1):
            print(f"  문제 노드 발견: '{node.topic}' - 대화를 가지지만 카테고리 좌표")
            coordinate_issues += 1
            
            # 첫 번째 대화 인덱스로 좌표 설정
            if node.conversation_indices:
                first_conv = node.conversation_indices[0]
                node.coordinates = {"start": first_conv, "end": first_conv}
                print(f"    좌표 수정: {first_conv} -> {first_conv}")
    
    print(f"  좌표 문제 수정된 노드: {coordinate_issues}개")
    
    # 3. 부모 노드 요약 재생성
    print("\n3. 부모 노드 요약 재생성 중...")
    
    # 모든 카테고리 노드의 요약을 자식들로부터 재생성
    category_nodes = [node for node in memory_manager.memory_tree.values() 
                     if node.coordinates["start"] == -1 and node.coordinates["end"] == -1]
    
    for node in category_nodes:
        if node.topic == "ROOT":
            continue
            
        if node.children_ids:
            print(f"  '{node.topic}' 요약 재생성 중... (자식 {len(node.children_ids)}개)")
            await aux_ai.update_parent_summary(node)
    
    # ROOT 노드도 업데이트
    root_node = memory_manager.get_root_node()
    if root_node and root_node.children_ids:
        print(f"  ROOT 요약 재생성 중... (자식 {len(root_node.children_ids)}개)")
        await aux_ai.update_parent_summary(root_node)
    
    # 4. 메모리 저장
    print("\n4. 수정된 메모리 저장 중...")
    memory_manager.save_tree()
    
    print("\n=== 메모리 구조 수정 완료 ===")
    
    # 5. 수정 결과 검증
    print("\n=== 수정 결과 검증 ===")
    
    total_nodes = len(memory_manager.memory_tree)
    category_nodes = sum(1 for node in memory_manager.memory_tree.values() 
                        if node.coordinates["start"] == -1)
    talk_nodes = sum(1 for node in memory_manager.memory_tree.values() 
                    if node.coordinates["start"] != -1)
    
    print(f"총 노드 수: {total_nodes}")
    print(f"카테고리 노드: {category_nodes}개")
    print(f"대화 노드: {talk_nodes}개")
    
    # 카테고리 노드가 대화를 가지고 있는지 검사
    problematic_categories = 0
    for node in memory_manager.memory_tree.values():
        if (node.coordinates["start"] == -1 and 
            hasattr(node, 'conversation_indices') and 
            len(node.conversation_indices) > 0):
            print(f"⚠️  여전히 문제가 있는 카테고리 노드: '{node.topic}'")
            problematic_categories += 1
    
    if problematic_categories == 0:
        print("✅ 모든 카테고리 노드가 정상입니다!")
    else:
        print(f"❌ {problematic_categories}개 카테고리 노드에 여전히 문제가 있습니다.")

if __name__ == "__main__":
    asyncio.run(fix_memory_structure())
