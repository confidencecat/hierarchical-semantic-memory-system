#!/usr/bin/env python3
"""
더 정확한 메모리 구조 수정 스크립트
"""

import json
import asyncio
from HSMS.MemoryManager import MemoryManager
from HSMS.AuxiliaryAI import AuxiliaryAI

async def fix_memory_structure_detailed():
    """메모리 구조를 상세하게 수정합니다."""
    print("=== 상세 메모리 구조 수정 시작 ===")
    
    memory_manager = MemoryManager(debug=True)
    aux_ai = AuxiliaryAI(memory_manager, debug=True)
    
    print(f"로드된 노드 수: {len(memory_manager.memory_tree)}")
    
    # 각 노드의 상태를 상세히 분석
    print("\n=== 노드 상태 분석 ===")
    problems = []
    
    for node_id, node in memory_manager.memory_tree.items():
        is_category = node.coordinates["start"] == -1 and node.coordinates["end"] == -1
        has_conversations = hasattr(node, 'conversation_indices') and len(node.conversation_indices) > 0
        
        print(f"노드: {node.topic} ({node_id[:8]}...)")
        print(f"  좌표: {node.coordinates}")
        print(f"  카테고리: {is_category}")
        print(f"  대화 수: {len(node.conversation_indices) if hasattr(node, 'conversation_indices') else 0}")
        
        # 문제 케이스 1: 카테고리인데 대화를 가지고 있음
        if is_category and has_conversations:
            print(f"  ❌ 문제: 카테고리 노드가 {len(node.conversation_indices)}개 대화를 가지고 있음")
            problems.append({
                'type': 'category_with_conversations',
                'node': node,
                'conversations': node.conversation_indices.copy()
            })
            
        # 문제 케이스 2: 대화 노드인데 좌표가 0,0인 경우 (다중 대화)
        elif not is_category and has_conversations and len(node.conversation_indices) > 1:
            print(f"  ⚠️  주의: 대화 노드가 {len(node.conversation_indices)}개 대화를 가지고 있음")
            if node.coordinates["start"] == 0 and node.coordinates["end"] == 0:
                print(f"    그리고 좌표가 0,0임 (첫 번째 대화 좌표로 변경 필요)")
                problems.append({
                    'type': 'multi_conversation_wrong_coords',
                    'node': node,
                    'conversations': node.conversation_indices.copy()
                })
                
        print()
    
    print(f"발견된 문제: {len(problems)}개")
    
    # 문제 수정
    if problems:
        print("\n=== 문제 수정 시작 ===")
        
        for i, problem in enumerate(problems):
            node = problem['node']
            conversations = problem['conversations']
            
            print(f"\n{i+1}. 문제 노드: '{node.topic}' 수정 중...")
            
            if problem['type'] == 'category_with_conversations':
                # 카테고리 노드에서 대화 제거
                print(f"   카테고리 노드에서 {len(conversations)}개 대화 제거")
                node.conversation_indices = []
                
            elif problem['type'] == 'multi_conversation_wrong_coords':
                # 첫 번째 대화 인덱스로 좌표 수정
                first_conv = conversations[0]
                print(f"   좌표를 {first_conv},{first_conv}로 수정")
                node.coordinates = {"start": first_conv, "end": first_conv}
    
    # 부모 노드 요약 재생성
    print("\n=== 부모 노드 요약 재생성 ===")
    
    # 카테고리 노드들의 요약을 자식들로부터 재생성
    category_nodes = [node for node in memory_manager.memory_tree.values() 
                     if (node.coordinates["start"] == -1 and 
                         node.coordinates["end"] == -1 and 
                         node.topic != "ROOT")]
    
    for node in category_nodes:
        if node.children_ids:
            print(f"'{node.topic}' 요약 재생성 중... (자식 {len(node.children_ids)}개)")
            await aux_ai.update_parent_summary(node)
    
    # ROOT 노드도 업데이트
    root_node = memory_manager.get_root_node()
    if root_node and root_node.children_ids:
        print(f"ROOT 요약 재생성 중... (자식 {len(root_node.children_ids)}개)")
        await aux_ai.update_parent_summary(root_node)
    
    # 수정사항 저장
    print("\n=== 수정사항 저장 ===")
    memory_manager.save_tree()
    
    # 최종 검증
    print("\n=== 최종 검증 ===")
    
    problems_found = 0
    for node_id, node in memory_manager.memory_tree.items():
        is_category = node.coordinates["start"] == -1 and node.coordinates["end"] == -1
        has_conversations = hasattr(node, 'conversation_indices') and len(node.conversation_indices) > 0
        
        if is_category and has_conversations:
            print(f"❌ 여전히 문제: 카테고리 '{node.topic}'이 {len(node.conversation_indices)}개 대화를 가짐")
            problems_found += 1
    
    if problems_found == 0:
        print("✅ 모든 구조적 문제가 해결되었습니다!")
    else:
        print(f"❌ {problems_found}개의 문제가 여전히 남아있습니다.")

if __name__ == "__main__":
    asyncio.run(fix_memory_structure_detailed())
