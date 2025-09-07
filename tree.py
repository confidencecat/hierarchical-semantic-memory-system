import asyncio
from config import debug_print, FANOUT_LIMIT, MAX_SEARCH_DEPTH, MAX_SUMMARY_LENGTH, UPDATE_TOPIC
from memory import load_json, save_json, get_node_data, save_node_data, create_new_node, update_all_memory
from ai_func import judgement_similar_multi_AI, summary_AI, topic_generation_AI, clustering_AI, parent_update_AI

# 전역 설정
SIMILARITY_THRESHOLD = 0.7  # 기존 노드에 추가하는 임계값 (엄격하게)
EXPLORATION_THRESHOLD = 0.5  # 탐색을 계속하는 임계값 (적당하게)

# ROOT 노드의 자식 ID들 조회
def get_root_children_ids():
    """ROOT 노드의 직접 자식들 반환"""
    hierarchical_memory = load_json('memory/hierarchical_memory.json', {})
    root_children = []
    
    for node_id, node_data in hierarchical_memory.items():
        if node_data.get('direct_parent_id') is None:  # ROOT의 직접 자식
            root_children.append(node_id)
    
    return root_children

# 특정 노드의 자식 ID들 조회
def get_children_ids(node_id):
    """특정 노드의 자식 ID들 반환"""
    if node_id == "ROOT":
        return get_root_children_ids()
    
    node_data = get_node_data(node_id)
    if node_data:
        return node_data.get('children_ids', [])
    return []

# 기억 노드(자식이 없는 노드)만 필터링
def get_memory_children_ids(parent_id):
    """부모 노드의 자식 중 기억 노드(자식이 없는 노드)만 반환"""
    children_ids = get_children_ids(parent_id)
    memory_nodes = []
    
    for child_id in children_ids:
        child_data = get_node_data(child_id)
        if child_data and not child_data.get('children_ids'):  # 자식이 없으면 기억 노드
            memory_nodes.append(child_id)
    
    return memory_nodes

# BFS 기반 트리 검색
async def search_tree(current_conversation):
    """
    BFS(너비 우선 탐색) 방식으로 관련 기억을 탐색
    """
    # 초기화
    current_level_nodes = get_root_children_ids()
    visited = set()
    found_memories = []
    depth = 1
    
    debug_print(f"BFS 검색 시작 (초기 노드: {len(current_level_nodes)}개)")
    
    while current_level_nodes and depth <= MAX_SEARCH_DEPTH:
        debug_print(f"깊이 {depth} 탐색 중 ({len(current_level_nodes)}개 노드)")
        
        # 방문하지 않은 노드만 필터링
        unvisited_nodes = [node_id for node_id in current_level_nodes if node_id not in visited]
        
        if not unvisited_nodes:
            break
        
        # 현재 레벨의 모든 노드에 대해 병렬 유사도 검사
        similarity_results = await judgement_similar_multi_AI(
            unvisited_nodes, current_conversation
        )
        
        next_level_nodes = []
        
        for i, node_id in enumerate(unvisited_nodes):
            visited.add(node_id)
            
            # 유사도 점수로 판단
            try:
                similarity_score = float(similarity_results[i].strip())
            except (ValueError, IndexError):
                # 숫자로 변환 실패 시 기존 방식으로 fallback
                if similarity_results[i].strip().lower() == 'true':
                    similarity_score = 0.8
                else:
                    similarity_score = 0.0
            
            # 최소 탐색 임계값 확인
            if similarity_score > EXPLORATION_THRESHOLD:
                node_data = get_node_data(node_id)
                if not node_data:
                    continue
                
                # 기억 노드인 경우 (자식이 없는 경우)
                if not node_data.get('children_ids'):
                    found_memories.extend(node_data.get('all_memory_indexes', []))
                    debug_print(f"기억 발견: 노드 {node_id[:8]}... ({len(node_data.get('all_memory_indexes', []))}개 대화)")
                
                # 부모 노드인 경우 (자식이 있는 경우)
                else:
                    children = node_data.get('children_ids', [])
                    next_level_nodes.extend(children)
                    debug_print(f"하위 탐색: 노드 {node_id[:8]}... ({len(children)}개 자식)")
        
        current_level_nodes = next_level_nodes
        depth += 1
    
    debug_print(f"BFS 검색 완료 (발견된 기억: {len(found_memories)}개)")
    return found_memories

# 최적 자식 노드 찾기 (저장 위치 탐색용)
async def find_best_matching_child(children_ids, conversation_pair):
    """가장 유사한 자식 노드 찾기"""
    if not children_ids:
        return None
    
    # 대화를 문자열로 변환
    conversation_str = ""
    for msg in conversation_pair:
        role = msg.get('role', 'user')
        content = msg.get('content', '')
        conversation_str += f"{role}: {content}\n"
    
    # 유사도 검사
    similarity_results = await judgement_similar_multi_AI(children_ids, conversation_str)
    
    best_match = None
    best_score = 0.0
    
    for i, child_id in enumerate(children_ids):
        child_data = get_node_data(child_id)
        if not child_data:
            continue
        
        # 유사도 결과를 점수로 변환
        # 원래 점수로 안하는데 조절이 힘들어서 점수 방식을 사용함
        try:
            similarity_score = float(similarity_results[i].strip())
        except (ValueError, IndexError):
            # 숫자로 변환 실패 시 기존 방식으로 fallback
            # 이런 경우는 거의 발생하지 않음
            if similarity_results[i].strip().lower() == 'true':
                similarity_score = 0.8  # True인 경우 중간 점수
            else:
                similarity_score = 0.0
        
        if similarity_score > best_score:
            best_score = similarity_score
            best_match = {
                'node_id': child_id,
                'similarity_score': similarity_score,
                'is_memory_node': not bool(child_data.get('children_ids'))
            }
    
    return best_match

# 저장 위치 탐색
async def find_storage_location(conversation_pair):
    """저장할 위치를 탐색하는 함수"""
    current_node_id = "ROOT"
    depth = 0
    max_storage_depth = MAX_SEARCH_DEPTH
    
    while depth < max_storage_depth:
        children = get_children_ids(current_node_id)
        
        if not children:
            # 리프 노드 도달
            return {
                'parent_id': current_node_id,
                'existing_memory_node': False
            }
        
        # 가장 유사한 자식 노드 찾기
        best_match = await find_best_matching_child(children, conversation_pair)
        
        if not best_match:
            # 유사한 자식 없음
            return {
                'parent_id': current_node_id,
                'existing_memory_node': False
            }
        
        if best_match['is_memory_node'] and best_match['similarity_score'] > SIMILARITY_THRESHOLD:
            # 기존 기억 노드에 추가
            return {
                'node_id': best_match['node_id'],
                'existing_memory_node': True
            }
        elif best_match['similarity_score'] > EXPLORATION_THRESHOLD:
            # 더 깊이 탐색
            current_node_id = best_match['node_id']
            depth += 1
        else:
            # 유사한 노드 없음, 현재 위치에 새 노드 생성
            return {
                'parent_id': current_node_id,
                'existing_memory_node': False
            }
    
    # 최대 깊이 도달
    return {
        'parent_id': current_node_id,
        'existing_memory_node': False
    }

# 기존 노드에 대화 추가
async def add_to_existing_node(node_id, memory_index, conversation_summary):
    """기존 기억 노드에 새 대화 추가"""
    node_data = get_node_data(node_id)
    if not node_data:
        debug_print(f"ERROR: 노드 {node_id} 데이터를 찾을 수 없습니다.")
        return False
    
    # 기억 인덱스 추가
    memory_indexes = node_data.get('all_memory_indexes', [])
    memory_indexes.append(memory_index)
    node_data['all_memory_indexes'] = memory_indexes
    
    # 요약 업데이트
    current_summary = node_data.get('summary', '')
    node_data['summary'] = f"{current_summary}\n{conversation_summary}"
    
    # 길이 체크 후 압축 (필요시)
    if len(node_data['summary']) > MAX_SUMMARY_LENGTH:
        compressed_summary, new_topic = parent_update_AI(
            node_data['summary'], 
            MAX_SUMMARY_LENGTH
        )
        node_data['summary'] = compressed_summary
        if new_topic:
            node_data['topic'] = new_topic
    
    # 노드 저장
    success = save_node_data(node_id, node_data)
    if success:
        debug_print(f"기존 노드에 대화 추가 완료: {node_id[:8]}...")
        # 부모 노드들 업데이트
        await update_parent_nodes(node_id, conversation_summary)
    
    return success

# fanout 제한 확인
def will_exceed_fanout_limit(parent_id):
    """새 노드 추가 시 fanout 제한을 초과하는지 확인"""
    children = get_children_ids(parent_id)
    return len(children) >= FANOUT_LIMIT

# 새 기억 노드 생성
async def create_new_memory_node(parent_id, memory_index, conversation_summary):
    """새로운 기억 노드 생성"""
    # 주제명 생성
    topic = topic_generation_AI(conversation_summary)
    
    # 노드 생성
    new_node_id = create_new_node(
        topic=topic,
        summary=conversation_summary,
        parent_id=parent_id if parent_id != "ROOT" else None,
        memory_indexes=[memory_index]
    )
    
    if new_node_id:
        debug_print(f"새 기억 노드 생성 완료: '{topic}' (ID: {new_node_id[:8]}...)")
        # 부모 노드들 업데이트
        await update_parent_nodes(new_node_id, conversation_summary)
        return new_node_id
    else:
        debug_print("ERROR: 새 기억 노드 생성 실패")
        return None

# 클러스터링 수행
async def perform_clustering(parent_id, new_memory_index, new_conversation_summary):
    """Fanout 제한 초과 시 클러스터링 수행"""
    debug_print(f"클러스터링 시작 (부모: {parent_id[:8] if parent_id != 'ROOT' else 'ROOT'}...)")
    
    # 1. 현재 부모의 모든 기억 자식 노드 획득
    memory_children_ids = get_memory_children_ids(parent_id)
    
    if len(memory_children_ids) < 2:
        # 클러스터링할 노드가 부족하면 그냥 새 노드 생성
        debug_print("클러스터링할 노드가 부족합니다. 새 노드 생성으로 전환")
        return await create_new_memory_node(parent_id, new_memory_index, new_conversation_summary)
    
    # 2. 클러스터링 대상 선택, 인공지능이 사용할 노드를 반환함.
    selected_node_ids, new_parent_topic = await clustering_AI(
        memory_children_ids, 
        new_conversation_summary, 
        FANOUT_LIMIT
    )
    
    if not selected_node_ids:
        # 클러스터링 실패 시 첫 번째 노드와 함께 클러스터링
        selected_node_ids = memory_children_ids[:min(2, len(memory_children_ids))]
        new_parent_topic = "관련 주제"
    
    # 3. 새로운 중간 부모 노드 생성
    new_parent_id = create_new_node(
        topic=new_parent_topic,
        summary="",  # 나중에 업데이트할 예정ㅇ
        parent_id=parent_id if parent_id != "ROOT" else None,
        memory_indexes=[]
    )
    
    if not new_parent_id:
        debug_print("ERROR: 새 부모 노드 생성 실패")
        return None
    
    # 4. 선택된 노드들을 새 부모 밑으로 이동
    all_memory_indexes = [new_memory_index]
    combined_summaries = [new_conversation_summary]
    
    for node_id in selected_node_ids:
        node_data = get_node_data(node_id)
        if node_data:
            # 부모 변경
            node_data['direct_parent_id'] = new_parent_id
            node_data['all_parent_ids'] = node_data.get('all_parent_ids', []) + [new_parent_id]
            save_node_data(node_id, node_data)
            
            # 데이터 수집
            all_memory_indexes.extend(node_data.get('all_memory_indexes', []))
            combined_summaries.append(node_data.get('summary', ''))
        
        # 기존 부모에서 제거
        if parent_id != "ROOT":
            parent_data = get_node_data(parent_id)
            if parent_data and node_id in parent_data.get('children_ids', []):
                parent_data['children_ids'].remove(node_id)
                save_node_data(parent_id, parent_data)
    
    # 5. 새 기억 노드 생성 (현재 대화용)
    new_memory_node_id = await create_new_memory_node(new_parent_id, new_memory_index, new_conversation_summary)
    
    # 6. 새 부모 노드 업데이트
    new_parent_data = get_node_data(new_parent_id)
    if new_parent_data:
        new_parent_data['children_ids'] = selected_node_ids + ([new_memory_node_id] if new_memory_node_id else [])
        # 통합 요약 생성
        combined_summary = summary_AI([{"role": "system", "content": "\n".join(combined_summaries)}])
        new_parent_data['summary'] = combined_summary
        save_node_data(new_parent_id, new_parent_data)
    
    debug_print(f"클러스터링 완료 (새 부모: '{new_parent_topic}', 통합된 노드: {len(selected_node_ids)}개)")
    return new_parent_id

# 부모 노드들 업데이트
async def update_parent_nodes(updated_node_id, new_content_summary):
    """부모 노드들의 요약과 주제를 업데이트"""
    if updated_node_id == "ROOT":
        return
    
    node_data = get_node_data(updated_node_id)
    if not node_data:
        return
    
    all_parent_ids = node_data.get('all_parent_ids', [])
    
    if not all_parent_ids:
        return  # ROOT 직속 자식인 경우
    
    # 1. 요약 이어붙이기 (순차적 처리)
    need_compression = []
    
    for parent_id in all_parent_ids:
        parent_data = get_node_data(parent_id)
        if not parent_data:
            continue
        
        parent_data['summary'] = parent_data.get('summary', '') + f"\n{new_content_summary}"
        
        # 길이 체크
        if len(parent_data['summary']) > MAX_SUMMARY_LENGTH:
            if UPDATE_TOPIC in ['smart', 'always']:
                need_compression.append(parent_id)
            elif UPDATE_TOPIC == 'never':
                debug_print(f"경고: 노드 {parent_id[:8]}... 요약 길이 초과 ({len(parent_data['summary'])}/{MAX_SUMMARY_LENGTH})")
        
        save_node_data(parent_id, parent_data)
    
    # 2. 병렬 압축 처리 (필요한 경우)
    if need_compression:
        debug_print(f"부모 노드 압축 시작 ({len(need_compression)}개)")
        
        for parent_id in need_compression:
            parent_data = get_node_data(parent_id)
            if parent_data:
                new_summary, new_topic = parent_update_AI(
                    parent_data['summary'], 
                    MAX_SUMMARY_LENGTH
                )
                parent_data['summary'] = new_summary
                if new_topic:
                    parent_data['topic'] = new_topic
                save_node_data(parent_id, parent_data)
        
        debug_print(f"부모 노드 압축 완료 ({len(need_compression)}개)")

# 대화 저장 메인 함수
async def save_tree(conversation_pair):
    """새로운 대화를 적절한 위치에 저장"""
    debug_print("대화 저장 프로세스 시작")
    
    # 1. 대화를 ALL_MEMORY에 추가하고 인덱스 획득
    memory_index = update_all_memory(conversation_pair)
    if memory_index == -1:
        debug_print("ERROR: ALL_MEMORY 업데이트 실패")
        return False
    
    # 2. 대화 요약 생성
    conversation_summary = summary_AI(conversation_pair, MAX_SUMMARY_LENGTH)
    
    # 3. 저장 위치 탐색
    target_location = await find_storage_location(conversation_pair)
    
    # 4. 기존 기억 노드에 추가 vs 새 노드 생성 결정
    if target_location.get('existing_memory_node'):
        # 기존 기억 노드에 추가
        success = await add_to_existing_node(
            target_location['node_id'], 
            memory_index, 
            conversation_summary
        )
    else:
        # 새 기억 노드 생성 필요
        parent_id = target_location.get('parent_id', "ROOT")
        
        # Fanout 제한 확인
        if will_exceed_fanout_limit(parent_id):
            # 클러스터링 수행
            success = await perform_clustering(parent_id, memory_index, conversation_summary)
        else:
            # 직접 새 노드 생성
            success = await create_new_memory_node(parent_id, memory_index, conversation_summary)
    
    debug_print("대화 저장 프로세스 완료")
    return bool(success)
