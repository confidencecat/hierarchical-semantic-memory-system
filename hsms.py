import argparse
import sys
import os
from config import (
    debug_print, AI_API_N, LOAD_API_N, AI_API, LOAD_API,
    get_config, update_config, validate_config_value,
    load_config, create_default_config
)
from memory import initialize_json_files, load_json
from main_ai import chat_mode, test_mode

def show_api_info():
    """API 키 정보 표시"""
    print("\n=== API 키 정보 ===")
    print(f"AI_API: {AI_API_N}개")
    if AI_API_N > 0:
        for i, key in enumerate(AI_API[:3]):
            print(f"  AI_{i+1}: {key[:4]}****")
        if AI_API_N > 3:
            print(f"  ... 외 {AI_API_N-3}개")
    else:
        print("  사용 가능한 AI_API 없음")
    
    print(f"LOAD_API: {LOAD_API_N}개")
    if LOAD_API_N > 0:
        for i, key in enumerate(LOAD_API[:5]):
            print(f"  LOAD_{i+1}: {key[:4]}****")
        if LOAD_API_N > 5:
            print(f"  ... 외 {LOAD_API_N-5}개")
    else:
        print("  사용 가능한 LOAD_API 없음")

def show_tree_structure():
    """현재 트리 구조를 도식화하여 표시"""
    print("\n=== 트리 구조 ===")
    
    hierarchical_memory = load_json('memory/hierarchical_memory.json', {})
    if not hierarchical_memory:
        print("저장된 트리 구조가 없습니다.")
        return
    
    # ROOT 노드의 자식들을 찾기
    root_children = []
    for node_id, node_data in hierarchical_memory.items():
        if node_data.get('direct_parent_id') is None:
            root_children.append(node_id)
    
    if not root_children:
        print("ROOT 노드에 자식이 없습니다.")
        return
    
    print("ROOT")
    
    def print_node(node_id, depth=1, is_last=True, parent_prefix=""):
        node_data = hierarchical_memory.get(node_id)
        if not node_data:
            return
        
        if depth == 1:
            connector = "|-- "
            new_parent_prefix = parent_prefix + ("    " if is_last else "|   ")
        else:
            connector = "|-- " if not is_last else "`-- "
            new_parent_prefix = parent_prefix + ("    " if is_last else "|   ")
        
        current_prefix = parent_prefix + connector
        
        # 노드 정보
        topic = node_data.get('topic', 'Unknown')
        children = node_data.get('children_ids', [])
        memories = node_data.get('all_memory_indexes', [])
        
        if memories:  # 기억 노드
            print(f"{current_prefix}{topic} [{len(memories)}개 기억]")
        else:  # 부모 노드
            print(f"{current_prefix}{topic} [{len(children)}개 자식]")
        
        # 자식 노드들 출력
        for i, child_id in enumerate(children):
            is_last_child = (i == len(children) - 1)
            print_node(child_id, depth + 1, is_last_child, new_parent_prefix)
    
    # ROOT의 자식들 출력
    for i, child_id in enumerate(root_children):
        is_last_child = (i == len(root_children) - 1)
        print_node(child_id, 1, is_last_child, "")

def validate_environment():
    """환경 검증"""
    errors = []
    warnings = []
    
    if AI_API_N == 0 and LOAD_API_N == 0:
        errors.append("사용 가능한 API 키가 없습니다. .env 파일을 확인하세요.")
    elif AI_API_N == 0:
        warnings.append("AI_API 키가 없습니다. LOAD_API를 대신 사용합니다.")
    elif LOAD_API_N == 0:
        warnings.append("LOAD_API 키가 없습니다. AI_API를 대신 사용합니다.") 
    if not os.path.exists('.env'):
        warnings.append(".env 파일이 없습니다. 환경 변수에서 API 키를 찾습니다.")
    
    if errors:
        print("오류:")
        for error in errors:
            print(f"  - {error}")
        return False
    
    if warnings:
        print("경고:")
        for warning in warnings:
            print(f"  - {warning}")
    
    print("환경 검증 완료")
    return True

def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(
        description='계층적 의미 기억 시스템 (HSMS)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시:
  python hsms.py                              # 기본 대화 모드
  python hsms.py --mode test --debug          # 테스트 모드 (디버그 포함)
  python hsms.py --search force --no-record   # 강제 검색, 기록 안함
  python hsms.py --api-info                   # API 정보만 표시
  python hsms.py --tree                       # 트리 구조만 표시
  python hsms.py --debug-txt                  # 디버그 텍스트 파일 저장
        """
    )
    
    parser.add_argument(
        '--mode',
        choices=['test', 'chat'],
        help='실행 모드: test (테스트), chat (대화형 모드)'
    )
    parser.add_argument(
        '--search',
        choices=['efficiency', 'force', 'no'],
        help='검색 방법: efficiency (효율적), force (강제), no (없음)'
    )
    parser.add_argument(
        '--api-info',
        action='store_true',
        help='사용 가능한 API 키 정보 표시'
    )
    parser.add_argument(
        '--tree',
        action='store_true',
        help='현재 트리 구조를 도식화하여 표시'
    )
    parser.add_argument(
        '--debug',
        action='store_true',
        help='디버그 모드 활성화'
    )
    parser.add_argument(
        '--debug-txt',
        action='store_true',
        help='디버그 메시지를 텍스트 파일로 저장'
    )
    parser.add_argument(
        '--fanout-limit',
        type=int,
        metavar='N',
        help='한 노드가 가질 수 있는 최대 자식 수 (1-50)'
    )
    parser.add_argument(
        '--model',
        choices=['gemini-1.5-flash', 'gemini-2.5-flash', 'gemini-2.5-flash-lite'],
        help='사용할 AI 모델'
    )
    parser.add_argument(
        '--no-record',
        action='store_true',
        help='대화를 기억 시스템에 저장하지 않음 (단순 응답 모드)'
    )
    parser.add_argument(
        '--update-topic',
        choices=['always', 'smart', 'never'],
        help='토픽 업데이트 모드: always (항상), smart (조건부), never (안함)'
    )
    
    args = parser.parse_args()
    
    print(" HSMS (Hierarchical Semantic Memory System)")
    print("=" * 50)
    
    if not validate_environment():
        sys.exit(1)
    load_config()
    
    config_updates = {}
    
    if args.mode is not None:
        config_updates['SYSTEM_MODE'] = args.mode
    if args.search is not None:
        config_updates['SEARCH_MODE'] = args.search
    if args.debug:
        config_updates['DEBUG'] = True
    if args.debug_txt:
        config_updates['DEBUG_TXT'] = True
    if args.fanout_limit is not None:
        if 1 <= args.fanout_limit <= 50:
            config_updates['FANOUT_LIMIT'] = args.fanout_limit
        else:
            print(f"오류: fanout-limit은 1-50 사이의 값이어야 합니다. (입력값: {args.fanout_limit})")
            sys.exit(1)
    if args.model is not None:
        config_updates['MODEL'] = args.model
    if args.no_record:
        config_updates['NO_RECORD'] = True
    if args.update_topic is not None:
        config_updates['UPDATE_TOPIC'] = args.update_topic
    
    if config_updates:
        update_config(**config_updates)
        print(f"설정 업데이트됨: {list(config_updates.keys())}")
    
    current_config = get_config()
    
    if args.api_info:
        show_api_info()
        if not current_config['SYSTEM_MODE']:  # API 정보만 보고 종료하려는 경우
            return
    
    # 트리 구조 표시 (요청 시)  
    if args.tree:
        show_tree_structure()
        if not current_config['SYSTEM_MODE']:  # 트리 구조만 보고 종료하려는 경우
            return
    
    print("\n데이터 파일 초기화 중...")
    if not initialize_json_files():
        print("데이터 파일 초기화 실패")
        sys.exit(1)
    print("데이터 파일 초기화 완료")
    
    # 현재 설정 정보 출력
    print(f"\n현재 시스템 설정:")
    print(f"  실행 모드: {current_config['SYSTEM_MODE']}")
    print(f"  검색 모드: {current_config['SEARCH_MODE']}")
    print(f"  디버그 모드: {'ON' if current_config['DEBUG'] else 'OFF'}")
    print(f"  디버그 파일 저장: {'ON' if current_config['DEBUG_TXT'] else 'OFF'}")
    print(f"  기록 모드: {'OFF' if current_config['NO_RECORD'] else 'ON'}")
    print(f"  Fanout 제한: {current_config['FANOUT_LIMIT']}")
    print(f"  AI 모델: {current_config['MODEL']}")
    print(f"  토픽 업데이트: {current_config['UPDATE_TOPIC']}")
    print(f"  요약 최대 길이: {current_config['MAX_SUMMARY_LENGTH']}")
    
    print("\n시스템 시작...")
    
    try:
        if current_config['SYSTEM_MODE'] == 'test':
            test_mode()
        elif current_config['SYSTEM_MODE'] == 'chat':
            chat_mode()
        else:
            print(f"알 수 없는 실행 모드: {current_config['SYSTEM_MODE']}")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n\n사용자에 의해 중단되었습니다.")
    except Exception as e:
        print(f"\n시스템 오류: {e}")
        if current_config['DEBUG']:
            import traceback
            traceback.print_exc()
        sys.exit(1)
    
    print("\nHSMS를 종료합니다.")

if __name__ == "__main__":
    main()
