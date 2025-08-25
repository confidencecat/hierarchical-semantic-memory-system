import asyncio
import argparse
import time
# 새로운 모듈 구조에서 클래스 임포트
from HSMS import MainAI, MemoryManager, TreeCleanupEngine
from config import API_KEY, LOAD_API_KEYS, TEST_QUESTIONS, RECORD_TEST_QUESTIONS


def parse_arguments():
    """명령줄 인수를 파싱합니다."""
    parser = argparse.ArgumentParser(description='계층적 의미 기억 시스템')
    parser.add_argument(
        '--mode', 
        choices=['test', 'chat', 'discord', 'search'], 
        default='chat',
        help='실행 모드: test (기존 질문들로 테스트), chat (대화형 모드), discord (Discord 봇 모드), search (검색 전용)'
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
        '--force-search',
        action='store_true',
        help='모든 대화에서 기억 호출 강제 (효율성 무시)'
    )
    parser.add_argument(
        '--force-record',
        action='store_true',
        help='AI 응답 없이 정보만 기록 (기록 전용 모드)'
    )
    parser.add_argument(
        '--debug',
        action='store_true',
        help='디버그 모드 활성화 (AI 분류 과정, 메모리 상태 등 상세 정보 출력)'
    )
    # 동적 트리 및 트리 정리 기능 관련 인수
    parser.add_argument(
        '--max-depth',
        type=int,
        default=4,
        help='트리의 최대 깊이를 설정합니다 (최소 3).'
    )
    parser.add_argument(
        '--clean-tree',
        action='store_true',
        help='트리 구조를 정리하고 최적화합니다.'
    )
    parser.add_argument(
        '--fanout-limit',
        type=int,
        default=12,
        help='한 노드가 가질 수 있는 최대 자식 수 (트리 정리 시 사용).'
    )
    parser.add_argument(
        '--rename',
        action='store_true',
        help='트리 정리 시 노드 이름을 자동으로 재명명합니다.'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='트리 정리 시 실제 변경 없이 계획만 출력합니다.'
    )
    parser.add_argument(
        '--top-search-n',
        type=int,
        default=0,
        help='검색 결과에서 반환할 최대 대화 수 (0이면 모든 관련 대화 반환, 기본값: 0)'
    )
    parser.add_argument(
        '--question',
        type=str,
        help='(테스트용) chat 모드에서 단일 질문을 처리하고 종료합니다.'
    )
    parser.add_argument(
        '--no-record',
        action='store_true',
        help='대화를 기억 시스템에 저장하지 않습니다 (단순 응답 모드).'
    )
    parser.add_argument(
        '--no-search',
        action='store_true',
        help='응답은 생성하지만, 기억을 검색하지는 않습니다.'
    )
    
    args = parser.parse_args()
    
    # max-depth 유효성 검사
    if args.max_depth < 3:
        parser.error("--max-depth는 3 이상이어야 합니다.")
        
    return args


def show_api_info():
    """API 키 정보를 표시합니다."""
    print("=== API 키 정보 ===")
    print(f"메인 API 키들: {len([k for k in API_KEY.values() if k])}")
    print(f"LOAD API 키들: {len(LOAD_API_KEYS)}")
    if LOAD_API_KEYS:
        print(f"- 비동기 병렬 검색 가능 (최대 {len(LOAD_API_KEYS)}개 동시 처리)")
    else:
        print("- 비동기 병렬 검색 제한됨 (LOAD API 키 없음)")
    print("=" * 20)


def show_tree_structure():
    """현재 트리 구조를 도식화하여 표시합니다."""
    memory_manager = MemoryManager()
    
    if not memory_manager.memory_tree:
        print("트리가 비어있습니다.")
        return
    
    print("=== 계층적 기억 트리 구조 ===")
    print(f"총 노드 수: {len(memory_manager.memory_tree)}")
    print()
    
    def build_tree_visualization(node_id, depth=0, is_last=True, prefix=""):
        if node_id not in memory_manager.memory_tree:
            return ""
        
        node = memory_manager.memory_tree[node_id]
        
        # 트리 구조 문자
        connector = "└── " if is_last else "├── "
        
        # 노드 타입별 표시
        if node.topic == "ROOT":
            emoji = "ROOT"
        elif node.coordinates["start"] == -1:  # 카테고리 노드
            emoji = "[CAT]"
        else:  # 대화 노드
            emoji = "[TALK]"
        
        # 좌표 정보 - 새로운 conversation_indices 방식 사용
        coord_info = ""
        if hasattr(node, 'conversation_indices') and node.conversation_indices:
            # 새로운 방식: conversation_indices 표시
            if len(node.conversation_indices) == 1:
                coord_info = f" (대화: {node.conversation_indices[0]})"
            elif len(node.conversation_indices) <= 3:
                coord_info = f" (대화: {', '.join(map(str, node.conversation_indices))})"
            else:
                # 많은 대화가 있는 경우 축약 표시
                first_few = node.conversation_indices[:2]
                coord_info = f" (대화: {', '.join(map(str, first_few))}...+{len(node.conversation_indices)-2}개)"
        elif node.coordinates["start"] >= 0:
            # 기존 방식 (하위 호환성)
            if node.coordinates["start"] == node.coordinates["end"]:
                coord_info = f" (대화: {node.coordinates['start']})"
            else:
                coord_info = f" (대화: {node.coordinates['start']}~{node.coordinates['end']})"
        elif node.topic != "ROOT":
            coord_info = " (카테고리)"
        
        # 현재 노드 출력
        result = f"{prefix}{connector}{emoji} {node.topic}{coord_info}\n"
        
        # 요약 정보 (카테고리가 아닌 경우)
        if node.coordinates["start"] != -1 and node.summary and depth < 2:
            summary_prefix = prefix + ("    " if is_last else "│   ")
            summary_text = node.summary[:50] + "..." if len(node.summary) > 50 else node.summary
            result += f"{summary_prefix}[TALK] {summary_text}\n"
        
        # 자식 노드들 처리
        children_ids = node.children_ids
        for i, child_id in enumerate(children_ids):
            if child_id in memory_manager.memory_tree:
                new_prefix = prefix + ("    " if is_last else "│   ")
                is_last_child = (i == len(children_ids) - 1)
                result += build_tree_visualization(child_id, depth + 1, is_last_child, new_prefix)
        
        return result
    
    # 루트부터 시작하여 전체 트리 구성
    tree_visual = build_tree_visualization(memory_manager.root_node_id)
    print(tree_visual)
    
    # 통계 정보
    print("=" * 50)
    print("|| 트리 통계:")
    
    # 카테고리별 노드 수 계산
    categories = {}
    conversation_nodes = 0
    
    for node in memory_manager.memory_tree.values():
        if node.coordinates["start"] == -1:  # 카테고리 노드
            categories[node.topic] = len(node.children_ids)
        elif node.coordinates["start"] >= 0:  # 대화 노드
            conversation_nodes += 1
    
    print(f"- 총 노드 수: {len(memory_manager.memory_tree)}")
    print(f"- 대화 기록 노드: {conversation_nodes}")
    print(f"- 카테고리 노드: {len(categories)}")
    
    if categories:
        print("\n|| 카테고리별 하위 노드:")
        for category, count in categories.items():
            if category != "ROOT":
                print(f"  - {category}: {count}개")
    
    print("=" * 50)


async def run_test_mode(force_search=False, force_record=False, debug=False, max_depth=4, top_search_n=0):
    """테스트 모드로 실행합니다."""
    print("=== 계층적 의미 기억 시스템 시작 (테스트 모드) ===")
    if force_search:
        print("|| 강제 검색 모드: 모든 대화에서 기억 탐색을 수행합니다.")
    elif force_record:
        print("|| 기록 전용 모드: AI 응답 없이 정보만 저장합니다.")
    else:
        print("|| 효율 모드: 필요한 경우에만 기억 탐색을 수행합니다.")
    if debug:
        print(">> 디버그 모드: 상세 정보를 출력합니다.")
    
    main_ai_instance = MainAI(force_search=force_search, force_record=force_record, debug=debug, max_depth=max_depth, top_search_n=top_search_n)
    
    # 테스트 질문들 - 더 다양한 시나리오 추가
    test_questions = TEST_QUESTIONS

    for i, question in enumerate(test_questions):
        print(f"\n--- 질문 {i+1} ---")
        print(f"Q: {question}")
        
        start_time = time.time()
        response = await main_ai_instance.chat_async(question)
        end_time = time.time()
        
        if force_record:
            print("A: [기록 완료]")
        else:
            print(f"A: {response}")
        print(f"처리 시간: {end_time - start_time:.2f}초")
        
        # 트리 상태 출력 (간단한 정보만)
        if i < 15:  # 처음 15개 질문에 대해서만 노드 수 표시
            status = main_ai_instance.get_tree_status()
            print(f"트리 노드 수: {status['total_nodes']}")
        
        # 일부 질문에서는 더 자세한 트리 구조 표시
        if i == 4 or i == 11 or i == 18:  # 개인정보, 과일, 동물 카테고리 완성 시점
            print("\n현재 트리 구조:")
            status = main_ai_instance.get_tree_status()
            print(status['tree_summary'])
    
    print("\n=== 최종 트리 구조 ===")
    final_status = main_ai_instance.get_tree_status()
    print(f"총 노드 수: {final_status['total_nodes']}")
    print(f"트리 구조:\n{final_status['tree_summary']}")


async def run_chat_mode(force_search=False, force_record=False, debug=False, max_depth=4, top_search_n=0, question=None, no_record=False, no_search=False):
    """대화형 모드로 실행하며, 실시간 명령어를 지원합니다."""
    
    # 초기 설정값 출력
    print("=== 계층적 의미 기억 시스템 시작 (대화형 모드) ===")
    if no_record:
        print("|| 저장 비활성화 모드: 대화가 기억 시스템에 저장되지 않습니다.")
    elif no_search:
        print("|| 검색 비활성화 모드: 기억을 검색하지 않고 응답합니다.")
    elif force_record:
        print("|| 기록 전용 모드: AI 응답 없이 정보만 저장합니다.")
    elif force_search:
        print("|| 강제 검색 모드: 모든 대화에서 기억 탐색을 수행합니다.")
    else:
        print("|| 효율 모드: 필요한 경우에만 기억 탐색을 수행합니다.")
    
    if debug:
        print(">> 디버그 모드: 상세 정보를 출력합니다.")

    # AI 인스턴스 생성
    main_ai_instance = MainAI(
        force_search=force_search, 
        force_record=force_record, 
        debug=debug, 
        max_depth=max_depth, 
        top_search_n=top_search_n, 
        no_record=no_record,
        no_search=no_search
    )

    # --question 인수가 있으면 해당 질문만 처리하고 종료
    if question:
        print(f"\n사용자: {question}")
        start_time = time.time()
        response = await main_ai_instance.chat_async(question)
        end_time = time.time()
        print(f"AI: {response}")
        print(f"(처리 시간: {end_time - start_time:.2f}초)")
        return

    print("\n=== 대화형 모드 (도움말: !help, 종료: exit) ===")
    while True:
        user_input = input("\n사용자: ").strip()
        
        if user_input.lower() in ['exit', 'quit', '종료', '그만']:
            print("AI: 대화를 종료합니다.")
            break

        # 명령어 처리 로직
        if user_input.startswith('!'):
            parts = user_input.split()
            command = parts[0].lower()

            if command == '!help':
                print("""
--- 명령어 도움말 ---
!status         : 현재 모든 설정 상태를 표시합니다.
!force-search   : 모든 대화에서 기억을 강제로 검색하는 모드를 켜고 끕니다.
!force-record   : AI 응답 없이 대화를 기록만 하는 모드를 켜고 끕니다.
!no-record      : 대화를 아예 저장하지 않는 모드를 켜고 끕니다.
!debug          : 상세한 처리 과정을 보여주는 디버그 모드를 켜고 끕니다.
!tree           : 현재 기억 트리 구조를 출력합니다.
!api-info       : 설정된 API 키 정보를 보여줍니다.
!max-depth [숫자] : 기억 트리의 최대 깊이를 설정합니다. (예: !max-depth 5)
!help           : 이 도움말을 표시합니다.
exit            : 프로그램을 종료합니다.
--------------------""")
                continue

            elif command == '!status':
                print(f"""
--- 현재 설정 상태 ---
- !force-search : {'ON' if main_ai_instance.force_search else 'OFF'}
- !force-record : {'ON' if main_ai_instance.force_record else 'OFF'}
- !no-record    : {'ON' if main_ai_instance.no_record else 'OFF'}
- !debug        : {'ON' if main_ai_instance.debug else 'OFF'}
- !max-depth    : {main_ai_instance.max_depth}
--------------------""")
                continue

            elif command == '!tree':
                show_tree_structure()
                continue

            elif command == '!api-info':
                show_api_info()
                continue

            elif command == '!debug':
                main_ai_instance.set_debug_mode(not main_ai_instance.debug)
                continue

            elif command == '!force-search':
                main_ai_instance.force_search = not main_ai_instance.force_search
                print(f">> [CONFIG] 강제 검색 모드가 {'ON' if main_ai_instance.force_search else 'OFF'}으로 설정되었습니다.")
                continue

            elif command == '!force-record':
                new_state = not main_ai_instance.force_record
                if new_state and main_ai_instance.no_record:
                    print(">> [ERROR] !no-record가 ON 상태에서는 !force-record를 켤 수 없습니다.")
                else:
                    main_ai_instance.force_record = new_state
                    print(f">> [CONFIG] 기록 전용 모드가 {'ON' if main_ai_instance.force_record else 'OFF'}으로 설정되었습니다.")
                continue

            elif command == '!no-record':
                new_state = not main_ai_instance.no_record
                if new_state and main_ai_instance.force_record:
                    print(">> [ERROR] !force-record가 ON 상태에서는 !no-record를 켤 수 없습니다.")
                else:
                    main_ai_instance.no_record = new_state
                    print(f">> [CONFIG] 저장 비활성화 모드가 {'ON' if main_ai_instance.no_record else 'OFF'}으로 설정되었습니다.")
                continue
            
            elif command == '!max-depth':
                if len(parts) > 1 and parts[1].isdigit():
                    new_depth = int(parts[1])
                    if new_depth >= 3:
                        main_ai_instance.set_max_depth(new_depth)
                    else:
                        print(">> [ERROR] max-depth는 3 이상이어야 합니다.")
                else:
                    print(">> [ERROR] 사용법: !max-depth [숫자]")
                continue

            else:
                print(f">> [ERROR] 알 수 없는 명령어입니다: {command}")
                continue

        # 일반 대화 처리
        start_time = time.time()
        response = await main_ai_instance.chat_async(user_input)
        end_time = time.time()
        
        print(f"AI: {response}")
        print(f"(처리 시간: {end_time - start_time:.2f}초)")


def run_discord_mode(debug=False):
    """Discord 봇 모드로 실행합니다."""
    print("=== Discord 봇 모드 시작 ===")
    if debug:
        print(">> 디버그 모드: 상세 정보를 출력합니다.")
    try:
        import hsms_discord
        hsms_discord.set_debug_mode(debug)  # 디버그 모드 설정
        hsms_discord.run_bot()
    except ImportError as e:
        print(f"|| 오류: Import 오류: {e}")
        print("Discord 봇을 실행하려면 hsms_discord.py 파일이 필요합니다.")
        print("또한 discord.py 라이브러리가 설치되어 있는지 확인하세요: pip install discord.py")
    except Exception as e:
        print(f"|| 오류: Discord 봇 실행 중 오류 발생: {e}")


async def run_search_mode(debug=False, max_depth=4, top_search_n=0):
    """검색 전용 모드로 실행합니다 (모든 대화에서 기억 검색)."""
    print("=== 계층적 의미 기억 시스템 시작 (검색 전용 모드) ===")
    print("|| 검색 모드: 모든 대화에서 기억 탐색을 수행합니다.")
    if debug:
        print(">> 디버그 모드: 상세 정보를 출력합니다.")
    
    main_ai_instance = MainAI(force_search=True, debug=debug, max_depth=max_depth, top_search_n=top_search_n)
    
    print("\n=== 검색 모드 (종료하려면 'exit' 입력) ===")
    
    while True:
        try:
            user_input = input("\n검색 질문: ").strip()
            
            if user_input.lower() in ['exit', '종료', 'quit']:
                print("검색 모드를 종료합니다.")
                break
            
            if not user_input:
                continue
            
            print(f"\n>> [SEARCH] 검색 시작: '{user_input[:40]}{'...' if len(user_input) > 40 else ''}'")
            
            start_time = time.time()
            response = await main_ai_instance.chat_async(user_input)
            end_time = time.time()
            
            print(f"\n검색 결과: {response}")
            print(f"검색 시간: {end_time - start_time:.2f}초")
            
        except KeyboardInterrupt:
            print("\n\n검색 모드를 종료합니다.")
            break
        except Exception as e:
            print(f"|| 오류: 검색 중 오류 발생: {e}")


def main_ai(prompt='False', max_depth=4, top_search_n=0):
    """메인 AI 인스턴스를 생성하고 대화를 처리합니다."""
    main_ai_instance = MainAI(max_depth=max_depth, top_search_n=top_search_n)
    return main_ai_instance.chat(prompt)


if __name__ == '__main__':
    args = parse_arguments()
    
    # --force-record와 --no-record 동시 사용 방지
    if args.force_record and args.no_record:
        print("오류: --force-record와 --no-record는 동시에 사용할 수 없습니다.")
        exit(1)

    # --force-search와 --no-search 동시 사용 방지
    if args.force_search and args.no_search:
        print("오류: --force-search와 --no-search는 동시에 사용할 수 없습니다.")
        exit(1)

    # force_search와 force_record는 동시에 사용할 수 없음
    if getattr(args, 'force_search', False) and getattr(args, 'force_record', False):
        print("오류: --force-search와 --force-record는 동시에 사용할 수 없습니다.")
        exit(1)
    
    if args.api_info:
        show_api_info()
    
    if args.tree:
        show_tree_structure()
    
    # clean-tree 기능 처리
    if args.clean_tree:
        print(f">> [CLEAN] 트리 정리 시작 (max-depth: {args.max_depth}, fanout-limit: {args.fanout_limit})")
        if args.dry_run:
            print(">> [CLEAN] 드라이런 모드: 실제 변경 없이 계획만 출력")
        if args.rename:
            print(">> [CLEAN] 노드 재명명 활성화")
        
        # 트리 정리 엔진 실행
        memory_manager = MemoryManager()
        cleanup_engine = TreeCleanupEngine(
            memory_manager=memory_manager,
            max_depth=args.max_depth,
            fanout_limit=args.fanout_limit,
            debug=True  # 정리 과정에서는 항상 디버그 출력
        )
        
        asyncio.run(cleanup_engine.run_cleanup(rename_nodes=args.rename, dry_run=args.dry_run))
        exit(0)
    
    # tree나 api_info만 요청한 경우 종료
    if args.tree or args.api_info:
        if not (args.mode in ['test', 'chat', 'discord', 'search']):
            exit(0)
    
    force_search = getattr(args, 'force_search', False)
    force_record = getattr(args, 'force_record', False)
    no_record = getattr(args, 'no_record', False)
    no_search = getattr(args, 'no_search', False)
    
    if args.mode == 'test':
        asyncio.run(run_test_mode(force_search=force_search, force_record=force_record, debug=args.debug, max_depth=args.max_depth, top_search_n=args.top_search_n))
    elif args.mode == 'chat':
        asyncio.run(run_chat_mode(force_search=force_search, force_record=force_record, debug=args.debug, max_depth=args.max_depth, top_search_n=args.top_search_n, question=args.question, no_record=no_record, no_search=no_search))
    elif args.mode == 'discord':
        run_discord_mode(debug=args.debug)
    elif args.mode == 'search':
        asyncio.run(run_search_mode(debug=args.debug, max_depth=args.max_depth, top_search_n=args.top_search_n))
