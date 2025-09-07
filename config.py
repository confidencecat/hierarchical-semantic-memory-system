import os
import json
import time
from datetime import datetime
import uuid
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

# API 키 관리
AI_API = []
LOAD_API = []
AI_API_N = 0
LOAD_API_N = 0

# 환경 변수에서 API 키 로드
def load_api_keys():
    global AI_API, LOAD_API, AI_API_N, LOAD_API_N
    
    # AI_API 로드 (주요 처리용)
    ai_keys = []
    for i in range(1, 10):
        key = os.getenv(f'AI_{i}')
        if key and key.strip():
            ai_keys.append(key.strip())
    
    AI_API = ai_keys
    AI_API_N = len(AI_API)
    
    # LOAD_API 로드 (병렬 처리용)
    load_keys = []
    for i in range(1, 100):
        key = os.getenv(f'LOAD_{i}')
        if key and key.strip():
            load_keys.append(key.strip())
    
    LOAD_API = load_keys
    LOAD_API_N = len(LOAD_API)
    
    # 폴백 로직: AI_API가 없으면 LOAD_API의 일부를 사용
    if AI_API_N == 0 and LOAD_API_N > 0:
        AI_API = LOAD_API[:min(3, LOAD_API_N)]
        AI_API_N = len(AI_API)

load_api_keys()

# AI 모델 설정
GEMINI_MODEL = "gemini-2.5-flash"

# 시스템 설정
FANOUT_LIMIT = 5
MAX_SEARCH_DEPTH = 10
MAX_SUMMARY_LENGTH = 200  # 더 짧게 변경
UPDATE_TOPIC = "smart"  # always, smart, never
SEARCH_MODE = "efficiency"  # efficiency, force, no
NO_RECORD = False
DEBUG = True

# 테스트 데이터
TEST_Q = [
    # 예시 질문들
]

# 성능 모니터링
CALL_STATS = {
    'total_calls': 0,
    'total_time': 0.0,
    'parallel_calls': 0,
    'error_count': 0,
    'memory_searches': 0,
    'cache_hits': 0
}

# 시스템 상수
MAX_SEARCH_DEPTH = 10
MAX_STORAGE_DEPTH = 8
SIMILARITY_THRESHOLD = 0.7
EXPLORATION_THRESHOLD = 0.5

SYSTEM_MODE = "chat"
SEARCH_MODE = "efficiency"  
UPDATE_TOPIC = "never"
MODEL = "gemini-2.5-flash"
FANOUT_LIMIT = 5
MAX_SUMMARY_LENGTH = 2000
DEBUG = False
DEBUG_TXT = False
NO_RECORD = False

# 디버그 로그 파일 핸들과 파일명
debug_log_file = None
debug_log_filename = None

def get_timestamp():
    """현재 시간을 지정된 형식으로 반환"""
    return datetime.now().strftime("[%Y.%m.%d-%H:%M:%S]")

def debug_log_init():
    """디버그 로그 파일 초기화"""
    global debug_log_file, debug_log_filename
    if DEBUG_TXT:
        # 기존 파일이 열려있다면 닫기
        if debug_log_file:
            debug_log_file.close()
            debug_log_file = None
        
        # 새 파일명 생성 (매번 새로운 타임스탬프)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        debug_log_filename = f"debug_log_{timestamp}.txt"
        
        # 초기 메시지 쓰기
        try:
            with open(debug_log_filename, 'w', encoding='utf-8') as f:
                f.write(f"Debug log started at {get_timestamp()}\n")
                f.flush()
                os.fsync(f.fileno())
            print(f"디버그 로그 파일 생성: {debug_log_filename}")
        except Exception as e:
            print(f"디버그 로그 파일 생성 오류: {e}")

def debug_print(message, end='\n'):
    """타임스탬프가 포함된 디버그 메시지 출력"""
    timestamp = get_timestamp()
    formatted_message = f"{timestamp} >>> {message}"
    
    # 화면 출력 (DEBUG가 True일 때만)
    if DEBUG:
        print(formatted_message, end=end)
    
    # 파일 저장 (DEBUG_TXT가 True일 때는 항상) - 확실한 즉시 저장
    if DEBUG_TXT and debug_log_filename:
        try:
            with open(debug_log_filename, 'a', encoding='utf-8') as f:
                f.write(formatted_message + end)
                f.flush()
                os.fsync(f.fileno())  # OS 레벨 강제 디스크 쓰기
        except Exception as e:
            print(f"디버그 로그 쓰기 오류: {e}")

def debug_log_separator():
    """디버그 로그에 구분선 추가"""
    if DEBUG_TXT and debug_log_filename:
        separator = "=" * 60 + "\n"
        try:
            with open(debug_log_filename, 'a', encoding='utf-8') as f:
                f.write(separator)
                f.flush()
                os.fsync(f.fileno())
        except Exception as e:
            print(f"디버그 로그 구분선 쓰기 오류: {e}")

def debug_log_close():
    """디버그 로그 파일 닫기"""
    global debug_log_file, debug_log_filename
    if debug_log_file:
        debug_log_file.close()
        debug_log_file = None
    debug_log_filename = None

def create_uuid():
    """UUID4 문자열 생성"""
    return str(uuid.uuid4())

def load_config():
    """config.json에서 설정 로드"""
    global SYSTEM_MODE, SEARCH_MODE, UPDATE_TOPIC, MODEL, FANOUT_LIMIT, MAX_SUMMARY_LENGTH
    global DEBUG, DEBUG_TXT, NO_RECORD
    
    try:
        if os.path.exists('config.json'):
            with open('config.json', 'r', encoding='utf-8') as f:
                config = json.load(f)
                
            SYSTEM_MODE = config.get('SYSTEM_MODE', SYSTEM_MODE)
            SEARCH_MODE = config.get('SEARCH_MODE', SEARCH_MODE)
            UPDATE_TOPIC = config.get('UPDATE_TOPIC', UPDATE_TOPIC)
            MODEL = config.get('MODEL', MODEL)
            FANOUT_LIMIT = config.get('FANOUT_LIMIT', FANOUT_LIMIT)
            MAX_SUMMARY_LENGTH = config.get('MAX_SUMMARY_LENGTH', MAX_SUMMARY_LENGTH)
            DEBUG = config.get('DEBUG', DEBUG)
            DEBUG_TXT = config.get('DEBUG_TXT', DEBUG_TXT)
            NO_RECORD = config.get('NO_RECORD', NO_RECORD)
    except Exception as e:
        print(f"[WARNING] config.json 로드 중 오류: {e}")

def save_config():
    """현재 설정을 config.json에 저장"""
    config = {
        'SYSTEM_MODE': SYSTEM_MODE,
        'SEARCH_MODE': SEARCH_MODE,
        'UPDATE_TOPIC': UPDATE_TOPIC,
        'MODEL': MODEL,
        'FANOUT_LIMIT': FANOUT_LIMIT,
        'MAX_SUMMARY_LENGTH': MAX_SUMMARY_LENGTH,
        'DEBUG': DEBUG,
        'DEBUG_TXT': DEBUG_TXT,
        'NO_RECORD': NO_RECORD
    }
    
    try:
        with open('config.json', 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[ERROR] config.json 저장 중 오류: {e}")

def validate_node_structure(node_data):
    """노드 데이터 구조 유효성 검사"""
    required_fields = ['node_id', 'topic', 'summary', 'direct_parent_id', 'all_parent_ids', 'children_ids']
    
    if not isinstance(node_data, dict):
        return False
        
    for field in required_fields:
        if field not in node_data:
            return False
            
    # 타입 검사
    if not isinstance(node_data['all_parent_ids'], list):
        return False
    if not isinstance(node_data['children_ids'], list):
        return False
        
    # 기억 노드인 경우 all_memory_indexes 필드 확인
    if len(node_data['children_ids']) == 0:  # 리프 노드 (기억 노드)
        if 'all_memory_indexes' not in node_data:
            return False
        if not isinstance(node_data['all_memory_indexes'], list):
            return False
    
    return True

def get_root_children_ids():
    """ROOT 노드의 직접 자식 ID들 반환"""
    try:
        from memory import load_json
        hierarchical_data = load_json('memory/hierarchical_memory.json', {})
        
        root_children = []
        for node_id, node_data in hierarchical_data.items():
            if node_data.get('direct_parent_id') == 'ROOT':
                root_children.append(node_id)
        
        return root_children
    except Exception as e:
        debug_print(f"ROOT 자식 노드 조회 오류: {e}")
        return []

# 초기 설정 로드
load_config()

# 디버그 초기화
if DEBUG_TXT:
    debug_log_init()
