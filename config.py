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
SYSTEM_MODE = "chat"  # test, chat
FANOUT_LIMIT = 5
MAX_SEARCH_DEPTH = 10
MAX_SUMMARY_LENGTH = 1000
UPDATE_TOPIC = "smart"  # always, smart, never
SEARCH_MODE = "efficiency"  # efficiency, force, no
NO_RECORD = False
DEBUG = False
DEBUG_TXT = False

# 테스트 데이터
TEST_Q = [
    # 개인정보 관련
    "내 이름은 김민수고 나이는 28살이야",
    "나는 서울대학교 컴퓨터공학과를 졸업했어",
    "내 생일은 1995년 3월 15일이야",
    "내 취미는 기타 연주와 등산이야",
    "내가 가장 좋아하는 색깔은 파란색이야",
    "내 키는 175cm이고 몸무게는 68kg이야",
    "내 혈액형은 A형이야",
    "내가 사는 곳은 강남구 논현동이야",
    "내 직업은 소프트웨어 개발자야",
    "내가 다니는 회사는 네이버야",
    
    # 가족 관련
    "우리 가족은 4명이야 - 아버지, 어머니, 누나, 나",
    "아버지는 의사이시고 어머니는 교사셔",
    "누나는 2살 위고 회계사로 일해",
    "할머니는 부산에 살고 계셔",
    "고양이 한 마리를 키우는데 이름이 '몽이'야",
    "우리 집 강아지는 골든 리트리버이고 이름이 '해피'야",
    "삼촌은 캐나다에 살고 있어",
    "사촌 동생이 의과대학에 다니고 있어",
    "외할아버지는 작년에 90세가 되셨어",
    "큰아버지는 치킨집을 운영하셔",
    
    # 학교 생활
    "대학교 1학년 때 동아리는 밴드부였어",
    "졸업 논문 주제는 '인공지능을 활용한 음성 인식 시스템'이었어",
    "대학교 때 가장 어려웠던 과목은 알고리즘이었어",
    "학과에서 성적이 상위 10%였어",
    "교환학생으로 일본 도쿄대학에 1년 다녔어",
    "대학교 축제에서 밴드 공연을 한 적이 있어",
    "컴퓨터 프로그래밍 대회에서 3등을 한 적이 있어",
    "졸업할 때 학과 우수상을 받았어",
    "대학원은 안 가고 바로 취업했어",
    "고등학교는 대치고등학교를 나왔어",
    
    # 취미와 관심사
    "피아노를 10년 동안 배웠어",
    "마라톤을 완주한 적이 3번 있어",
    "등산으로 한라산을 5번 올라갔어",
    "요리 중에서는 파스타 만들기를 좋아해",
    "독서는 주로 SF 소설을 읽어",
    "영화는 액션 장르를 가장 좋아해",
    "여행은 일본을 7번 다녀왔어",
    "사진 찍기가 취미인데 DSLR 카메라를 써",
    "헬스장을 5년째 다니고 있어",
    "게임은 주로 FPS 장르를 해",
    
    # 직장 생활
    "입사한 지 3년이 되었어",
    "현재 백엔드 개발팀에서 일하고 있어",
    "주로 Python과 Java를 사용해서 개발해",
    "프로젝트 팀장을 맡고 있어",
    "작년에 사내 해커톤에서 1등을 했어",
    "월급은 세전 4500만원이야",
    "회사에서 집까지는 지하철로 40분 걸려",
    "점심은 주로 회사 구내식당에서 먹어",
    "동료들과 매주 금요일에 치킨을 먹어",
    "올해 승진해서 대리가 되었어",
    
    # 음식 선호도
    "가장 좋아하는 음식은 삼겹살이야",
    "매운 음식을 정말 좋아해",
    "초밥집은 '스시로'를 자주 가",
    "커피는 아메리카노만 마셔",
    "맥주는 하이트를 선호해",
    "디저트로는 초콜릿 케이크를 좋아해",
    "라면은 신라면이 제일 맛있어",
    "중국집은 '홍콩반점'을 자주 시켜 먹어",
    "아이스크림은 바닐라 맛을 좋아해",
    "과일 중에서는 사과를 가장 좋아해",
    
    # 건강 관련
    "키 175cm에 몸무게 68kg이야",
    "혈압이 조금 높은 편이야",
    "왼쪽 무릎에 오래된 부상이 있어",
    "알레르기는 새우에 있어",
    "시력이 나빠서 안경을 써",
    "수면 시간은 보통 6-7시간이야",
    "금연한 지 2년이 되었어",
    "건강검진에서 콜레스테롤이 약간 높게 나왔어",
    "치과에 6개월마다 정기검진 받으러 가",
    "비타민D 부족으로 영양제를 먹고 있어",
    
    # 여행 경험
    "작년에 태국 방콕에 5일 다녀왔어",
    "유럽 여행으로 프랑스, 이탈리아, 스페인을 갔었어",
    "제주도는 총 12번 가봤어",
    "부산 여행에서 해운대에서 1박 했어",
    "일본 오사카에서 우니동을 먹어봤어",
    "베트남 다낭에서 쌀국수가 정말 맛있었어",
    "몽골 여행에서 승마 체험을 했어",
    "중국 베이징에서 만리장성을 봤어",
    "하와이에서 서핑을 배웠어",
    "호주 시드니에서 오페라 하우스를 구경했어",
    
    # 좋아하는 것들
    "가수는 아이유를 가장 좋아해",
    "영화배우 중에서는 이병헌을 좋아해",
    "드라마는 '이상한 변호사 우영우'를 재밌게 봤어",
    "책은 '해리포터' 시리즈를 7번 읽었어",
    "만화는 '원피스'를 20년째 보고 있어",
    "브랜드는 나이키를 선호해",
    "자동차는 현대 아반떼를 타고 있어",
    "핸드폰은 삼성 갤럭시 S23을 써",
    "노트북은 맥북 프로를 사용해",
    "시계는 애플워치를 차고 있어",
    
    # 특별한 경험들
    "번지점프를 뉴질랜드에서 해봤어",
    "패러글라이딩을 양평에서 체험했어",
    "스쿠버다이빙 자격증을 따고 필리핀에서 다이빙했어",
    "마술을 2년 동안 배운 적이 있어",
    "연극 동아리에서 주연을 맡았던 적이 있어",
    "라디오 DJ 체험을 방송국에서 해봤어",
    "요트를 타고 한강에서 크루즈를 했어",
    "열기구를 터키에서 타봤어",
    "캠핑을 강원도 평창에서 50번 넘게 했어",
    "낚시로 30cm 배스를 잡은 적이 있어",
    
    # 목표와 계획
    "내년에 일본어 자격증 1급을 따려고 해",
    "5년 내에 집을 사는 게 목표야",
    "올해 안에 토익 900점을 넘기려고 해",
    "내년에 창업을 해보려고 준비 중이야",
    "10년 후에는 CTO가 되고 싶어",
    "내년 여름에 유럽 한 달 여행을 계획하고 있어",
    "올해 하반기에 대학원 진학을 고려하고 있어",
    "5년 내에 마라톤 풀코스 3시간 30분을 목표로 해",
    "내년에 요리학원에 다닐 예정이야",
    "3년 내에 캐나다 이민을 생각하고 있어",
    
    # 과거 추억
    "초등학교 때 반장을 3번 했어",
    "중학교 때 전교 1등을 한 적이 있어",
    "고등학교 때 첫 연애를 했어",
    "대학교 1학년 때 MT에서 길을 잃었던 적이 있어",
    "어릴 때 개구리를 잡으러 논에 가곤 했어",
    "초등학교 운동회에서 달리기 1등을 했어",
    "중학교 때 밴드부에서 드럼을 쳤어",
    "고등학교 때 수학 올림피아드에 나갔어",
    "어린 시절 할아버지와 바둑을 두곤 했어",
    "초등학교 때 합창단에서 활동했어",
    
    # 현재 상황
    "지금 원룸에 혼자 살고 있어",
    "매일 아침 7시에 일어나",
    "출근할 때는 지하철 2호선을 타",
    "점심시간은 12시부터 1시까지야",
    "퇴근 후에는 주로 헬스장에 가",
    "주말에는 보통 늦잠을 자",
    "현재 다이어트 중이라 식단 관리하고 있어",
    "요즘 영어 회화 학원을 다니고 있어",
    "주식 투자를 작년부터 시작했어",
    "비트코인을 조금 보유하고 있어",
    
    # 물건과 소유물
    "차는 2020년식 현대 아반떼를 타고 있어",
    "시계는 롤렉스 서브마리너를 차고 있어",
    "노트북은 맥북 프로 M2를 사용해",
    "핸드폰은 아이폰 14 프로를 써",
    "헤드폰은 소니 WH-1000XM4를 사용해",
    "신발은 나이키 에어맥스를 주로 신어",
    "가방은 루이비통 백팩을 사용해",
    "안경은 레이밴 웨이페어러를 써",
    "향수는 샤넬 블루 드 샤넬을 사용해",
    "지갑은 구찌 제품을 사용하고 있어",
    
    # 기술과 프로그래밍
    "Python을 7년째 사용하고 있어",
    "JavaScript 프레임워크로는 React를 선호해",
    "데이터베이스는 PostgreSQL을 주로 써",
    "클라우드는 AWS를 사용해봤어",
    "Git을 이용한 버전 관리를 하고 있어",
    "Docker로 컨테이너화 작업을 해봤어",
    "머신러닝은 TensorFlow를 사용해",
    "모바일 앱 개발로 Flutter를 배우고 있어",
    "블록체인 개발에 관심이 많아",
    "인공지능 관련 논문을 읽는 걸 좋아해",
    
    # 친구들과 인간관계
    "절친한 친구가 5명 있어",
    "대학교 동기들과 매월 만나",
    "직장 동료 중에 특히 친한 사람이 3명 있어",
    "고등학교 친구들과는 1년에 2번 정도 만나",
    "소개팅을 작년에 5번 했어",
    "현재 사귀고 있는 여자친구가 있어",
    "여자친구와는 6개월째 만나고 있어",
    "친구들과 매주 축구를 해",
    "동호회에서 20명 정도와 친해",
    "SNS 친구는 총 300명 정도 있어",
    
    # 돈과 경제 생활
    "용돈은 한 달에 30만원 정도 써",
    "저축은 매월 100만원 정도 해",
    "투자로는 주식에 500만원 넣었어",
    "부동산은 아직 없어",
    "대출은 학자금 대출 300만원이 남아있어",
    "신용카드는 3개를 사용하고 있어",
    "보험은 생명보험과 의료보험에 가입했어",
    "적금을 2개 통장에 넣고 있어",
    "펀드 투자도 조금 해보고 있어",
    "가계부를 앱으로 관리하고 있어",
    
    # 날씨와 계절 선호도
    "봄을 가장 좋아하는 계절이야",
    "비 오는 날을 좋아해",
    "눈 내리는 겨울 풍경을 좋아해",
    "더위를 많이 타는 편이야",
    "추위는 괜찮은 편이야",
    "태풍이나 폭우는 무서워해",
    "벚꽃 시기에 여의도에 가곤 해",
    "단풍 구경을 매년 가",
    "해수욕장은 여름에 꼭 가",
    "겨울 스키를 타러 강원도에 가",
    
    # 스포츠 관련
    "축구팀은 토트넘을 응원해",
    "야구는 두산 베어스 팬이야",
    "농구는 NBA 레이커스를 좋아해",
    "테니스를 2년째 배우고 있어",
    "수영을 어릴 때부터 했어",
    "골프를 작년부터 시작했어",
    "볼링 평균 점수가 150점이야",
    "탁구를 중학교 때 선수로 했어",
    "배드민턴을 주 2회 쳐",
    "스쿼시장을 한 달에 2번 가",
    
    # 교통수단과 이동
    "지하철을 주로 이용해",
    "버스는 가끔 타",
    "택시는 비올 때만 타",
    "자전거는 주말에 타",
    "오토바이 면허는 없어",
    "비행기는 일 년에 3-4번 타",
    "기차여행을 좋아해",
    "배는 멀미 때문에 잘 안 타",
    "지하철 2호선을 가장 많이 이용해",
    "카셰어링을 가끔 이용해",
    
    # 문화생활
    "영화관은 CGV를 주로 가",
    "연극을 한 달에 1번은 봐",
    "뮤지컬 중에서는 '오페라의 유령'을 좋아해",
    "콘서트는 일 년에 5번 정도 가",
    "박물관 관람을 좋아해",
    "미술관도 자주 가는 편이야",
    "도서관에서 책을 빌려 읽어",
    "서점에서 시간 보내는 걸 좋아해",
    "카페에서 공부하는 걸 선호해",
    "노래방을 월 2-3번 가",
    
    # 언어와 학습
    "영어는 토익 850점이야",
    "일본어를 3년째 배우고 있어",
    "중국어도 조금 할 줄 알아",
    "스페인어에 관심이 있어",
    "한국사 자격증이 있어",
    "컴활 1급을 가지고 있어",
    "정보처리기사 자격증이 있어",
    "토익스피킹 레벨6이야",
    "OPIC IH등급을 받았어",
    "온라인 강의를 자주 들어",
    
    # 성격과 특성
    "내향적인 성격이야",
    "완벽주의 성향이 있어",
    "계획을 세우는 걸 좋아해",
    "새로운 도전을 즐기는 편이야",
    "화를 잘 안 내는 성격이야",
    "꼼꼼한 편이야",
    "감성적인 면이 있어",
    "유머 감각이 있다고 생각해",
    "인내심이 강한 편이야",
    "호기심이 많아",
    
    # 일상 루틴
    "매일 아침 6시에 일어나",
    "기상 후 바로 물 한 잔을 마셔",
    "아침 운동을 30분 해",
    "아침식사는 토스트를 주로 먹어",
    "출근길에 팟캐스트를 들어",
    "점심 후에는 커피를 마셔",
    "오후 3시쯤 간식을 먹어",
    "퇴근 후에 헬스장에 가",
    "저녁은 집에서 해먹는 편이야",
    "잠들기 전에 책을 읽어",
    
    # 마지막 종합 질문들
    "나에 대해서 설명해줘",
    "내가 좋아하는 것들을 정리해줘",
    "내 가족 구성원을 말해줘",
    "내 취미와 관심사를 알려줘",
    "내가 다녔던 학교들을 말해줘",
    "내 직업과 회사에 대해 설명해줘",
    "내가 여행 간 나라들을 나열해줘",
    "내 건강 상태는 어때?",
    "내가 가진 자격증들을 말해줘",
    "내 미래 계획들을 정리해줘"
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
MAX_STORAGE_DEPTH = 8
SIMILARITY_THRESHOLD = 0.7
EXPLORATION_THRESHOLD = 0.5

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
    global SYSTEM_MODE, SEARCH_MODE, UPDATE_TOPIC, GEMINI_MODEL, FANOUT_LIMIT, MAX_SUMMARY_LENGTH
    global DEBUG, DEBUG_TXT, NO_RECORD
    
    try:
        if os.path.exists('config.json'):
            with open('config.json', 'r', encoding='utf-8') as f:
                config = json.load(f)
                
            SYSTEM_MODE = config.get('SYSTEM_MODE', SYSTEM_MODE)
            SEARCH_MODE = config.get('SEARCH_MODE', SEARCH_MODE)
            UPDATE_TOPIC = config.get('UPDATE_TOPIC', UPDATE_TOPIC)
            GEMINI_MODEL = config.get('MODEL', GEMINI_MODEL)
            FANOUT_LIMIT = config.get('FANOUT_LIMIT', FANOUT_LIMIT)
            MAX_SUMMARY_LENGTH = config.get('MAX_SUMMARY_LENGTH', MAX_SUMMARY_LENGTH)
            DEBUG = config.get('DEBUG', DEBUG)
            DEBUG_TXT = config.get('DEBUG_TXT', DEBUG_TXT)
            NO_RECORD = config.get('NO_RECORD', NO_RECORD)
            
            if DEBUG:
                print(f"config.json 로드 완료:")
                print(f"  - SYSTEM_MODE: {SYSTEM_MODE}")
                print(f"  - SEARCH_MODE: {SEARCH_MODE}")
                print(f"  - MODEL: {GEMINI_MODEL}")
                print(f"  - DEBUG: {DEBUG}")
        else:
            # config.json이 없으면 기본 설정으로 생성
            create_default_config()
            if DEBUG:
                print("config.json이 없어서 기본 설정으로 생성했습니다.")
                
    except Exception as e:
        print(f"[WARNING] config.json 로드 중 오류: {e}")
        print("기본 설정을 사용합니다.")

def save_config():
    """현재 설정을 config.json에 저장"""
    config = {
        'SYSTEM_MODE': SYSTEM_MODE,
        'SEARCH_MODE': SEARCH_MODE,
        'UPDATE_TOPIC': UPDATE_TOPIC,
        'MODEL': GEMINI_MODEL,
        'FANOUT_LIMIT': FANOUT_LIMIT,
        'MAX_SUMMARY_LENGTH': MAX_SUMMARY_LENGTH,
        'DEBUG': DEBUG,
        'DEBUG_TXT': DEBUG_TXT,
        'NO_RECORD': NO_RECORD
    }
    
    try:
        with open('config.json', 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        
        if DEBUG:
            print("config.json 저장 완료")
    except Exception as e:
        print(f"[ERROR] config.json 저장 중 오류: {e}")

def create_default_config():
    """기본 config.json 파일 생성"""
    default_config = {
        'SYSTEM_MODE': 'chat',
        'SEARCH_MODE': 'efficiency',
        'UPDATE_TOPIC': 'smart',
        'MODEL': 'gemini-2.5-flash',
        'FANOUT_LIMIT': 5,
        'MAX_SUMMARY_LENGTH': 1000,
        'DEBUG': False,
        'DEBUG_TXT': False,
        'NO_RECORD': False
    }
    
    try:
        with open('config.json', 'w', encoding='utf-8') as f:
            json.dump(default_config, f, indent=2, ensure_ascii=False)
        print("기본 config.json 파일을 생성했습니다.")
    except Exception as e:
        print(f"[ERROR] 기본 config.json 생성 중 오류: {e}")

def update_config(**kwargs):
    """config.json의 특정 설정값들 업데이트"""
    global SYSTEM_MODE, SEARCH_MODE, UPDATE_TOPIC, GEMINI_MODEL, FANOUT_LIMIT, MAX_SUMMARY_LENGTH
    global DEBUG, DEBUG_TXT, NO_RECORD
    
    # 전역 변수 업데이트
    if 'SYSTEM_MODE' in kwargs:
        SYSTEM_MODE = kwargs['SYSTEM_MODE']
    if 'SEARCH_MODE' in kwargs:
        SEARCH_MODE = kwargs['SEARCH_MODE']
    if 'UPDATE_TOPIC' in kwargs:
        UPDATE_TOPIC = kwargs['UPDATE_TOPIC']
    if 'MODEL' in kwargs:
        GEMINI_MODEL = kwargs['MODEL']
    if 'FANOUT_LIMIT' in kwargs:
        FANOUT_LIMIT = kwargs['FANOUT_LIMIT']
    if 'MAX_SUMMARY_LENGTH' in kwargs:
        MAX_SUMMARY_LENGTH = kwargs['MAX_SUMMARY_LENGTH']
    if 'DEBUG' in kwargs:
        old_debug = DEBUG
        DEBUG = kwargs['DEBUG']
        # DEBUG 상태 변경 시 로그 초기화
        if DEBUG != old_debug and DEBUG_TXT:
            debug_log_init()
    if 'DEBUG_TXT' in kwargs:
        old_debug_txt = DEBUG_TXT
        DEBUG_TXT = kwargs['DEBUG_TXT']
        # DEBUG_TXT 상태 변경 시 로그 처리
        if DEBUG_TXT != old_debug_txt:
            if DEBUG_TXT:
                debug_log_init()
            else:
                debug_log_close()
    if 'NO_RECORD' in kwargs:
        NO_RECORD = kwargs['NO_RECORD']
    
    # config.json 파일 업데이트
    save_config()
    
    if DEBUG:
        print(f"설정 업데이트 완료: {kwargs}")

def get_config():
    """현재 config.json 설정을 딕셔너리로 반환"""
    return {
        'SYSTEM_MODE': SYSTEM_MODE,
        'SEARCH_MODE': SEARCH_MODE,
        'UPDATE_TOPIC': UPDATE_TOPIC,
        'MODEL': GEMINI_MODEL,
        'FANOUT_LIMIT': FANOUT_LIMIT,
        'MAX_SUMMARY_LENGTH': MAX_SUMMARY_LENGTH,
        'DEBUG': DEBUG,
        'DEBUG_TXT': DEBUG_TXT,
        'NO_RECORD': NO_RECORD
    }

def validate_config_value(key, value):
    """config.json 설정값 유효성 검사"""
    valid_configs = {
        'SYSTEM_MODE': ['test', 'chat'],
        'SEARCH_MODE': ['efficiency', 'force', 'no'],
        'UPDATE_TOPIC': ['always', 'smart', 'never'],
        'MODEL': ['gemini-1.5-flash', 'gemini-2.5-flash', 'gemini-2.5-flash-lite'],
        'FANOUT_LIMIT': lambda x: isinstance(x, int) and 1 <= x <= 50,
        'MAX_SUMMARY_LENGTH': lambda x: isinstance(x, int) and 100 <= x <= 10000,
        'DEBUG': lambda x: isinstance(x, bool),
        'DEBUG_TXT': lambda x: isinstance(x, bool),
        'NO_RECORD': lambda x: isinstance(x, bool)
    }
    
    if key not in valid_configs:
        return False, f"알 수 없는 설정 키: {key}"
    
    validator = valid_configs[key]
    
    if callable(validator):
        if validator(value):
            return True, "유효함"
        else:
            return False, f"유효하지 않은 값: {value}"
    elif isinstance(validator, list):
        if value in validator:
            return True, "유효함"
        else:
            return False, f"유효하지 않은 값: {value}. 가능한 값: {validator}"
    
    return False, "검증 오류"

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
            if node_data.get('direct_parent_id') is None:
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
