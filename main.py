import asyncio
import argparse
import time
# 새로운 모듈 구조에서 클래스 임포트
from HSMS import MainAI, MemoryManager
from config import API_KEY, LOAD_API_KEYS


def parse_arguments():
    """명령줄 인수를 파싱합니다."""
    parser = argparse.ArgumentParser(description='계층적 의미 기억 시스템')
    parser.add_argument(
        '--mode', 
        choices=['test', 'chat', 'discord'], 
        default='chat',
        help='실행 모드: test (기존 질문들로 테스트), chat (대화형 모드), discord (Discord 봇 모드)'
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
        '--debug',
        action='store_true',
        help='디버그 모드 활성화 (AI 분류 과정, 메모리 상태 등 상세 정보 출력)'
    )
    return parser.parse_args()


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
        
        # 좌표 정보
        coord_info = ""
        if node.coordinates["start"] >= 0:
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


async def run_test_mode(force_search=False, debug=False):
    """테스트 모드로 실행합니다."""
    print("=== 계층적 의미 기억 시스템 시작 (테스트 모드) ===")
    if force_search:
        print("|| 강제 검색 모드: 모든 대화에서 기억 탐색을 수행합니다.")
    if debug:
        print(">> 디버그 모드: 상세 정보를 출력합니다.")
    
    main_ai_instance = MainAI(force_search=force_search, debug=debug)
    
    # 테스트 질문들 - 더 다양한 시나리오 추가
    test_questions = [
        # 개인 정보 시리즈
        "내 이름은 서재민이다.",
        "내가 다니는 고등학교는 대건고등학교이다.",
        "내가 좋아하는 과목은 수학이다.",
        "내 취미는 독서이다.",
        "가장 친한 친구는 김철수이다.",
        
        # 과일 카테고리 시리즈
        "사과에 대해서 궁금하다",
        "사과의 씨에는 독이 있는가?",
        "나는 사과에 대해서 부정적으로 생각한다.",
        "포도에 대해서 궁금하다.",
        "포도의 씨에는 독이 있는가?",
        "나는 포도에 대해서 부정적으로 생각한다. 왜냐하면 포도는 한 송이이지만 알맹이 모두 맛이 다르기 때문이다.",
        "딸기는 어떤 맛인가요?",
        "바나나의 영양가는?",
        "오렌지 비타민C 함량이 궁금해",
        
        # 동물 카테고리 시리즈
        "고양이는 어떤 성격의 동물인가요?",
        "강아지 훈련 방법이 궁금해요",
        "토끼는 어떤 먹이를 먹나요?",
        "새의 종류에는 뭐가 있나요?",
        
        # 음식 카테고리 시리즈
        "김치찌개 레시피 알려줘",
        "라면 맛있게 끓이는 법",
        "파스타 만드는 방법",
        
        # 학습 카테고리 시리즈
        "영어 공부 방법이 궁금해",
        "과학 실험 재미있는 것들",
        "역사 공부하는 팁",
        
        # 카테고리 분류 및 분리 실험.
        "나는 사과를 좋아하는데, 사과가 가장 맛있는것 같아. 하지만 동물들은 사과를 별로 좋아하지 않는다.",
        "나는 영어의 난해한 부분을 좋아한다. 그리고 과학에서는 발견하지 못한 부분을 좋아한다.",
        "영어의 문법이 어려운 이유가 무엇인가? 아랍어가 어려운 이유가 무엇인가? 화학이 어려운 이유가 무엇인가?",
        "나는 대구에 거주한다. 너는 어디에 살고 있지? 어떻게하면 너에 대해서 더 알 수 있는가?",
        "나는 19살이다. 화학을 공부하지 않아서 어려움이 있다.",
        "SSD와 HDD에 대해서 궁금하다. 이에 대해서 설명해줘. 다음으로 인공지능의 윤리에 대해서 설명해줘.",
        "인공지능과 관련된 지식을 공부하기 위해서는 어떻게 해야하는가? 수학을 더 효율적으로 공부하기 위해서는 어떻게 해야하는가?",

        # 기억 검색 테스트 시리즈 (비동기 병렬 검색 테스트)
        "저번에 내 이름이 뭐라고 했지?",
        "저번에 나에 대한 소개를 했는데, 나에 대한 정보를 모두 말해봐.",
        "저번에 말한 내가 사과를 싫어하는 이유는?",
        "저번에 내가 포도를 싫어하는 이유를 말했다. 그 내용이 무엇인가?",
        "내가 좋아하는 과목이 뭐였지?",
        "내 친구 이름이 뭐였나?",
        "과일 중에서 내가 부정적으로 생각하는 것들은?",
        "내가 언급한 동물들 모두 말해봐",
        "지금까지 내가 물어본 음식 관련 질문들은?",
        "저번에 내 나이를 말해줬다. 내 나이는 몇살이지?",
        "저번에 말한 내가 공부하고 싶어했던 과목 혹은 분야에 대해서 모두 요약해서 설명해줘."
        
    ]

    for i, question in enumerate(test_questions):
        print(f"\n--- 질문 {i+1} ---")
        print(f"Q: {question}")
        
        start_time = time.time()
        response = await main_ai_instance.chat_async(question)
        end_time = time.time()
        
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


async def run_chat_mode(force_search=False, debug=False):
    """대화형 모드로 실행합니다."""
    print("=== 계층적 의미 기억 시스템 시작 (대화형 모드) ===")
    if force_search:
        print("|| 강제 검색 모드: 모든 대화에서 기억 탐색을 수행합니다.")
    else:
        print("|| 효율 모드: 필요한 경우에만 기억 탐색을 수행합니다.")
    if debug:
        print(">> 디버그 모드: 상세 정보를 출력합니다.")
    
    main_ai_instance = MainAI(force_search=force_search, debug=debug)
    
    print("\n=== 대화형 모드 (종료하려면 'exit' 입력) ===")
    while True:
        user_input = input("\n사용자: ")
        if user_input.lower() in ['exit', 'quit', '종료', '그만']:
            print("AI: 대화를 종료합니다.")
            break
        
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


def main_ai(prompt='False'):
    """메인 AI 인스턴스를 생성하고 대화를 처리합니다."""
    main_ai_instance = MainAI()
    return main_ai_instance.chat(prompt)


if __name__ == '__main__':
    args = parse_arguments()
    
    if args.api_info:
        show_api_info()
    
    if args.tree:
        show_tree_structure()
    
    # tree나 api_info만 요청한 경우 종료
    if args.tree or args.api_info:
        if not (args.mode in ['test', 'chat', 'discord']):
            exit(0)
    
    if args.mode == 'test':
        asyncio.run(run_test_mode(force_search=args.force_search, debug=args.debug))
    elif args.mode == 'chat':
        asyncio.run(run_chat_mode(force_search=args.force_search, debug=args.debug))
    elif args.mode == 'discord':
        run_discord_mode(debug=args.debug)
