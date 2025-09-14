import json
import os
import uuid
import shutil
from datetime import datetime
from config import debug_print, get_timestamp

# JSON 파일 안전 저장
def save_json(file_path: str, data, backup: bool = False) -> bool:
    """
    딕셔너리 데이터를 JSON 파일로 안전하게 저장
    Args:
        file_path: 저장할 파일 경로
        data: 저장할 데이터
        backup: 기존 파일 백업 여부 (기본값: False)
    Returns:
        bool: 저장 성공 여부
    """
    try:
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        # 임시 파일에 저장(원자적 쓰기)
        temp_path = f"{file_path}.tmp"
        with open(temp_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        # 임시 파일을 실제 파일로 이동
        shutil.move(temp_path, file_path)
        # debug_print(f"JSON saved successfully: {file_path}")
        return True
        
    except Exception as e:
        debug_print(f"Error saving JSON {file_path}: {e}")
        # 임시 파일
        if os.path.exists(f"{file_path}.tmp"):
            os.remove(f"{file_path}.tmp")
        return False

# JSON 파일 안전 로드
def load_json(file_path: str, default=None):
    try:
        if not os.path.exists(file_path):
            # debug_print(f"File not found: {file_path}, returning default")
            return default
        
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # debug_print(f"JSON loaded successfully: {file_path}")
        return data
        
    except json.JSONDecodeError as e:
        debug_print(f"JSON decode error in {file_path}: {e}")
        # 백업 파일 복구 시도
        backup_path = f"{file_path}.backup"
        if os.path.exists(backup_path):
            debug_print(f"Attempting recovery from backup: {backup_path}")
            try:
                with open(backup_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                debug_print("Recovery from backup successful")
                return data
            except Exception as backup_error:
                debug_print(f"Backup recovery failed: {backup_error}")
        
        return default
        
    except Exception as e:
        debug_print(f"Error loading JSON {file_path}: {e}")
        return default

# ALL_MEMORY에 새 대화 추가
def update_all_memory(new_conversation: list) -> int:
    try:
        # 기존 ALL_MEMORY 로드
        all_memory = load_json('memory/all_memory.json', [])
        
        # 새 대화 추가
        all_memory.append(new_conversation)
        index = len(all_memory) - 1
        
        # 파일 저장
        if save_json('memory/all_memory.json', all_memory):
            debug_print(f"New conversation added to all_memory.json at index {index}")
            return index
        else:
            debug_print("Failed to save all_memory.json")
            return -1
            
    except Exception as e:
        debug_print(f"Error updating all_memory: {e}")
        return -1

# 노드 데이터 조회
def get_node_data(node_id: str):
    try:
        hierarchical_memory = load_json('memory/hierarchical_memory.json', {})
        return hierarchical_memory.get(node_id, None)
        
    except Exception as e:
        debug_print(f"Error getting node data for {node_id}: {e}")
        return None

# 노드 데이터 저장
def save_node_data(node_id: str, node_data: dict) -> bool:
    try:
        # 기존 계층 메모리 로드
        hierarchical_memory = load_json('memory/hierarchical_memory.json', {})
        
        # 노드 데이터 업데이트
        hierarchical_memory[node_id] = node_data
        
        # 파일 저장
        success = save_json('memory/hierarchical_memory.json', hierarchical_memory)
        if success:
            debug_print(f"Node data saved for {node_id}")
        else:
            debug_print(f"Failed to save node data for {node_id}")
        
        return success
        
    except Exception as e:
        debug_print(f"Error saving node data for {node_id}: {e}")
        return False

# 새 노드 생성
def create_new_node(topic: str, summary: str, parent_id: str = None, memory_indexes: list = None) -> str:
    try:
        # 새 노드 ID 생성
        new_node_id = str(uuid.uuid4())
        
        # 부모 경로 계산
        all_parent_ids = []
        if parent_id:
            parent_data = get_node_data(parent_id)
            if parent_data:
                all_parent_ids = parent_data.get('all_parent_ids', []) + [parent_id]
        
        # 노드 데이터 구성
        node_data = {
            "node_id": new_node_id,
            "topic": topic,
            "summary": summary,
            "direct_parent_id": parent_id,
            "all_parent_ids": all_parent_ids,
            "children_ids": [],
            "all_memory_indexes": memory_indexes if memory_indexes else []
        }
        
        # 노드 저장
        if save_node_data(new_node_id, node_data):
            # 부모 노드에 자식으로 추가
            if parent_id:
                parent_data = get_node_data(parent_id)
                if parent_data:
                    parent_data['children_ids'].append(new_node_id)
                    save_node_data(parent_id, parent_data)
                    debug_print(f"Added {new_node_id} as child to {parent_id}")
            
            debug_print(f"New node created: {new_node_id} - {topic}")
            return new_node_id
        else:
            debug_print(f"Failed to create new node: {topic}")
            return None
            
    except Exception as e:
        debug_print(f"Error creating new node {topic}: {e}")
        return None

# 데이터 구조 검증
def validate_data_structure() -> bool:
    """
    JSON 파일들의 데이터 구조 검증
    Returns:
        bool: 검증 성공 여부
    """
    try:
        # all_memory.json 검증
        all_memory = load_json('memory/all_memory.json', [])
        if not isinstance(all_memory, list):
            debug_print("ERROR: all_memory.json should be a list")
            return False
        
        # hierarchical_memory.json 검증
        hierarchical_memory = load_json('memory/hierarchical_memory.json', {})
        if not isinstance(hierarchical_memory, dict):
            debug_print("ERROR: hierarchical_memory.json should be a dictionary")
            return False
        
        # 노드 구조 검증
        for node_id, node_data in hierarchical_memory.items():
            required_fields = ['node_id', 'topic', 'summary', 'direct_parent_id', 
                             'all_parent_ids', 'children_ids', 'all_memory_indexes']
            for field in required_fields:
                if field not in node_data:
                    debug_print(f"ERROR: Missing field {field} in node {node_id}")
                    return False
        
        debug_print("Data structure validation passed")
        return True
        
    except Exception as e:
        debug_print(f"Error during data structure validation: {e}")
        return False

def initialize_json_files():
    """초기 JSON 파일들을 생성"""
    try:
        # all_memory.json 초기화
        if not os.path.exists('memory/all_memory.json'):
            save_json('memory/all_memory.json', [])
            debug_print("Created all_memory.json")
        
        # hierarchical_memory.json 초기화
        if not os.path.exists('memory/hierarchical_memory.json'):
            save_json('memory/hierarchical_memory.json', {})
            debug_print("Created hierarchical_memory.json")
        
        return True
        
    except Exception as e:
        debug_print(f"Error initializing JSON files: {e}")
        return False
