# 계층적 의미 기억 시스템 (Hierarchical Semantic Memory System)

## 📋 목차
1. [프로젝트 개요](#1-프로젝트-개요)
2. [시스템 아키텍처](#2-시스템-아키텍처)
3. [설치 및 설정](#3-설치-및-설정)
4. [사용법](#4-사용법)
5. [핵심 클래스 및 함수](#5-핵심-클래스-및-함수)
6. [AI 분류 시스템](#6-ai-분류-시스템)
7. [파일 구조](#7-파일-구조)
8. [고급 기능](#8-고급-기능)

## 1. 프로젝트 개요

### 1.1 핵심 개념
본 프로젝트는 **AI 기반 계층적 의미 기억 시스템**으로, 대화 내용을 의미적으로 분류하여 트리 구조로 관리하는 차세대 대화 AI입니다.

### 1.2 주요 특징
- 🌳 **계층적 트리 구조**: 카테고리 → 하위 주제 → 대화 노드
- 🤖 **AI 기반 분류**: Google Gemini를 활용한 지능적 주제 분류
- ⚡ **비동기 병렬 처리**: 다중 API 키로 고속 검색 및 분류
- 🎯 **다중 주제 처리**: 한 대화에서 여러 주제 자동 분리
- 💬 **Discord 봇 지원**: 실시간 서버별 기억 관리
- 🐛 **디버그 모드**: AI 분류 과정 실시간 관찰
- 🔧 **모듈화 설계**: 유지보수 및 확장 용이

### 1.3 문제 해결
**기존 문제점**: 단순 키워드 기반 분류로 인한 오분류
- ❌ "SSD 설명" → "배(과일)" 노드 
- ❌ "인류 역사" → "개(동물)" 노드

**해결 방안**: AI 기반 의미적 분류 시스템
- ✅ 컨텍스트 이해를 통한 정확한 분류
- ✅ 다중 주제 대화 자동 분리
- ✅ Few-shot prompting으로 분류 정확도 향상

## 2. 시스템 아키텍처

### 2.1 전체 구조도
```
┌─────────────────────────────────────────────────────────────┐
│                        User Interface                       │
├─────────────────┬─────────────────┬─────────────────────────┤
│   CLI Mode      │   Chat Mode     │    Discord Bot Mode     │
│  (main.py)      │   (main.py)     │   (hsms_discord.py)     │
└─────────────────┴─────────────────┴─────────────────────────┘
                            │
                    ┌───────▼────────┐
                    │   MainAI       │
                    │(HSMS/MainAI.py)│
                    └───────┬────────┘
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
┌───────▼────────┐ ┌────────▼────────┐ ┌────────▼────────┐
│  AuxiliaryAI   │ │  MemoryManager  │ │   AIManager     │
│(HSMS/Auxiliary │ │(HSMS/MemoryMgr) │ │(HSMS/AIManager) │
│  AI.py)        │ │     .py)        │ │     .py)        │
└────────────────┘ └─────────────────┘ └─────────────────┘
        │                   │                   │
        │                   │                   │
┌───────▼────────┐ ┌────────▼────────┐ ┌────────▼────────┐
│   LoadAI       │ │   MemoryNode    │ │  Google Gemini  │
│(HSMS/LoadAI.py)│ │(HSMS/MemoryNode │ │    (AI API)     │
│                │ │     .py)        │ │                 │
└────────────────┘ └─────────────────┘ └─────────────────┘
```

### 2.2 모듈 구조 (NEW!)
```
📁 HSMS/ (패키지)
├── __init__.py              # 패키지 초기화 및 클래스 익스포트
├── DataManager.py           # 데이터 관리 및 파일 입출력
├── MemoryNode.py            # 개별 기억 노드 클래스
├── MemoryManager.py         # 계층적 기억 트리 관리
├── AIManager.py             # AI 호출 및 비동기 처리 관리
├── AuxiliaryAI.py           # 보조 AI (핵심 분류 및 기억 처리)
├── LoadAI.py                # 로드 AI (레거시 호환용)
└── MainAI.py                # 메인 AI (사용자 대화 처리)

📄 hierarchical.py           # 하위 호환성을 위한 임포트 래퍼
📄 main.py                   # CLI 메인 실행 파일
📄 hsms_discord.py           # Discord 봇 인터페이스
```

### 2.3 데이터 플로우
```
사용자 입력
    │
    ▼
MainAI.chat_async()
    │
    ├─── 기억 검색 필요성 판단
    │    │
    │    ▼
    │    LoadAI.search_parallel() ──→ 관련 기억 검색
    │
    ▼
AI 응답 생성
    │
    ▼
AuxiliaryAI.handle_conversation()
    │
    ├─── 기존 카테고리 관련성 검사
    │    │
    │    ▼
    │    AI 기반 카테고리 분류
    │    │
    │    ├─── 단일 카테고리 → 기존/새 노드 판단
    │    └─── 다중 카테고리 → 대화 내용 분리
    │
    ▼
MemoryManager.add_node() ──→ JSON 파일 저장
```

### 2.3 메모리 트리 구조
```
ROOT
├── 소개 (Category)
│   ├── 이름 (Topic Node)
│   ├── 학교 (Topic Node)
│   └── 취미 (Topic Node)
├── 과일 (Category)
│   ├── 사과 (Topic Node)
│   │   ├── 사과 맛 (Sub-topic)
│   │   └── 사과 독성 (Sub-topic)
│   └── 포도 (Topic Node)
├── 동물 (Category)
│   ├── 고양이 (Topic Node)
│   └── 강아지 (Topic Node)
└── 과학 (Category)
    ├── 물리학 (Topic Node)
    └── 화학 (Topic Node)
```

## 3. 설치 및 설정

### 3.1 시스템 요구사항
- Python 3.10+
- Google Gemini API Key
- Discord Bot Token (Discord 기능 사용 시)
- 인터넷 연결

### 3.2 의존성 설치
```bash
# 레포지토리 클론
git clone https://github.com/confidencecat/hierarchical-semantic-memory-system.git
cd hierarchical-semantic-memory-system

# 패키지 설치
pip install -r requirements.txt
```

### 3.3 환경 변수 설정
`.env` 파일을 생성하고 다음 내용을 추가:

```env
# 필수: Google Gemini API 키
API_1=your_primary_gemini_api_key
API_2=your_backup_gemini_api_key

# 선택: 검색 성능 향상용 추가 API 키
LOAD_1=your_load_api_key_1
LOAD_2=your_load_api_key_2
LOAD_3=your_load_api_key_3

# Discord 봇 사용 시 필수
DISCORD_TOKEN=your_discord_bot_token
```

### 3.4 API 키 발급 방법
1. **Google Gemini API**:
   - [Google AI Studio](https://makersuite.google.com/app/apikey) 접속
   - API 키 생성 및 복사
   
2. **Discord Bot Token**:
   - [Discord Developer Portal](https://discord.com/developers/applications) 접속
   - New Application 생성 → Bot 메뉴 → Token 복사

## 4. 사용법

### 4.1 기본 명령어
```bash
# 테스트 모드 (33개 예제 질문으로 테스트)
python main.py --mode test

# 대화형 모드
python main.py --mode chat

# Discord 봇 모드
python main.py --mode discord

# 디버그 모드 (AI 분류 과정 실시간 출력)
python main.py --mode chat --debug

# 강제 검색 모드 (모든 대화에서 기억 탐색)
python main.py --mode chat --force-search

# 트리 구조만 출력
python main.py --tree

# API 정보 확인
python main.py --api-info
```

### 4.2 Discord 봇 명령어
```
!help        - 도움말 표시
!tree        - 현재 기억 트리 구조 표시  
!status      - 봇 상태 정보
!clear       - 서버의 기억 초기화 (관리자만)
!force [on/off] - 강제 검색 모드 토글 (관리자만)
!debug [on/off] - 디버그 모드 토글 (관리자만)
```

### 4.3 사용 예시
```bash
# 디버그 모드로 대화 시작
python main.py --mode chat --debug

사용자: 나는 사과를 좋아한다. 그런데 강아지도 사과를 먹을 수 있나?
🐛 [DEBUG] === AI 분류 시작 ===
🐛 [DEBUG] 관련 카테고리: ['과일', '동물']
🐛 [DEBUG] 대화 분리 결과:
🐛 [DEBUG] 과일: "나는 사과를 좋아한다"
🐛 [DEBUG] 동물: "강아지도 사과를 먹을 수 있나?"
```

## 5. 핵심 클래스 및 함수

### 5.1 MainAI 클래스
**파일**: `hierarchical.py`  
**역할**: 사용자와의 주요 인터페이스, 대화 흐름 제어

#### 주요 메서드:
```python
class MainAI:
    def __init__(self, force_search=False, debug=False):
        """메인 AI 초기화
        Args:
            force_search: 모든 대화에서 강제 검색 수행 여부
            debug: 디버그 모드 활성화 여부
        """
    
    async def chat_async(self, user_input: str) -> str:
        """비동기 대화 처리
        1. 기억 검색 필요성 판단
        2. 관련 기억 검색 (필요시)
        3. AI 응답 생성
        4. 대화 내용 분류 및 저장
        """
    
    def _needs_memory_search(self, user_input: str) -> bool:
        """기억 검색 필요성 판단 (키워드 기반 빠른 판단)"""
    
    async def _search_memory_async(self, user_input: str) -> str:
        """병렬 기억 검색 수행"""
```

### 5.2 AuxiliaryAI 클래스  
**파일**: `hierarchical.py`  
**역할**: AI 기반 대화 분류 및 메모리 트리 관리

#### 주요 메서드:
```python
class AuxiliaryAI:
    async def handle_conversation(self, conversation: list):
        """대화 분류 및 저장 메인 함수
        1. 기존 카테고리와의 관련성 검사
        2. 다중 카테고리 대화 분리
        3. 적절한 노드에 저장
        """
    
    async def _check_category_relevance_async(self, user_input: str, categories: dict) -> dict:
        """AI를 사용한 카테고리 관련성 판단
        Returns:
            dict: {카테고리명: True/False}
        """
    
    async def _separate_conversation_by_categories(self, user_input: str, ai_response: str, categories: list) -> dict:
        """다중 주제 대화를 카테고리별로 분리
        Returns:
            dict: {카테고리명: {'user': 분리된_사용자_발언, 'ai': 분리된_AI_응답}}
        """
    
    async def _create_new_category_and_node(self, conversation: list, conversation_index: int):
        """새 카테고리 및 하위 노드 생성"""
```

### 5.3 MemoryManager 클래스
**파일**: `hierarchical.py`  
**역할**: 메모리 트리 구조 관리 및 JSON 파일 저장

#### 주요 메서드:
```python
class MemoryManager:
    def __init__(self):
        """메모리 관리자 초기화 및 기존 데이터 로드"""
    
    def add_node(self, node: MemoryNode, parent_id: str = None):
        """트리에 새 노드 추가"""
    
    def get_node(self, node_id: str) -> MemoryNode:
        """노드 ID로 노드 검색"""
    
    def save_to_all_memory(self, conversation: list) -> int:
        """전체 대화 기록에 저장 후 인덱스 반환"""
    
    def save_to_file(self):
        """메모리 트리를 JSON 파일로 저장"""
    
    def print_tree(self, node_id: str = "root", depth: int = 0):
        """트리 구조 콘솔 출력"""
```

### 5.4 MemoryNode 클래스
**파일**: `hierarchical.py`  
**역할**: 개별 메모리 노드 데이터 구조

LOAD_3=your_load_api_key_3
# ... 최대 LOAD_20까지

# Discord 봇 토큰 (Discord 모드 사용 시 필수)
DISCORD_TOKEN=your_discord_bot_token_here
```

## 4. 사용법

### 4.1 기본 실행

```bash
# 대화형 모드 (기본)
python main.py

# 테스트 모드
python main.py --mode test

# Discord 봇 모드
python main.py --mode discord

# 모든 대화에서 기억 호출 강제
python main.py --force-search

# 트리 구조 시각화
python main.py --tree

# API 키 정보 확인
python main.py --api-info
```

### 4.2 사용 가능한 옵션

| 옵션 | 설명 |
|------|------|
| `--mode {test,chat,discord}` | 실행 모드 선택 |
| `--force-search` | 모든 대화에서 기억 탐색 강제 |
| `--tree` | 현재 트리 구조 시각화 출력 |
| `--api-info` | 사용 가능한 API 키 정보 표시 |

### 4.3 Discord 봇 사용법

Discord 봇을 사용하려면:

1. Discord Developer Portal에서 봇을 생성하고 토큰을 획득
2. `.env` 파일에 `DISCORD_TOKEN` 추가
3. `python main.py --mode discord` 실행

**Discord 봇 명령어:**
- `!help` - 도움말 표시
- `!tree` - 현재 기억 트리 구조 표시
- `!status` - 봇 상태 정보
- `!clear` - 서버의 기억 초기화 (관리자만)
- `!force [on/off]` - 강제 검색 모드 토글 (관리자만)

**사용법:**
- 봇을 멘션(`@봇이름`)하고 질문
- DM으로 직접 대화 가능

## 5. 시스템 아키텍처

### 5.1 모듈별 역할

#### main.py
- 명령줄 인터페이스 제공
- 테스트/채팅/Discord 모드 관리
- 설정 옵션 처리

#### hierarchical.py
- **DataManager**: 파일 입출력 및 JSON 관리
- **MemoryNode**: 개별 기억 노드 클래스
- **MemoryManager**: 계층적 트리 구조 관리
- **AIManager**: AI 호출 및 비동기 처리
- **AuxiliaryAI**: 기억 분류 및 저장 로직
- **MainAI**: 사용자 대화 처리

#### discord.py
- Discord 봇 구현
- 서버별 독립적인 기억 관리
- 관리자 명령어 지원

#### config.py
- API 키 및 환경 변수 관리
- Fine-tuning 데이터 정의
- 파일 경로 설정

### 5.2 트리 구조 예시

```
🌳 ROOT
├── 📁 과일 (카테고리)
│   ├── 🍎 사과 (대화: 5~7)
│   ├── 🍇 포도 (대화: 8~10)
│   └── 🍓 딸기 (대화: 11~11)
├── 📁 동물 (카테고리)
│   ├── 🐱 고양이 (대화: 14~16)
│   └── 🐶 개 (대화: 17~19)
└── 👤 개인정보 (대화: 0~4)
    ├── 📝 이름 (대화: 0~0)
    └── 🏫 학교 (대화: 1~1)
```

## 6. 주요 기능

### 6.1 효율성 옵션

**기본 모드 (효율성 우선):**
- 키워드 기반 빠른 판단으로 기억 검색 최소화
- 단순한 질문에는 탐색 생략

**강제 검색 모드 (`--force-search`):**
- 모든 대화에서 기억 탐색 수행
- 완전한 맥락 인식을 원하는 경우 사용

### 6.2 비동기 병렬 검색

- 다중 LOAD API 키를 활용한 병렬 처리
- 라운드 로빈 방식으로 부하 분산
- 검색 속도 대폭 향상

### 6.3 카테고리 자동 분류

지원되는 카테고리:
- **과일**: 사과, 포도, 딸기, 바나나 등
- **동물**: 개, 고양이, 토끼, 새 등
- **음식**: 요리, 레시피, 음식점 등
- **과목**: 수학, 영어, 과학, 사회 등

## 7. API 키 설정

### 7.1 Gemini API 키 획득

1. [Google AI Studio](https://makersuite.google.com/app/apikey) 방문
2. API 키 생성
3. `.env` 파일에 `API_1` 추가

### 7.2 Discord 봇 토큰 획득

1. [Discord Developer Portal](https://discord.com/developers/applications) 방문
2. 새 애플리케이션 생성
3. Bot 섹션에서 토큰 복사
4. `.env` 파일에 `DISCORD_TOKEN` 추가

## 8. 성능 최적화

### 8.1 LOAD API 키 활용

병렬 검색 성능 향상을 위해 여러 개의 Gemini API 키를 `LOAD_1`, `LOAD_2`, ... `LOAD_20`으로 설정할 수 있습니다.

### 8.2 메모리 효율성

- 카테고리 노드 보호로 의미 구조 보존
- 좌표 기반 인덱싱으로 효율적인 검색
- 지연 로딩으로 필요한 데이터만 로드

## 9. 문제 해결

### 9.1 일반적인 오류

**"API 키가 설정되지 않았습니다"**
- `.env` 파일의 `API_1` 확인
- 파일 경로가 올바른지 확인

**"Discord 토큰이 올바르지 않습니다"**
- `.env` 파일의 `DISCORD_TOKEN` 확인
- 토큰이 유효한지 Discord Developer Portal에서 확인

**"모듈을 찾을 수 없습니다"**
- `pip install -r requirements.txt` 실행
- Python 버전 확인 (3.8 이상 권장)

### 9.2 성능 이슈

**검색이 느린 경우:**
- LOAD API 키를 추가하여 병렬 처리 활성화
- `--force-search` 옵션 비활성화

**메모리 사용량이 큰 경우:**
- 주기적으로 트리 정리
- 오래된 대화 기록 아카이빙

## 10. 개발 및 확장

### 10.1 새로운 카테고리 추가

`hierarchical.py`의 `find_or_create_category_node` 함수에서 키워드를 추가할 수 있습니다:

```python
# 새로운 카테고리 추가 예시
hobby_keywords = ['게임', '영화', '독서', '운동', ...]
if any(keyword in user_input for keyword in hobby_keywords):
    return self.get_or_create_category_node('취미', '취미 활동에 대한 대화')
```

### 10.2 새로운 인터페이스 추가

모듈화된 구조 덕분에 새로운 인터페이스(웹, Telegram 등)를 쉽게 추가할 수 있습니다:

```python
# 새로운 인터페이스 예시
# 새로운 모듈 구조 사용 (권장)
from HSMS import MainAI

# 또는 하위 호환성을 위한 기존 방식
from hierarchical import MainAI

def web_interface():
    ai = MainAI(force_search=False)
    # 웹 인터페이스 구현
```

## 11. 라이선스

이 프로젝트는 오픈소스이며, 자유롭게 수정하고 배포할 수 있습니다.

## 12. 기여

버그 리포트, 기능 제안, 풀 리퀘스트를 환영합니다!

---

**개발팀**: 계층적 의미 기억 시스템  
**버전**: 2.0  
**최종 업데이트**: 2025년 8월

## 2. 시스템 아키텍처

계층적 의미 기억 시스템은 **트리 기반 메모리 구조**와 **AI 기반 의미 분석**을 결합한 아키텍처로 구성됩니다.

```
┌─────────────────────────────────────────────────────────────────┐
│                     사용자 인터페이스                              │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ │
│  │  --mode     │ │   --tree    │ │ --api-info  │ │    exit     │ │
│  │ test/chat   │ │  트리 시각화  │ │  API 정보   │ │   종료      │ │
│  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘ │
└─────────────────────────────────┬───────────────────────────────┘
                                  │
┌─────────────────────────────────┴───────────────────────────────┐
│                          MainAI                                │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              chat_async()                               │   │
│  │  1. 사용자 입력 분석                                      │   │
│  │  2. 기억 필요 여부 판단                                   │   │
│  │  3. 비동기 병렬 검색 실행                                │   │
│  │  4. 맥락 기반 응답 생성                                   │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────┬───────────────────────────────┘
                                  │
┌─────────────────────────────────┴───────────────────────────────┐
│                       AuxiliaryAI                              │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │            handle_conversation()                       │   │
│  │  1. 카테고리 노드 탐지/생성                               │   │
│  │  2. 새로운 주제 여부 판단                                │   │
│  │  3. 트리 노드 생성/업데이트                              │   │
│  │  4. 부모 노드 요약 갱신                                  │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────┬───────────────────────────────┘
                                  │
┌─────────────────────────────────┴───────────────────────────────┐
│                      MemoryManager                             │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              트리 구조 관리                              │   │
│  │  • initialize_tree(): 트리 초기화                       │   │
│  │  • add_node(): 노드 추가                               │   │
│  │  • update_node(): 노드 갱신                           │   │
│  │  • save_tree(): 트리 저장                              │   │
│  │  • get_tree_summary(): 트리 요약                      │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────┬───────────────────────────────┘
                                  │
┌─────────────────────────────────┴───────────────────────────────┐
│                       AIManager                                │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              AI 호출 관리                               │   │
│  │  • call_ai(): 단일 동기 호출                            │   │
│  │  • call_ai_async_single(): 단일 비동기 호출             │   │
│  │  • call_ai_async_multiple(): 병렬 비동기 호출           │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────┬───────────────────────────────┘
                                  │
┌─────────────────────────────────┴───────────────────────────────┐
│                    데이터 저장소                                │
│  ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐   │
│  │ hierarchical_   │ │ all_memory.json │ │   config.py     │   │
│  │ memory.json     │ │ (전체 대화 기록) │ │ (API 키/설정)   │   │
│  │ (트리 구조)     │ │                 │ │                 │   │
│  └─────────────────┘ └─────────────────┘ └─────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

## 3. 계층적 트리 구조

### 3.1 트리 구조 개념

시스템은 **ROOT 노드**를 중심으로 한 트리 구조를 사용하여 대화 내용을 체계적으로 분류합니다:

```
🌳 ROOT
├── 📁 과일 (카테고리)
│   ├── 🍎 사과 (대화: 5~5)
│   ├── 🍇 포도 (대화: 8~8)
│   ├── 🍓 딸기 (대화: 11~11)
│   └── 🍌 바나나 (대화: 12~12)
├── 📁 동물 (카테고리)
│   ├── 🐱 고양이 (대화: 14~14)
│   ├── 🐶 개 (대화: 15~15)
│   ├── 🐰 토끼 (대화: 16~16)
│   └── 🐦 새 (대화: 17~17)
├── 📁 과목 (카테고리)
│   ├── 📊 수학 (대화: 2~28)
│   └── 🌍 영어 (대화: 21~21)
└── 👤 자기소개 (대화: 0~24)
    └── 📝 이름확인 (대화: 33~33)
```

### 3.2 노드 유형

1. **ROOT 노드**: 최상위 노드, 모든 카테고리의 부모
2. **카테고리 노드**: 관련 주제들을 묶는 중간 노드 (`coordinates: -1, -1`)
3. **대화 노드**: 실제 대화 내용을 저장하는 리프 노드 (`coordinates: start~end`)

## 4. 핵심 클래스 및 함수 상세 설명

### 4.1 MemoryNode 클래스

계층적 트리의 개별 노드를 나타내는 핵심 데이터 구조입니다.

```python
class MemoryNode:
    def __init__(self, node_id=None, topic=None, summary=None, 
                 parent_id=None, children_ids=None, coordinates=None, references=None)
```

**주요 속성:**
- `node_id`: 고유 식별자 (UUID)
- `topic`: 노드 주제명
- `summary`: 대화 내용 요약
- `parent_id`: 부모 노드 ID
- `children_ids`: 자식 노드 ID 리스트
- `coordinates`: 대화 인덱스 범위 `{"start": n, "end": m}`
- `references`: 다른 노드 참조 리스트

**주요 메서드:**
1. `to_dict()`: 노드를 딕셔너리로 변환하여 JSON 저장 준비
2. `from_dict(data)`: 딕셔너리에서 노드 객체 복원

### 4.2 MemoryManager 클래스

계층적 기억 트리의 전체 구조를 관리하는 핵심 관리자 클래스입니다.

```python
class MemoryManager:
    def __init__(self)
```

**주요 속성:**
- `memory_tree`: 노드 ID를 키로 하는 노드 딕셔너리
- `root_node_id`: 루트 노드의 ID
- `data_manager`: 파일 입출력 관리자

**주요 메서드:**

1. `initialize_tree()`: 트리 구조 초기화 또는 기존 트리 로드
   - 기존 `hierarchical_memory.json` 파일이 있으면 로드
   - 없으면 새로운 ROOT 노드 생성

2. `add_node(node, parent_id)`: 새 노드를 트리에 추가
   - 부모-자식 관계 설정
   - 트리 저장 자동 실행

3. `update_node(node_id, **kwargs)`: 노드 정보 업데이트
   - 노드 속성 동적 수정
   - 변경사항 즉시 저장

4. `get_tree_summary(max_depth=3)`: 트리 구조의 텍스트 요약 생성
   - 지정된 깊이까지 재귀적 탐색
   - 계층적 들여쓰기로 구조 표현

5. `save_tree()`: 트리를 JSON 파일에 저장
   - `hierarchical_memory.json`에 전체 트리 구조 저장

### 4.3 AuxiliaryAI 클래스

계층적 기억 관리 시스템의 핵심 컨트롤러입니다.

```python
class AuxiliaryAI:
    def __init__(self, memory_manager)
```

**주요 메서드:**

1. `handle_conversation(conversation)`: 새로운 대화 처리의 메인 진입점
   ```python
   def handle_conversation(self, conversation):
       # 1. 전체 기록에 저장
       # 2. 사용자 입력 분석
       # 3. 관련 노드 찾기
       # 4. 새로운 주제인지 판단
       # 5. 노드 생성 또는 업데이트
   ```

2. `find_relevant_node(user_input)`: 사용자 입력과 가장 관련된 노드 탐지
   - 카테고리 키워드 우선 매칭
   - AI 기반 의미적 유사도 분석
   - 트리 구조 요약 활용

3. `find_or_create_category_node(user_input)`: 카테고리 노드 탐지/생성
   ```python
   # 지원되는 카테고리
   - 과일: ['사과', '포도', '딸기', '바나나', '오렌지', ...]
   - 동물: ['개', '고양이', '강아지', '새', '물고기', ...]
   - 음식: ['음식', '요리', '밥', '국', '찌개', '라면', ...]
   - 과목: ['수학', '영어', '국어', '과학', '사회', ...]
   ```

4. `check_for_new_topic(parent_node, user_input)`: 새로운 주제 여부 판단
   - 카테고리별 세밀한 하위 주제 분석
   - AI 기반 주제 변경 감지

5. `create_new_node(parent_node, user_input, conversation, conversation_index)`: 새 노드 생성
   - 키워드 기반 빠른 주제 추출
   - AI 기반 백업 주제 추출
   - 대화 요약 생성 및 좌표 설정

6. `update_node_and_parents(node, conversation, conversation_index)`: 노드 및 부모 업데이트
   - 기존 요약에 새 대화 통합
   - 좌표 범위 확장
   - 부모 노드 재귀적 업데이트 (카테고리 노드 제외)

### 4.4 AIManager 클래스

AI 모델 호출을 관리하고 비동기 처리를 지원하는 클래스입니다.

```python
class AIManager:
```

**주요 메서드:**

1. `call_ai(prompt, system, history, fine, api_key, retries)`: 기본 동기 AI 호출
   - Google Generative AI (Gemini) 모델 사용
   - 재시도 로직 및 오류 처리
   - ResourceExhausted 예외 처리

2. `call_ai_async_single(prompt, system, ...)`: 단일 비동기 AI 호출
   - asyncio.run_in_executor 활용
   - 동기 함수를 비동기로 래핑

3. `call_ai_async_multiple(queries, system_prompt, ...)`: 병렬 비동기 AI 호출
   - 다중 LOAD API 키 활용
   - 라운드 로빈 방식으로 API 키 분배
   - asyncio.gather로 병렬 실행

### 4.5 MainAI 클래스

사용자와 직접 대화하는 메인 AI 인터페이스입니다.

```python
class MainAI:
    def __init__(self)
```

**주요 메서드:**

1. `chat_async(user_input)`: 비동기 대화 처리 메인 함수
   ```python
   async def chat_async(self, user_input):
       # 1. 기억 필요 여부 키워드 기반 판단
       # 2. 필요 시 비동기 병렬 트리 검색
       # 3. 관련 기억 데이터 추출
       # 4. 맥락 기반 응답 생성
       # 5. 대화 기억 시스템에 저장
   ```

2. `_check_nodes_relevance_async(query, nodes)`: 비동기 병렬 노드 관련성 검사
   - 모든 노드에 대해 동시 관련성 검사
   - 다중 API 키 활용한 고속 처리
   - 검색 과정 실시간 시각화

3. `_extract_conversation_data(nodes)`: 관련 노드에서 대화 데이터 추출
   - 노드 좌표 기반 대화 인덱스 범위 추출
   - 전체 대화 기록에서 해당 구간 수집

4. `get_tree_status()`: 현재 트리 상태 정보 반환
   - 총 노드 수, 트리 요약, 루트 노드 ID

### 4.6 DataManager 클래스

파일 입출력 및 데이터 관리를 담당하는 유틸리티 클래스입니다.

```python
class DataManager:
```

**주요 정적 메서드:**

1. `load_json(file)`: JSON 파일 로드
   - 파일 존재 여부 확인
   - 안전한 파일 읽기

2. `save_json(file, data)`: JSON 파일 저장
   - 디렉토리 자동 생성
   - UTF-8 인코딩으로 저장

3. `history_str(buf)`: 대화 기록을 문자열로 변환
   - 중첩 리스트/딕셔너리 처리
   - 표준화된 대화 형식 생성

## 5. 주요 기능 및 명령어

### 5.1 명령줄 인터페이스

```bash
python hierarchical_main.py [옵션]
```

**사용 가능한 옵션:**

1. `--mode {test,chat}`: 실행 모드 선택
   - `test`: 사전 정의된 질문들로 시스템 테스트
   - `chat`: 사용자와의 대화형 모드 (기본값)

2. `--tree`: 현재 트리 구조 시각화 출력
   - 이모지와 계층 구조로 직관적 표시
   - 노드별 대화 인덱스 범위 표시
   - 카테고리별 통계 정보 제공

3. `--api-info`: 사용 가능한 API 키 정보 표시
   - 메인 API 키 개수
   - LOAD API 키 개수
   - 비동기 병렬 검색 가능 여부

### 5.2 트리 시각화 예시

```
=== 계층적 기억 트리 구조 ===
총 노드 수: 23

🌳 ROOT (대화: 0~0)
├── 자기 소개 (대화: 0~24)
│   💬 사용자는 자신의 이름이 서재민이라고 밝혔고...
│   └── 이름 확인 (대화: 33~33)
│       💬 사용자가 이전에 자신의 이름을 물어본 적이...
├── 과일 (카테고리)
│   💬 이 카테고리는 과일에 대한 모든 대화를 관리...
│   ├── 사과 (대화: 5~5)
│   ├── 포도 (대화: 8~8)
│   └── 딸기 (대화: 11~11)
└── 동물 (카테고리)
    ├── 고양이 (대화: 14~14)
    └── 개 (대화: 15~15)

==================================================
📊 트리 통계:
- 총 노드 수: 23
- 대화 기록 노드: 20
- 카테고리 노드: 3

📁 카테고리별 하위 노드:
  - 과일: 6개
  - 동물: 5개
  - 음식: 3개
==================================================
```

## 6. 핵심 알고리즘 및 프로세스

### 6.1 대화 처리 흐름

```
1. 사용자 입력 수신
   ↓
2. 기억 필요 여부 판단 (키워드 기반)
   ├─ 필요없음 → 단순 응답 생성
   └─ 필요함 ↓
3. 비동기 병렬 트리 검색
   ├─ 모든 노드 동시 관련성 검사
   ├─ LOAD API 키 라운드 로빈 활용
   └─ 관련 노드 필터링
   ↓
4. 관련 대화 데이터 추출
   ├─ 노드 좌표 기반 인덱스 추출
   └─ 전체 대화 기록에서 구간 수집
   ↓
5. 맥락 기반 응답 생성
   ├─ 과거 기억 + 현재 질문
   └─ 간결한 1-2문장 응답
   ↓
6. 대화 기억 시스템 저장
   ├─ 카테고리 노드 탐지/생성
   ├─ 새 주제 여부 판단
   ├─ 노드 생성 또는 업데이트
   └─ 부모 노드 요약 갱신
```

### 6.2 카테고리 분류 알고리즘

```python
def categorize_input(user_input):
    # 1. 키워드 매칭 (우선순위)
    if matches_fruit_keywords(user_input):
        return "과일"
    elif matches_animal_keywords(user_input):
        return "동물"
    elif matches_subject_keywords(user_input):
        return "과목"
    elif matches_food_keywords(user_input):
        return "음식"
    
    # 2. AI 기반 의미 분석 (백업)
    else:
        return ai_categorize(user_input)
```

### 6.3 비동기 병렬 검색 알고리즘

```python
async def parallel_search(query, nodes, api_keys):
    tasks = []
    for i, node in enumerate(nodes):
        api_key = api_keys[i % len(api_keys)]  # 라운드 로빈
        task = check_relevance_async(query, node, api_key)
        tasks.append(task)
    
    results = await asyncio.gather(*tasks)
    return filter_relevant_nodes(nodes, results)
```

## 7. 설정 파일 구조

### 7.1 config.py

```python
# API 키 설정
API_KEY = {
    'API_1': 'your_main_api_key',
    'API_2': 'your_backup_api_key'
}

# LOAD API 키 자동 감지
LOAD_API_KEYS = [
    load_key for i in range(1, 21) 
    if (load_key := globals().get(f'LOAD_{i}'))
]

# 파일 경로
HIERARCHICAL_MEMORY = 'memory/hierarchical_memory.json'
ALL_MEMORY = 'memory/all_memory.json'

# AI 모델 설정
GEMINI_MODEL = 'gemini-1.5-flash'

# Fine-tuning 데이터
FIND_NODE_FINE = [
    ("사과에 대해 궁금해", "사과"),
    ("수학 공부법 알려줘", "수학"),
    # ... 더 많은 예제
]
```

### 7.2 메모리 파일 구조

**hierarchical_memory.json**: 트리 구조 저장
```json
{
    "root_node_id": "uuid-string",
    "nodes": [
        {
            "node_id": "uuid-string",
            "topic": "ROOT",
            "summary": "최상위 루트 노드",
            "parent_id": null,
            "children_ids": ["child-uuid-1", "child-uuid-2"],
            "coordinates": {"start": 0, "end": 0},
            "references": []
        }
    ]
}
```

**all_memory.json**: 전체 대화 기록
```json
[
    [
        {"role": "user", "content": "안녕하세요"},
        {"role": "assistant", "content": "안녕하세요!"}
    ],
    [
        {"role": "user", "content": "사과가 좋아요"},
        {"role": "assistant", "content": "사과는 건강에 좋은 과일입니다."}
    ]
]
```

## 8. 성능 최적화 기법

### 8.1 비동기 병렬 처리

1. **다중 API 키 활용**: LOAD_1 ~ LOAD_20 자동 감지
2. **라운드 로빈 분배**: API 키를 순환하며 부하 분산
3. **asyncio.gather**: 모든 노드 동시 검사로 검색 속도 향상

### 8.2 메모리 효율성

1. **카테고리 노드 보호**: 요약 변경 방지로 의미 보존
2. **좌표 기반 인덱싱**: 효율적인 대화 구간 추출
3. **지연 로딩**: 필요한 데이터만 선택적 로드

### 8.3 응답 최적화

1. **키워드 기반 빠른 판단**: AI 호출 전 1차 필터링
2. **간결한 시스템 프롬프트**: 1-2문장 응답으로 토큰 절약
3. **재시도 로직**: API 오류 시 지수 백오프 적용

## 9. 확장 가능성

### 9.1 새로운 카테고리 추가

```python
# find_or_create_category_node 함수에 추가
hobby_keywords = ['게임', '영화', '독서', '운동', ...]
if any(keyword in user_input for keyword in hobby_keywords):
    return self.get_or_create_category_node('취미', '취미 활동에 대한 대화')
```

### 9.2 다른 AI 모델 지원

```python
# AIManager 클래스 확장
def call_openai(self, prompt, system):
    # OpenAI GPT 모델 연동
    pass

def call_claude(self, prompt, system):
    # Anthropic Claude 모델 연동
    pass
```

### 9.3 데이터베이스 연동

```python
# MemoryManager 확장
def save_to_database(self):
    # PostgreSQL, MongoDB 등 데이터베이스 저장
    pass
```

## 10. 결론

계층적 의미 기억 시스템은 기존의 선형적 기억 관리 방식을 넘어서, **트리 구조 기반의 의미적 분류**와 **비동기 병렬 검색**을 통해 효율적이고 직관적인 AI 대화 시스템을 구현했습니다. 

**주요 성과:**
- 🌳 체계적인 계층 구조로 정보 관리 효율성 증대
- ⚡ 비동기 병렬 처리로 검색 속도 대폭 향상  
- 🎯 의미적 분류로 정확한 맥락 인식 구현
- 📊 시각적 트리 구조로 사용자 편의성 제고

이 시스템은 확장 가능한 아키텍처를 바탕으로 다양한 도메인과 사용 사례에 적용할 수 있으며, AI 기반 장기 기억 관리의 새로운 패러다임을 제시합니다.
