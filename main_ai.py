import asyncio
from config import (
    SEARCH_MODE, NO_RECORD, DEBUG, FANOUT_LIMIT, MAX_SUMMARY_LENGTH, 
    UPDATE_TOPIC, GEMINI_MODEL, TEST_Q, debug_print, DEBUG_TXT, debug_log_separator, debug_log_close
)
from ai_func import need_memory_judgement_AI, respond_AI
from tree import search_tree, save_tree
from memory import initialize_json_files

current_search_mode = SEARCH_MODE
current_no_record = NO_RECORD
current_debug = DEBUG
current_debug_txt = DEBUG_TXT
current_fanout_limit = FANOUT_LIMIT
current_max_summary_length = MAX_SUMMARY_LENGTH
current_update_topic = UPDATE_TOPIC
current_model = GEMINI_MODEL

# 실시간 명령어 처리
def command(command_input):
    """실시간 명령어 처리 함수"""
    global current_search_mode, current_no_record, current_debug, current_debug_txt
    global current_fanout_limit, current_max_summary_length, current_update_topic, current_model
    
    parts = command_input.strip().split()
    cmd = parts[0].lower()
    
    if cmd == '!help':
        print("""
=== HSMS 명령어 도움말 ===
!help                    - 이 도움말 표시
!api-info               - API 키 정보 표시
!status                 - 현재 시스템 상태 표시
!search [MODE]          - 검색 모드 변경 (efficiency/force/no)
!debug                  - 디버그 모드 토글
!debug-text             - 디버그 텍스트 파일 저장 모드 토글
!fanout-limit [NUMBER]  - fanout 제한값 변경 (1-50)
!model [MODEL_NAME]     - AI 모델 변경
!record [MODE]          - 기록 모드 변경 (ON/OFF)
!update-topic [MODE]    - 토픽 업데이트 정책 변경 (always/smart/never)
!max-summary [NUMBER]   - 요약 최대 길이 설정 (100-1000)
!tree                   - 트리 구조 표시
""")
    
    elif cmd == '!api-info':
        from config import AI_API_N, LOAD_API_N, AI_API, LOAD_API
        print(f"\n=== API 키 정보 ===")
        print(f"AI_API: {AI_API_N}개")
        for i, key in enumerate(AI_API[:3]):
            print(f"  AI_{i+1}: {key[:4]}****")
        print(f"LOAD_API: {LOAD_API_N}개")
        for i, key in enumerate(LOAD_API[:5]):
            print(f"  LOAD_{i+1}: {key[:4]}****")
        if LOAD_API_N > 5:
            print(f"  ... 외 {LOAD_API_N-5}개")
    
    elif cmd == '!status':
        print(f"\n=== 시스템 상태 ===")
        print(f"검색 모드: {current_search_mode}")
        print(f"기록 모드: {'ON' if not current_no_record else 'OFF'}")
        print(f"디버그 모드: {'ON' if current_debug else 'OFF'}")
        print(f"디버그 텍스트 저장: {'ON' if current_debug_txt else 'OFF'}")
        print(f"Fanout 제한: {current_fanout_limit}")
        print(f"최대 요약 길이: {current_max_summary_length}")
        print(f"토픽 업데이트: {current_update_topic}")
        print(f"AI 모델: {current_model}")
    
    elif cmd == '!search':
        if len(parts) > 1:
            import config
            mode = parts[1].lower()
            if mode in ['efficiency', 'force', 'no']:
                current_search_mode = mode
                config.SEARCH_MODE = mode
                print(f"검색 모드가 '{mode}'로 변경되었습니다.")
            else:
                print("잘못된 검색 모드입니다. (efficiency/force/no)")
        else:
            print(f"현재 검색 모드: {current_search_mode}")
    
    elif cmd == '!debug':
        import config
        current_debug = not current_debug
        config.DEBUG = current_debug
        print(f"디버그 모드: {'ON' if current_debug else 'OFF'}")
    
    elif cmd == '!debug-text':
        import config
        current_debug_txt = not current_debug_txt
        config.DEBUG_TXT = current_debug_txt
        if current_debug_txt:
            config.debug_log_init()
        else:
            config.debug_log_close()
        print(f"디버그 텍스트 저장: {'ON' if current_debug_txt else 'OFF'}")
    
    elif cmd == '!fanout-limit':
        if len(parts) > 1:
            try:
                import config
                limit = int(parts[1])
                if 1 <= limit <= 50:
                    current_fanout_limit = limit
                    config.FANOUT_LIMIT = limit
                    print(f"Fanout 제한이 {limit}로 변경되었습니다.")
                else:
                    print("Fanout 제한은 1-50 범위여야 합니다.")
            except ValueError:
                print("올바른 숫자를 입력하세요.")
        else:
            print(f"현재 Fanout 제한: {current_fanout_limit}")
    
    elif cmd == '!model':
        if len(parts) > 1:
            model = parts[1]
            current_model = model
            print(f"AI 모델이 '{model}'로 변경되었습니다.")
        else:
            print(f"현재 AI 모델: {current_model}")
    
    elif cmd == '!record':
        if len(parts) > 1:
            mode = parts[1].upper()
            if mode in ['ON', 'OFF']:
                current_no_record = (mode == 'OFF')  # record ON이면 no_record는 False
                print(f"기록 모드: {mode}")
            else:
                print("잘못된 기록 모드입니다. (ON/OFF)")
        else:
            current_mode = 'ON' if not current_no_record else 'OFF'
            print(f"현재 기록 모드: {current_mode}")
    
    elif cmd == '!update-topic':
        if len(parts) > 1:
            mode = parts[1].lower()
            if mode in ['always', 'smart', 'never']:
                current_update_topic = mode
                print(f"토픽 업데이트 정책이 '{mode}'로 변경되었습니다.")
            else:
                print("잘못된 토픽 업데이트 모드입니다. (always/smart/never)")
        else:
            print(f"현재 토픽 업데이트 정책: {current_update_topic}")
    
    elif cmd == '!max-summary':
        if len(parts) > 1:
            try:
                length = int(parts[1])
                if 100 <= length <= 1000:
                    current_max_summary_length = length
                    print(f"최대 요약 길이가 {length}로 변경되었습니다.")
                else:
                    print("최대 요약 길이는 100-1000 범위여야 합니다.")
            except ValueError:
                print("올바른 숫자를 입력하세요.")
        else:
            print(f"현재 최대 요약 길이: {current_max_summary_length}")
    
    elif cmd == '!tree':
        from hsms import show_tree_structure
        show_tree_structure()
    
    else:
        print(f"알 수 없는 명령어: {cmd}")
        print("!help로 사용 가능한 명령어를 확인하세요.")

# 핵심 대화 처리 로직
async def main(user_question):
    """핵심 대화 처리 함수"""
    global current_search_mode, current_no_record, current_debug
    
    if current_debug:
        debug_print(f"대화 처리 시작: {user_question[:50]}...")
    
    elif current_debug_txt:
        debug_print(f"대화 처리 시작: {user_question[:50]}...")
    
    # 기억 필요성 판단
    need_memory = False
    if current_search_mode == 'efficiency':
        need_memory = need_memory_judgement_AI(user_question)
    elif current_search_mode == 'force':
        need_memory = True
    # current_search_mode == 'no'인 경우 need_memory는 False 유지
    
    # 기억 검색 (필요한 경우)
    memory_results = []
    if need_memory:
        if current_debug:
            debug_print("기억 검색 시작...")
        elif current_debug_txt:
            debug_print("기억 검색 시작...")
            
        memory_results = await search_tree(user_question)  # ALL_MEMORY 인덱스 리스트 반환
        
        if current_debug:
            debug_print(f"기억 검색 완료: {len(memory_results)}개 기억 발견")
        elif current_debug_txt:
            debug_print(f"기억 검색 완료: {len(memory_results)}개 기억 발견")
    
    # 응답 생성
    if current_debug:
        debug_print("응답 생성 시작...")
    elif current_debug_txt:
        debug_print("응답 생성 시작...")
        
    response = respond_AI(user_question, memory_results)
    
    if current_debug:
        debug_print("응답 생성 완료")
    elif current_debug_txt:
        debug_print("응답 생성 완료")
    
    # 기억 저장 (NO_RECORD가 False인 경우)
    if not current_no_record:
        conversation_pair = [
            {"role": "user", "content": user_question},
            {"role": "assistant", "content": response}
        ]
        if current_debug:
            debug_print("기억 저장 시작...")
        elif current_debug_txt:
            debug_print("기억 저장 시작...")
            
        await save_tree(conversation_pair)
        
        if current_debug:
            debug_print("기억 저장 완료")
        elif current_debug_txt:
            debug_print("기억 저장 완료")
    
    # 질의응답 완료 후 구분선 추가
    if current_debug_txt:
        debug_log_separator()
    
    return response

def main_sync(user_question):
    """main 함수의 동기 버전"""
    return asyncio.run(main(user_question))

def chat_mode():
    """터미널 기반 대화형 모드"""
    print("=== HSMS 대화 모드 시작 ===")
    print("'!help'로 명령어 확인, 'exit'로 종료")
    
    initialize_json_files()
    
    while True:
        try:
            user_input = input("\n사용자: ").strip()
            
            if user_input.lower() == 'exit':
                print("시스템을 종료합니다.")
                break
                
            if user_input.startswith('!'):
                command(user_input)
                continue
            
            if not user_input:
                continue
                
            response = main_sync(user_input)
            print(f"AI: {response}")
            
        except KeyboardInterrupt:
            print("\n\n시스템을 종료합니다.")
            break
        except Exception as e:
            print(f"오류 발생: {e}")
            if current_debug:
                import traceback
                traceback.print_exc()
    
    if current_debug_txt:
        debug_log_close()

# 자동화 테스트 모드
def test_mode():
    """자동화된 테스트 모드"""
    print("=== HSMS 테스트 모드 시작 ===")
    
    initialize_json_files()
    
    for i, test_question in enumerate(TEST_Q, 1):
        print(f"\n[테스트 {i}/{len(TEST_Q)}]")
        print(f"질문: {test_question}")
        
        try:
            response = main_sync(test_question)
            print(f"응답: {response}")
        except Exception as e:
            print(f"오류: {e}")
            if current_debug:
                import traceback
                traceback.print_exc()
        
        if current_debug and i < len(TEST_Q):
            input("다음 테스트로 진행하려면 Enter를 누르세요...")
    
    print("\n=== 테스트 완료 ===")

def process_single_question(question, search_mode="efficiency", no_record=False, debug=False):
    """단일 질문을 처리하는 외부 API용 함수"""
    global current_search_mode, current_no_record, current_debug
    
    old_search_mode = current_search_mode
    old_no_record = current_no_record
    old_debug = current_debug
    
    current_search_mode = search_mode
    current_no_record = no_record
    current_debug = debug
    
    try:
        response = main_sync(question)
        return response
    finally:
        current_search_mode = old_search_mode
        current_no_record = old_no_record
        current_debug = old_debug
