# 계층적 의미 기억 시스템 (Hierarchical Semantic Memory System)

## 목차
- [1. 개요](#1-개요)
- [2. 설치 및 환경 설정](#2-설치-및-환경-설정)
- [3. 프로젝트 구조](#3-프로젝트-구조)
- [4. 핵심 모듈 분석](#4-핵심-모듈-분석)
- [5. 실행 방법](#5-실행-방법)
- [6. Discord 봇 설정](#6-discord-봇-설정)
- [7. 설정 파일 분석](#7-설정-파일-분석)
- [8. 기능별 상세 분석](#8-기능별-상세-분석)

---

## 1. 개요

### 1.1 목적
AI 기반 대화형 시스템에서 장기 기억을 효율적으로 관리하고 검색할 수 있는 계층적 의미 기억 시스템입니다. 기존의 선형적 기억 저장 방식의 한계를 극복하고, 의미적 연관성에 기반한 계층적 구조를 통해 더욱 효율적이고 맥락적인 기억 관리를 실현합니다.

### 1.2 시스템 아키텍처
```
┌─────────────────────────────────────────────────────┐
│                 User Interface                      │
│              (CLI, Discord Bot)                     │
└─────────────────┬───────────────────────────────────┘
                  │
┌─────────────────▼───────────────────────────────────┐
│                  MainAI                             │
│           (Main Conversation Handler)               │
└─────────────────┬───────────────────────────────────┘
                  │
┌─────────────────▼───────────────────────────────────┐
│                AuxiliaryAI                          │
│         (Assistant AI Classification)               │
└─────────────────┬───────────────────────────────────┘
                  │
┌─────────────────▼───────────────────────────────────┐
│              MemoryManager                          │
│         (Hierarchical Memory Manager)               │
└─────────────────┬───────────────────────────────────┘
                  │
┌─────────────────▼───────────────────────────────────┐
│  MemoryNode   │   DataManager  │ TreeCleanupEngine  │
│ (Memory Node) │ (Data Storage) │ (Tree Optimizer)   │
└─────────────────────────────────────────────────────┘
```

### 1.3 주요 특징
- **계층적 트리 구조**: 대화를 의미적 카테고리로 분류하여 계층적으로 관리
- **AI 기반 분류**: Gemini API를 활용한 자동 대화 분류 및 기억 검색
- **비동기 병렬 처리**: 다중 API 키를 활용한 고속 병렬 AI 호출
- **동적 트리 관리**: 실시간 트리 구조 최적화 및 자동 그룹화
- **다중 인터페이스**: CLI, Discord 봇 지원
- **디버그 모드**: 상세한 분류 과정 추적 및 모니터링

---

## 2. 설치 및 환경 설정

### 2.1 요구사항 설치

```bash
# requirements.txt 다운로드
pip install -r requirements.txt
```

#### 2.1.1 필수 패키지
- `google-generativeai>=0.3.0`: Gemini AI API 클라이언트
- `python-dotenv>=0.19.0`: 환경 변수 관리
- `discord.py>=2.0.0`: Discord 봇 기능
- `asyncio-throttle>=1.0.2`: 비동기 처리 제한

### 2.2 환경 변수 설정

프로젝트 루트에 `.env` 파일을 생성하고 다음 내용을 추가하세요:

```env
# 메인 API 키 (필수)
API_1=your_gemini_api_key_here
API_2=your_secondary_api_key_here

# LOAD API 키들 (병렬 처리용, 선택사항)
LOAD_1=your_load_api_key_1
LOAD_2=your_load_api_key_2
LOAD_3=your_load_api_key_3

# Discord 봇 토큰 (Discord 봇 사용 시)
DISCORD_TOKEN=your_discord_bot_token_here
```

### 2.3 API 키 설정 안내

#### 2.3.1 Gemini API 키 발급
1. [Google AI Studio](https://makersuite.google.com/app/apikey)에 접속
2. "Create API Key" 클릭
3. 발급받은 키를 `.env` 파일의 `API_1`에 설정

#### 2.3.2 Discord 봇 토큰 발급 (선택사항)
1. [Discord Developer Portal](https://discord.com/developers/applications)에 접속
2. "New Application" 클릭하여 앱 생성
3. "Bot" 탭에서 "Add Bot" 클릭
4. "Token" 복사하여 `.env` 파일의 `DISCORD_TOKEN`에 설정

---

## 3. 프로젝트 구조

```
hierarchical_semantic_memory_system/
├── HSMS/                           # 핵심 모듈 패키지
│   ├── __init__.py                 # 패키지 초기화
│   ├── AIManager.py                # AI 호출 관리자
│   ├── AuxiliaryAI.py              # 보조 AI (분류 담당)
│   ├── DataManager.py              # 데이터 관리자
│   ├── MainAI.py                   # 메인 AI (대화 담당)
│   ├── MemoryManager.py            # 기억 관리자
│   ├── MemoryNode.py               # 기억 노드
│   └── TreeCleanupEngine.py        # 트리 정리 엔진
├── memory/                         # 기억 저장소
│   ├── all_memory.json             # 전체 대화 기록
│   └── hierarchical_memory.json    # 계층적 트리 구조
├── config.py                       # 설정 및 Fine-tuning 데이터
├── main.py                         # 메인 실행 파일
├── hsms_discord.py                 # Discord 봇 구현
├── requirements.txt                # 패키지 의존성
└── README.md                       # 프로젝트 문서
```

---

## 4. 핵심 모듈 분석

### 4.1 HSMS/__init__.py
패키지 초기화 파일로 모든 핵심 클래스를 외부에서 임포트할 수 있도록 설정합니다.

**주요 클래스:**
- `DataManager`: 데이터 관리 및 파일 입출력
- `MemoryNode`: 개별 기억 노드
- `MemoryManager`: 계층적 기억 트리 관리
- `AIManager`: AI 호출 및 비동기 처리 관리
- `AuxiliaryAI`: 보조 AI (핵심 분류 및 기억 처리)
- `MainAI`: 메인 AI (사용자 대화 처리)
- `TreeCleanupEngine`: 트리 정리 및 최적화 엔진

### 4.2 AIManager.py (AI 호출 관리자)

#### 4.2.1 주요 기능
- AI 호출 최적화 및 오류 처리
- 비동기 병렬 처리 지원
- 성능 모니터링 및 통계 수집

#### 4.2.2 핵심 메서드
- **`call_ai(prompt, system, history, fine, api_key, retries, debug, call_info)`**: 정적 메서드로 기본 AI 호출 수행
  - `prompt`: 사용자 프롬프트
  - `system`: 시스템 프롬프트
  - `history`: 대화 히스토리
  - `fine`: Fine-tuning 데이터
  - `api_key`: 사용할 API 키
  - `retries`: 재시도 횟수 (기본 3회)
  - `debug`: 디버그 모드 여부
  - `call_info`: 호출 정보 저장용 딕셔너리

- **`call_ai_async_single(prompt, system, history, fine, api_key, retries)`**: 단일 비동기 AI 호출
- **`call_ai_async_multiple(queries, system_prompt, history, fine)`**: 다중 병렬 비동기 호출
- **`get_stats()`**: AI 호출 통계 반환

#### 4.2.3 주요 변수
- `debug`: 디버그 모드 활성화 여부
- `call_stats`: AI 호출 통계 정보 딕셔너리
  - `total_calls`: 총 호출 횟수
  - `total_time`: 총 소요 시간
  - `parallel_calls`: 병렬 호출 횟수
  - `error_count`: 오류 발생 횟수

### 4.3 AuxiliaryAI.py (보조 AI - 분류 담당)

#### 4.3.1 주요 기능
- 대화 내용 자동 분류 및 카테고리 배정
- 계층적 트리 구조 동적 관리
- 기억 검색 및 관련 대화 추출

#### 4.3.2 핵심 메서드
- **`handle_conversation(conversation, conversation_index)`**: 새로운 대화 처리 및 분류
- **`search_relevant_memories(user_input)`**: 사용자 입력과 관련된 기억 검색
- **`_process_conversation_with_dynamic_structure(conversation, conversation_index)`**: 동적 구조 고려 대화 분류
- **`_create_new_category_structure(conversation, conversation_index, user_input)`**: 신규 카테고리 및 하위 노드 생성
- **`_add_to_existing_category(conversation, conversation_index, category_name, user_input)`**: 기존 카테고리에 대화 추가
- **`_handle_multiple_categories(conversation, conversation_index, relevant_categories, user_input)`**: 다중 카테고리 상황 처리
- **`_check_category_relevance_async(user_input, categories)`**: 카테고리 관련성 병렬 판단
- **`_separate_conversation_by_categories(user_input, ai_response, categories)`**: 카테고리별 대화 분리
- **`_hierarchical_search(user_input)`**: 계층적 탐색 수행
- **`_evaluate_nodes_relevance(user_input, nodes)`**: 노드 관련성 병렬 평가

#### 4.3.3 주요 변수
- `memory_manager`: MemoryManager 인스턴스
- `ai_manager`: AIManager 인스턴스
- `debug`: 디버그 모드 활성화 여부
- `max_depth`: 트리 최대 깊이
- `top_search_n`: 반환할 최대 대화 수
- `_save_lock`: 트리 저장 동기화용 asyncio.Lock

### 4.4 DataManager.py (데이터 관리자)

#### 4.4.1 주요 기능
- JSON 파일 읽기/쓰기 관리
- 데이터 무결성 보장
- 오류 처리 및 백업 생성

#### 4.4.2 핵심 메서드 (모두 정적 메서드)
- **`load_json(file)`**: JSON 파일 로드 및 오류 처리
  - 파일 존재 확인
  - JSON 파싱 오류 시 자동 백업 생성
  - 빈 파일 처리
- **`save_json(file, data)`**: JSON 파일 저장
  - 디렉토리 자동 생성
  - UTF-8 인코딩으로 저장
- **`history_str(buf)`**: 대화 히스토리를 문자열로 변환

### 4.5 MainAI.py (메인 AI - 대화 담당)

#### 4.5.1 주요 기능
- 사용자와의 직접적인 대화 처리
- 기억 검색 필요성 AI 기반 판단
- 응답 생성 및 대화 저장 조율

#### 4.5.2 핵심 메서드
- **`chat_async(user_input)`**: 비동기 대화 처리 메인 메서드
- **`chat(user_input)`**: 동기 버전 대화 처리
- **`_needs_memory_search_async(user_input)`**: 기억 검색 필요성 AI 판단
- **`get_tree_status()`**: 트리 상태 정보 반환

#### 4.5.3 주요 변수
- `memory_manager`: MemoryManager 인스턴스
- `auxiliary_ai`: AuxiliaryAI 인스턴스
- `ai_manager`: AIManager 인스턴스
- `force_search`: 모든 대화에서 기억 호출 강제 여부
- `force_record`: AI 응답 없이 기록만 수행 여부
- `debug`: 디버그 모드 활성화 여부
- `max_depth`: 트리 최대 깊이
- `top_search_n`: 반환할 최대 대화 수

### 4.6 MemoryManager.py (기억 관리자)

#### 4.6.1 주요 기능
- 계층적 기억 트리 구조 관리
- 노드 추가/수정/삭제 작업
- 트리 무결성 검증

#### 4.6.2 핵심 메서드
- **`initialize_tree()`**: 트리 구조 초기화 또는 로드
- **`save_tree()`**: 트리를 파일에 저장
- **`get_node(node_id)`**: 노드 ID로 노드 조회
- **`get_root_node()`**: 루트 노드 반환
- **`add_node(node, parent_id)`**: 새 노드를 트리에 추가
- **`update_node(node_id, **kwargs)`**: 노드 정보 업데이트
- **`save_to_all_memory(conversation)`**: 대화를 전체 기록에 저장
- **`get_node_depth(node_id)`**: 특정 노드의 깊이 계산
- **`can_insert_child(parent_id, max_depth)`**: 자식 추가 가능 여부 확인
- **`validate_tree_integrity()`**: 트리 무결성 검증
- **`insert_group_above(existing_child_id, group_topic, group_summary)`**: 기존 노드 위에 그룹 삽입
- **`reparent_node(node_id, new_parent_id)`**: 노드 재배치

#### 4.6.3 주요 변수
- `debug`: 디버그 모드 활성화 여부
- `data_manager`: DataManager 인스턴스
- `memory_tree`: 노드 ID를 키로 하는 노드 딕셔너리
- `root_node_id`: 루트 노드의 ID

### 4.7 MemoryNode.py (기억 노드)

#### 4.7.1 주요 기능
- 개별 기억 단위 표현
- 계층 구조 관계 관리
- 대화 인덱스 추적

#### 4.7.2 핵심 메서드
- **`add_conversation(conversation_index)`**: 대화 인덱스 추가 (중복 방지)
- **`remove_conversation(conversation_index)`**: 대화 인덱스 제거
- **`get_conversation_count()`**: 노드가 가진 대화 수 반환
- **`to_dict()`**: 노드를 딕셔너리로 변환
- **`from_dict(cls, data)`**: 딕셔너리에서 노드 생성 (클래스 메서드)

#### 4.7.3 주요 변수
- `node_id`: 고유 노드 식별자 (UUID)
- `topic`: 노드의 주제/제목
- `summary`: 노드 내용 요약
- `parent_id`: 부모 노드 ID
- `children_ids`: 자식 노드 ID 리스트
- `coordinates`: 하위 호환성용 좌표 정보
- `references`: 다른 노드에 대한 참조 리스트
- `conversation_indices`: 관련 대화 인덱스 리스트

### 4.8 TreeCleanupEngine.py (트리 정리 엔진)

#### 4.8.1 주요 기능
- 트리 구조 자동 최적화
- 노드 클러스터링 및 그룹화
- 중복 노드 병합 처리

#### 4.8.2 핵심 메서드
- **`run_cleanup(rename_nodes, dry_run)`**: 전체 트리 정리 프로세스 실행
- **`_cluster_excessive_fanouts()`**: 자식 과다 노드 클러스터링
- **`_cluster_nodes_by_similarity(nodes)`**: 유사도 기반 노드 클러스터링
- **`_build_similarity_matrix(nodes)`**: 노드 간 유사도 매트릭스 구축
- **`_connected_components_clustering(nodes, similarity_matrix)`**: 연결 요소 기반 클러스터링
- **`_create_cluster_group(parent_id, cluster_nodes, group_name)`**: 클러스터 그룹 생성
- **`_resolve_cross_parent_duplicates()`**: 교차 부모간 중복 해결
- **`_merge_similar_leaves()`**: 유사한 리프 노드 병합

#### 4.8.3 주요 변수
- `memory_manager`: MemoryManager 인스턴스
- `ai_manager`: AIManager 인스턴스
- `max_depth`: 트리 최대 깊이
- `fanout_limit`: 노드당 최대 자식 수
- `debug`: 디버그 모드 활성화 여부
- `cleanup_stats`: 정리 작업 통계 정보

---

## 5. 실행 방법

### 5.1 기본 실행

```bash
# 기본 대화형 모드
python main.py --mode chat

# 테스트 모드 (미리 정의된 질문들로 테스트)
python main.py --mode test

# 검색 전용 모드 (모든 대화에서 기억 검색)
python main.py --mode search

# Discord 봇 모드
python main.py --mode discord
```

### 5.2 고급 옵션

```bash
# 디버그 모드로 실행 (상세 분류 과정 출력)
python main.py --mode chat --debug

# 강제 검색 모드 (모든 대화에서 기억 탐색)
python main.py --mode chat --force-search

# 기록 전용 모드 (AI 응답 없이 정보만 저장)
python main.py --mode chat --force-record

# 트리 최대 깊이 설정
python main.py --mode chat --max-depth 5

# 검색 결과 개수 제한
python main.py --mode chat --top-search-n 5
```

### 5.3 트리 관리 옵션

```bash
# 현재 트리 구조 확인
python main.py --tree

# API 키 정보 확인
python main.py --api-info

# 트리 구조 최적화 (실제 적용)
python main.py --clean-tree

# 트리 구조 최적화 (계획만 출력)
python main.py --clean-tree --dry-run

# 트리 최적화 + 노드 이름 재생성
python main.py --clean-tree --rename

# 팬아웃 제한 설정하여 최적화
python main.py --clean-tree --fanout-limit 8
```

### 5.4 명령줄 인수 상세 설명

#### 5.4.1 모드 선택
- `--mode test`: 미리 정의된 테스트 질문들로 시스템 테스트
- `--mode chat`: 사용자와의 대화형 모드
- `--mode discord`: Discord 봇으로 실행
- `--mode search`: 검색 전용 모드 (기억 탐색만 수행)

#### 5.4.2 동작 제어
- `--force-search`: 모든 대화에서 강제로 기억 검색
- `--force-record`: AI 응답 생성 없이 대화만 기록
- `--debug`: 상세한 디버그 정보 출력

#### 5.4.3 트리 구조 설정
- `--max-depth N`: 트리 최대 깊이 설정 (기본값: 4, 최소: 3)
- `--top-search-n N`: 검색 시 반환할 최대 대화 수 (0=무제한)

#### 5.4.4 트리 정리 기능
- `--clean-tree`: 트리 구조 최적화 실행
- `--fanout-limit N`: 노드당 최대 자식 수 (기본값: 12)
- `--rename`: 트리 정리 시 노드 이름 자동 재생성
- `--dry-run`: 실제 변경 없이 계획만 출력

#### 5.4.5 정보 조회
- `--tree`: 현재 트리 구조 시각화 출력
- `--api-info`: 설정된 API 키 정보 표시

---

## 6. Discord 봇 설정

### 6.1 봇 생성 및 설정

1. **Discord 개발자 포털 접속**
   ```
   https://discord.com/developers/applications
   ```

2. **새 애플리케이션 생성**
   - "New Application" 클릭
   - 봇 이름 입력 (예: "기억 관리 AI")

3. **봇 계정 생성**
   - 좌측 메뉴에서 "Bot" 선택
   - "Add Bot" 클릭
   - 토큰 복사하여 `.env` 파일에 저장

4. **권한 설정**
   - "OAuth2" > "URL Generator" 선택
   - Scopes: `bot` 체크
   - Bot Permissions:
     - `Send Messages`
     - `Read Message History`
     - `Use Slash Commands`
     - `Add Reactions`

### 6.2 Discord 봇 명령어

#### 6.2.1 기본 사용법
- **멘션을 통한 대화**: `@봇이름 안녕하세요`
- **DM 대화**: 봇에게 직접 메시지 전송

#### 6.2.2 슬래시 명령어
- **`!help` / `!도움말`**: 도움말 표시
- **`!tree` / `!트리`**: 현재 기억 트리 구조 표시
- **`!status` / `!상태`**: 봇 상태 정보 표시
- **`!clear` / `!초기화`**: 서버의 기억 초기화 (관리자 전용)
- **`!force [on/off]` / `!강제 [켜기/끄기]`**: 강제 검색 모드 토글 (관리자 전용)
- **`!debug [on/off]` / `!디버그 [켜기/끄기]`**: 디버그 모드 토글 (관리자 전용)

### 6.3 hsms_discord.py 주요 함수

#### 6.3.1 봇 설정 함수
- **`get_ai_instance(guild_id, force_search, top_search_n)`**: 서버별 AI 인스턴스 관리
- **`set_debug_mode(debug)`**: 전역 디버그 모드 설정

#### 6.3.2 이벤트 핸들러
- **`on_ready()`**: 봇 준비 완료 시 실행
- **`on_message(message)`**: 메시지 수신 시 실행

#### 6.3.3 명령어 핸들러
- **`help_command(ctx)`**: 도움말 표시
- **`tree_command(ctx)`**: 트리 구조 표시
- **`status_command(ctx)`**: 봇 상태 표시
- **`clear_command(ctx)`**: 기억 초기화 (관리자 전용)
- **`force_command(ctx, mode)`**: 강제 모드 토글 (관리자 전용)
- **`debug_command(ctx, mode)`**: 디버그 모드 토글 (관리자 전용)

#### 6.3.4 주요 변수
- `ai_instances`: 서버별 MainAI 인스턴스 딕셔너리
- `debug_mode`: 전역 디버그 모드 상태

---

## 7. 설정 파일 분석

### 7.1 config.py 주요 상수

#### 7.1.1 파일 경로
- **`ALL_MEMORY`**: `'memory/all_memory.json'` - 전체 대화 기록 파일
- **`HIERARCHICAL_MEMORY`**: `'memory/hierarchical_memory.json'` - 계층적 트리 구조 파일

#### 7.1.2 AI 모델 설정
- **`GEMINI_MODEL`**: `"gemini-2.5-flash"` - 사용할 Gemini 모델 버전

#### 7.1.3 API 키 설정
- **`API_KEY`**: 메인 API 키 딕셔너리
  - `API_1`: 주요 API 키 (필수)
  - `API_2`: 보조 API 키 (선택사항)
- **`LOAD_API_KEYS`**: 병렬 처리용 API 키 리스트 (자동 로드)
- **`DISCORD_TOKEN`**: Discord 봇 토큰 (선택사항)

#### 7.1.4 테스트 데이터
- **`TEST_QUESTIONS`**: 시스템 테스트용 질문 리스트
- **`RECORD_TEST_QUESTIONS`**: 기록 전용 테스트 질문 리스트

### 7.2 Fine-tuning 데이터 세트

#### 7.2.1 노드 유사성 판단 (NODE_SIMILARITY_FINE)
트리 정리 엔진에서 노드 간 유사성을 판단하는 데 사용되는 학습 데이터입니다.

**예시 구조:**
```python
[
    ["""노드1: "DNA 복제 과정"
    설명1: 유전 정보의 정확한 복제와 오류 수정 메커니즘에 대한 논의
    
    노드2: "DNA 손상 복구"  
    설명2: UV 손상으로 인한 피리미딘 이합체 형성과 복구 시스템
    
    이 두 노드가 같은 상위 그룹으로 묶일 만큼 유사한가요?""", "True"]
]
```

#### 7.2.2 카테고리 관련성 판단 (CATEGORY_RELEVANCE_FINE)
사용자 대화와 기존 카테고리의 관련성을 판단하는 학습 데이터입니다.

#### 7.2.3 대화 분리 (CONVERSATION_SEPARATION_FINE)
다중 카테고리에 해당하는 대화를 카테고리별로 분리하는 학습 데이터입니다.

#### 7.2.4 기타 Fine-tuning 데이터
- **`NEW_TOPIC_FINE`**: 새 주제 감지용 데이터
- **`MEMORY_SEARCH_FINE`**: 메모리 검색 필요성 판단용 데이터
- **`GROUP_SIMILARITY_FINE`**: 그룹 유사도 판단용 데이터
- **`CATEGORY_NAME_FINE`**: 카테고리명 생성용 데이터

---

## 8. 기능별 상세 분석

### 8.1 계층적 기억 구조

#### 8.1.1 트리 구조 개념
```
ROOT (루트)
├── 개인정보 (카테고리)
│   ├── 기본정보 (하위 카테고리/대화 노드)
│   └── 가족관계 (하위 카테고리/대화 노드)
├── 과학 (카테고리)
│   ├── 물리학 (하위 카테고리)
│   │   ├── 양자역학 (대화 노드)
│   │   └── 상대성이론 (대화 노드)
│   └── 화학 (하위 카테고리)
│       ├── 유기화학 (대화 노드)
│       └── 무기화학 (대화 노드)
└── 취미 (카테고리)
    ├── 음악 (하위 카테고리)
    └── 독서 (하위 카테고리)
```

#### 8.1.2 노드 타입
- **ROOT 노드**: 전체 트리의 최상위 노드
- **카테고리 노드**: `coordinates["start"] == -1`로 식별
- **대화 노드**: `coordinates["start"] >= 0`로 식별, 실제 대화 내용 포함

#### 8.1.3 좌표 시스템
- **기존 방식**: `coordinates["start"]`와 `coordinates["end"]`로 대화 범위 표시
- **새로운 방식**: `conversation_indices` 리스트로 관련 대화 인덱스 직접 관리

### 8.2 AI 기반 분류 시스템

#### 8.2.1 분류 과정
1. **관련성 평가**: 사용자 입력과 기존 카테고리들의 관련성 AI 판단
2. **카테고리 수에 따른 분기**:
   - 0개: 새 카테고리 생성
   - 1개: 기존 카테고리에 추가
   - 2개 이상: 다중 카테고리 처리 (분리 또는 그룹화)

#### 8.2.2 동적 구조 관리
- **깊이 제한 확인**: `max_depth` 파라미터로 트리 깊이 제한
- **그룹화 결정**: 유사한 카테고리들의 자동 그룹화
- **병합 정책**: 깊이 제한 시 기존 노드에 병합

#### 8.2.3 대화 분리 알고리즘
다중 카테고리 관련 대화를 카테고리별로 분리하여 각각 저장:
```python
# 예시: "영어 문법이 어렵고 수학도 복잡해"
# → 영어 카테고리: "영어 문법이 어렵다"
# → 수학 카테고리: "수학이 복잡하다"
```

### 8.3 기억 검색 시스템

#### 8.3.1 검색 필요성 판단
AI가 사용자 입력을 분석하여 과거 기억 참조 필요성을 판단:
- **True**: 과거 대화 참조 필요 (예: "저번에 말한 그 영화 제목이 뭐였지?")
- **False**: 일반적인 질문 (예: "오늘 날씨 어때?")

#### 8.3.2 계층적 탐색 알고리즘
1. **1단계**: 최상위 카테고리 노드들의 관련성 평가
2. **2단계**: 관련 카테고리의 하위 노드들을 탐색 후보에 추가
3. **3단계**: 후보 노드들에서 실제 대화 수집 및 반환

#### 8.3.3 검색 결과 포맷
```
======1번 대화======
사용자: [사용자 발언]
AI: [AI 응답]
==================

======5번 대화======
사용자: [사용자 발언]
AI: [AI 응답]
==================

위 기억을 참고해서 응답해라.
```

### 8.4 트리 최적화 시스템

#### 8.4.1 최적화 필요성
- **과도한 팬아웃**: 한 노드의 자식이 너무 많을 때 (기본값: 12개 초과)
- **중복 노드**: 동일한 주제를 다루는 노드들
- **유사 노드**: 의미적으로 유사한 노드들

#### 8.4.2 클러스터링 알고리즘
1. **유사도 매트릭스 구축**: AI를 활용한 노드 간 유사도 판단
2. **연결 요소 탐색**: 그래프 이론의 연결 요소 알고리즘 적용
3. **클러스터 그룹화**: 유사한 노드들을 하나의 그룹으로 묶기

#### 8.4.3 정리 작업 통계
```python
cleanup_stats = {
    'moves': 0,        # 이동된 노드 수
    'merges': 0,       # 병합된 노드 수
    'new_groups': 0,   # 생성된 그룹 수
    'renames': 0,      # 이름이 변경된 노드 수
    'start_time': 0,   # 시작 시간
    'end_time': 0      # 종료 시간
}
```

### 8.5 성능 최적화 기능

#### 8.5.1 비동기 병렬 처리
- **다중 API 키 활용**: `LOAD_API_KEYS`를 통한 병렬 AI 호출
- **라운드 로빈 방식**: API 키들을 순환하며 부하 분산
- **예외 처리**: 개별 호출 실패 시에도 전체 처리 계속

#### 8.5.2 메모리 효율성
- **지연 로딩**: 필요한 시점에만 트리 구조 로드
- **선택적 저장**: 변경사항이 있을 때만 파일 저장
- **참조 관리**: 순환 참조 방지 및 메모리 누수 방지

#### 8.5.3 디버깅 및 모니터링
- **상세 로깅**: 각 단계별 처리 과정 추적
- **성능 측정**: AI 호출 시간, 처리 단계별 소요 시간 측정
- **통계 수집**: 호출 횟수, 성공률, 오류율 등 통계 정보

---

## 마무리

이 계층적 의미 기억 시스템은 AI 기반의 지능적인 대화 분류와 기억 관리를 통해 더욱 맥락적이고 효율적인 대화형 AI 시스템을 구현합니다. 모듈화된 설계와 확장 가능한 구조를 통해 다양한 사용 사례에 적용할 수 있으며, Discord 봇과 CLI 인터페이스를 통해 접근성을 높였습니다.

주요 강점:
- **지능적 분류**: AI 기반 자동 대화 분류 및 카테고리화
- **효율적 검색**: 계층적 구조를 활용한 빠른 기억 검색
- **동적 최적화**: 실시간 트리 구조 최적화 및 관리
- **확장성**: 모듈화된 설계로 기능 확장 용이
- **다중 인터페이스**: CLI와 Discord 봇 지원

이 시스템을 통해 사용자는 더욱 자연스럽고 맥락적인 AI 대화 경험을 얻을 수 있으며, 장기간에 걸친 대화 기록을 효율적으로 관리하고 활용할 수 있습니다.
  - `--clean-tree`: 트리 구조 최적화 실행
  - `--fanout-limit`: 노드당 최대 자식 수 (기본값: 12)
  - `--rename`: 트리 정리 시 노드 이름 자동 재명명
  - `--dry-run`: 실제 변경 없이 계획만 출력

- **`show_api_info()`**: 사용 가능한 API 키 정보를 표시한다
  - 메인 API 키 개수 출력
  - LOAD API 키 개수 출력
  - 병렬 처리 가능 여부 표시

- **`show_tree_structure()`**: 현재 메모리 트리 구조를 도식화하여 표시한다
  - ROOT부터 시작하는 계층적 구조
  - 각 노드의 주제와 대화 인덱스 표시
  - 트리 깊이와 노드 개수 통계 제공

- **`run_tree_cleanup(args)`**: 트리 정리 엔진을 실행한다
  - TreeCleanupEngine 인스턴스 생성
  - 설정된 매개변수로 정리 프로세스 실행
  - 정리 전후 통계 비교 제공

#### 2.1.2 모드별 실행 흐름

**Chat 모드**:
1. MainAI 인스턴스 생성 (force_search, force_record, debug, max_depth 설정)
2. 무한 루프로 사용자 입력 대기
3. 각 입력에 대해 `chat_async()` 호출
4. 응답 출력 및 다음 입력 대기

**Test 모드**:
1. MainAI 인스턴스 생성
2. config.py의 TEST_QUESTIONS 또는 RECORD_TEST_QUESTIONS 순회
3. 각 질문에 대해 시간 측정하며 처리
4. 처리 시간과 트리 노드 수 통계 출력

**Discord 모드**:
1. hsms_discord.py 실행
2. Discord 봇 토큰으로 로그인
3. 메시지 이벤트 리스너 활성화

**Search 모드**:
1. MemoryManager 인스턴스 생성
2. 사용자 검색어 입력 대기
3. `search_memory()` 메서드로 관련 노드 검색
4. 검색 결과 포맷하여 출력

### 2.2 config.py (설정 및 Fine Tuning 데이터)

#### 2.2.1 주요 변수
- **`API_KEY`**: 메인 Gemini API 키 딕셔너리
  - `API_1`: 주요 API 키 (필수)
  - `API_2`: 백업 API 키 (선택)

- **`LOAD_API_KEYS`**: 병렬 처리용 추가 API 키 리스트
  - 최대 30개 지원
  - 환경변수 LOAD_1 ~ LOAD_30에서 자동 로드

- **`GEMINI_MODEL`**: 사용할 Gemini 모델명 ("gemini-2.5-flash")

- **`ALL_MEMORY`**: 전체 대화 기록 저장 파일 경로
- **`HIERARCHICAL_MEMORY`**: 계층적 트리 구조 저장 파일 경로

#### 2.2.2 Fine Tuning 데이터

**`CATEGORY_RELEVANCE_FINE`**: 카테고리 관련성 판단 예시
- 대화가 특정 카테고리와 관련이 있는지 판단
- 각 예시는 [질문, 답변] 형태
- True/False 형태의 판단 결과

**`CONVERSATION_SEPARATION_FINE`**: 대화 분리 예시
- 여러 카테고리가 관련된 대화를 카테고리별로 분리
- 복합 주제 대화의 올바른 분리 방법 제시

**`MEMORY_SEARCH_FINE`**: 메모리 검색 필요성 판단 예시
- 과거 대화 참조가 필요한 경우 True
- 일반적인 질문이나 새로운 정보 제공 시 False

**`GROUP_SIMILARITY_FINE`**: 그룹 유사도 판단 예시
- 두 카테고리가 하나의 그룹으로 묶일 만큼 유사한지 판단
- 학문 분야, 취미 활동 등의 그룹화 기준 제시

**`NODE_SIMILARITY_FINE`**: 노드 유사성 판단 예시 (TreeCleanupEngine용)
- 두 노드가 같은 상위 그룹으로 묶일 만큼 유사한지 판단
- TreeCleanupEngine의 클러스터링에 활용

#### 2.2.3 테스트 데이터
- **`TEST_QUESTIONS`**: 기본 테스트 질문 목록
- **`RECORD_TEST_QUESTIONS`**: 기록 전용 모드 테스트 질문 목록

### 2.3 HSMS/MemoryNode.py (메모리 노드 클래스)

#### 2.3.1 클래스 속성
- **`node_id`**: UUID4 형태의 고유 노드 식별자
- **`topic`**: 노드의 주제 또는 제목
- **`summary`**: 해당 노드에 저장된 대화의 요약
- **`parent_id`**: 부모 노드의 ID (ROOT는 None)
- **`children_ids`**: 하위 노드들의 ID 리스트
- **`coordinates`**: 하위 호환성을 위한 기존 좌표 시스템 (deprecated)
- **`references`**: 다른 노드에 대한 참조 저장
- **`conversation_indices`**: 이 노드와 관련된 대화 인덱스 리스트

#### 2.3.2 주요 메서드
- **`__init__()`**: 노드 초기화
  - 모든 속성을 선택적 매개변수로 받음
  - node_id가 None이면 자동으로 UUID4 생성

- **`add_conversation(conversation_index)`**: 대화 인덱스를 노드에 추가
  - 중복 방지 로직 포함
  - 정수 유효성 검사
  - 자동 정렬 유지

- **`remove_conversation(conversation_index)`**: 대화 인덱스를 노드에서 제거
  - 존재 여부 확인 후 제거

- **`get_conversation_count()`**: 이 노드가 가진 대화 수 반환

- **`to_dict()`**: 노드를 딕셔너리로 직렬화
  - JSON 저장을 위한 변환

- **`from_dict()`**: 딕셔너리에서 노드 객체 복원
  - 클래스 메서드로 구현

### 2.4 HSMS/DataManager.py (데이터 관리 클래스)

#### 2.4.1 정적 메서드
- **`load_json(file)`**: JSON 파일을 안전하게 로드한다
  - 파일 존재 여부 확인
  - JSON 파싱 오류 시 자동 백업 생성
  - 빈 파일 처리 로직
  - UTF-8 인코딩 지원

- **`save_json(file, data)`**: 데이터를 JSON 파일로 저장한다
  - 디렉토리 자동 생성
  - UTF-8 인코딩으로 저장
  - 들여쓰기 포함한 가독성 있는 형태

- **`history_str(buf)`**: 대화 히스토리를 문자열로 변환한다
  - 리스트나 딕셔너리 형태의 대화 기록 처리
  - role과 content 필드 추출

### 2.5 HSMS/AIManager.py (AI 호출 관리 클래스)

#### 2.5.1 클래스 속성
- **`debug`**: 디버그 모드 활성화 여부
- **`call_stats`**: AI 호출 통계 정보
  - `total_calls`: 총 호출 수
  - `total_time`: 총 소요 시간
  - `parallel_calls`: 병렬 호출 수
  - `error_count`: 오류 발생 수

#### 2.5.2 주요 메서드
- **`call_ai()`**: 정적 메서드로 단일 AI 호출을 수행한다
  - 매개변수:
    - `prompt`: 사용자 질문
    - `system`: 시스템 지침
    - `history`: 대화 히스토리
    - `fine`: Fine Tuning 데이터
    - `api_key`: 사용할 API 키
    - `retries`: 재시도 횟수 (기본값: 3)
    - `debug`: 디버그 출력 여부
  - ResourceExhausted 예외 처리
  - 지수 백오프 재시도 로직
  - 응답 텍스트 정리 (assistant: 접두사 제거)

- **`call_ai_async_single()`**: 단일 비동기 AI 호출
  - call_ai를 executor에서 실행
  - 통계 정보 수집

- **`call_ai_async_multiple()`**: 병렬 비동기 AI 호출
  - 여러 프롬프트를 동시에 처리
  - LOAD_API_KEYS 활용한 병렬 처리
  - Fine Tuning 데이터 지원
  - 실패한 호출에 대한 재시도 로직

### 2.6 HSMS/MemoryManager.py (메모리 관리 클래스)

#### 2.6.1 주요 속성
- **`memory_tree`**: 전체 노드를 저장하는 딕셔너리 {node_id: MemoryNode}
- **`data_manager`**: DataManager 인스턴스
- **`root_node_id`**: ROOT 노드의 ID
- **`debug`**: 디버그 모드 활성화 여부

#### 2.6.2 주요 메서드
- **`__init__()`**: 메모리 관리자 초기화
  - 기존 데이터 로드
  - ROOT 노드 생성 또는 확인

- **`load_tree()`**: 저장된 트리 구조를 메모리에 로드
  - hierarchical_memory.json에서 로드
  - 노드 객체로 복원

- **`save_tree()`**: 현재 트리 구조를 파일에 저장
  - 딕셔너리로 직렬화 후 JSON 저장

- **`add_node(node, parent_id)`**: 새 노드를 트리에 추가
  - 부모-자식 관계 설정
  - 트리 구조 유지

- **`get_node(node_id)`**: 노드 ID로 노드 객체 조회

- **`search_memory(query, limit=10)`**: 메모리 검색 수행
  - 주제와 요약에서 키워드 검색
  - 관련도 점수 계산
  - 상위 limit개 결과 반환

- **`get_node_depth(node_id)`**: 노드의 깊이 계산
  - ROOT부터의 거리

- **`get_node_path(node_id)`**: ROOT부터 해당 노드까지의 경로 반환

- **`update_node(node_id, **kwargs)`**: 노드 정보 업데이트
  - topic, summary 등의 속성 수정

### 2.7 HSMS/MainAI.py (메인 AI 클래스)

#### 2.7.1 주요 속성
- **`memory_manager`**: MemoryManager 인스턴스
- **`auxiliary_ai`**: AuxiliaryAI 인스턴스
- **`ai_manager`**: AIManager 인스턴스
- **`force_search`**: 모든 대화에서 기억 검색 강제 여부
- **`force_record`**: AI 응답 없이 기록만 수행 여부
- **`debug`**: 디버그 모드 활성화 여부
- **`max_depth`**: 트리 최대 깊이

#### 2.7.2 주요 메서드
- **`chat_async(user_input)`**: 비동기 대화 처리
  - force_record 모드와 일반 모드 분기
  - 메모리 검색 필요성 판단
  - AI 응답 생성
  - 대화 기록 저장

- **`_search_memory_if_needed(user_input)`**: 메모리 검색 필요성 판단 및 실행
  - MEMORY_SEARCH_FINE 활용한 AI 판단
  - force_search 모드에서는 항상 검색

- **`_generate_response_with_memory(user_input, memories)`**: 메모리 기반 응답 생성
  - 관련 기억을 컨텍스트로 포함
  - 일관성 있는 응답 생성

### 2.8 HSMS/AuxiliaryAI.py (보조 AI 클래스)

#### 2.8.1 주요 속성
- **`memory_manager`**: MemoryManager 인스턴스
- **`ai_manager`**: AIManager 인스턴스
- **`debug`**: 디버그 모드
- **`max_depth`**: 트리 최대 깊이

#### 2.8.2 핵심 메서드
- **`handle_conversation(conversation)`**: 대화 처리 메인 함수
  - 대화 분류 및 저장
  - 카테고리 생성 또는 기존 노드 업데이트

- **`find_or_create_category(user_content)`**: 카테고리 탐색 및 생성
  - 기존 카테고리와의 관련성 판단
  - 새 카테고리 생성 결정
  - AB 그룹핑 시스템 활용

- **`create_dynamic_tree_structure(category_id, new_conversation)`**: 동적 트리 구조 생성
  - 깊이 제한 확인
  - 기존 노드와의 유사성 판단
  - 새 노드 생성 또는 기존 노드 업데이트

- **`group_categories_if_needed(categories)`**: AB 그룹핑 시스템
  - 카테고리 수가 fanout_limit 초과 시 활성화
  - 유사한 카테고리들을 그룹으로 묶음
  - GROUP_SIMILARITY_FINE 활용

### 2.9 HSMS/TreeCleanupEngine.py (트리 최적화 엔진)

#### 2.9.1 주요 속성
- **`memory_manager`**: MemoryManager 인스턴스
- **`ai_manager`**: AIManager 인스턴스
- **`max_depth`**: 트리 최대 깊이
- **`fanout_limit`**: 노드당 최대 자식 수
- **`debug`**: 디버그 모드
- **`cleanup_stats`**: 정리 작업 통계

#### 2.9.2 핵심 메서드
- **`run_cleanup(rename_nodes, dry_run)`**: 전체 정리 프로세스 실행
  - 자식 과다 노드 클러스터링
  - 중복 노드 해결
  - 유사 리프 병합
  - 노드 이름 정리 (옵션)

- **`_cluster_excessive_fanouts()`**: 자식 수가 fanout_limit를 초과하는 노드 처리
  - 유사도 기반 클러스터링
  - 새로운 그룹 노드 생성

- **`_build_similarity_matrix(nodes)`**: 노드 간 유사도 매트릭스 구축
  - NODE_SIMILARITY_FINE 활용
  - 병렬 AI 호출로 성능 최적화

- **`_connected_components_clustering(nodes, similarity_matrix)`**: 연결 요소 알고리즘
  - DFS 기반 클러스터링
  - 유사한 노드들을 그룹화

### 2.10 hsms_discord.py (Discord 봇 인터페이스)

#### 2.10.1 주요 클래스
- **`HSMSBot`**: Discord Bot 클래스
  - MainAI 인스턴스 포함
  - 비동기 메시지 처리

#### 2.10.2 주요 기능
- **메시지 이벤트 처리**: 사용자 메시지에 대한 AI 응답
- **명령어 시스템**: !hsms, !tree 등의 봇 명령어
- **멀티 채널 지원**: 여러 Discord 채널에서 동시 작동

## 3. 모드별 작동 순서

### 3.1 Chat 모드 (python main.py --mode chat)

1. **초기화 단계**
   ```
   main.py 실행
   ├── parse_arguments() - 명령줄 인수 파싱
   ├── MainAI 인스턴스 생성
   │   ├── MemoryManager 초기화
   │   │   ├── DataManager로 기존 데이터 로드
   │   │   └── ROOT 노드 확인/생성
   │   ├── AuxiliaryAI 초기화
   │   └── AIManager 초기화
   └── 무한 루프 시작
   ```

2. **사용자 입력 처리 단계**
   ```
   사용자 입력 받음
   ├── MainAI.chat_async(user_input) 호출
   ├── _search_memory_if_needed() - 메모리 검색 필요성 판단
   │   ├── MEMORY_SEARCH_FINE으로 AI 판단
   │   └── 필요시 MemoryManager.search_memory() 실행
   ├── AI 응답 생성
   │   ├── 메모리 있으면: _generate_response_with_memory()
   │   └── 메모리 없으면: 직접 AI 호출
   └── 대화 기록 저장
       └── AuxiliaryAI.handle_conversation() 호출
   ```

3. **대화 분류 및 저장 단계**
   ```
   AuxiliaryAI.handle_conversation()
   ├── find_or_create_category() - 카테고리 찾기/생성
   │   ├── 기존 카테고리와 관련성 판단 (CATEGORY_RELEVANCE_FINE)
   │   ├── 관련 카테고리 없으면 새 카테고리 생성
   │   └── group_categories_if_needed() - AB 그룹핑 시스템
   ├── create_dynamic_tree_structure() - 동적 트리 구조 생성
   │   ├── 깊이 제한 확인
   │   ├── 기존 노드와 유사성 판단
   │   └── 새 노드 생성 또는 기존 노드 업데이트
   └── MemoryManager.save_tree() - 트리 저장
   ```

### 3.2 Force-Record 모드 (python main.py --mode chat --force-record)

1. **초기화 단계** (Chat 모드와 동일)

2. **사용자 입력 처리 단계**
   ```
   사용자 입력 받음
   ├── MainAI.chat_async(user_input) 호출
   ├── force_record 모드 확인
   ├── 빈 AI 응답("")으로 대화 객체 생성
   │   └── {"role": "user", "content": user_input}
   │       {"role": "assistant", "content": ""}
   └── AuxiliaryAI.handle_conversation() 호출 (AI 응답 없이)
   ```

3. **특별 처리 단계**
   ```
   AuxiliaryAI에서 빈 응답 감지
   ├── 사용자 발언만으로 요약 생성
   │   └── "사용자가 [내용]에 대해 이야기했다" 형식
   ├── 카테고리 분류 (일반 모드와 동일)
   └── 기억 저장 (사용자 정보 중심)
   ```

### 3.3 Test 모드 (python main.py --mode test)

1. **초기화 단계**
   ```
   main.py 실행
   ├── parse_arguments() 
   ├── MainAI 인스턴스 생성
   └── TEST_QUESTIONS 또는 RECORD_TEST_QUESTIONS 로드
   ```

2. **순차 테스트 단계**
   ```
   각 테스트 질문에 대해:
   ├── 시작 시간 기록
   ├── MainAI.chat_async(question) 호출
   ├── 종료 시간 기록
   ├── 처리 시간 계산
   ├── 현재 트리 노드 수 조회
   └── 결과 출력 (질문, 응답, 시간, 노드 수)
   ```

### 3.4 Tree Cleanup 모드 (python main.py --clean-tree)

1. **초기화 단계**
   ```
   main.py 실행
   ├── parse_arguments()
   ├── MemoryManager 인스턴스 생성
   └── TreeCleanupEngine 인스턴스 생성
   ```

2. **정리 프로세스 단계**
   ```
   TreeCleanupEngine.run_cleanup()
   ├── 정리 전 트리 통계 생성
   ├── _cluster_excessive_fanouts() - 자식 과다 노드 클러스터링
   │   ├── fanout_limit 초과 노드 찾기
   │   ├── _build_similarity_matrix() - 유사도 매트릭스 구축
   │   │   └── NODE_SIMILARITY_FINE으로 병렬 AI 판단
   │   ├── _connected_components_clustering() - 클러스터링
   │   └── _create_cluster_group() - 새 그룹 노드 생성
   ├── _resolve_cross_parent_duplicates() - 중복 노드 해결
   │   ├── 동일 topic 노드 찾기
   │   └── _merge_duplicate_nodes() - 노드 병합
   ├── _merge_similar_leaves() - 유사 리프 노드 병합
   ├── _rename_nodes() - 노드 이름 정리 (옵션)
   └── 정리 후 트리 통계 생성 및 비교
   ```

### 3.5 Discord 모드 (python main.py --mode discord)

1. **봇 초기화 단계**
   ```
   hsms_discord.py 실행
   ├── HSMSBot 클래스 인스턴스 생성
   ├── MainAI 인스턴스 생성
   ├── Discord 토큰으로 로그인
   └── 이벤트 리스너 등록
   ```

2. **메시지 처리 단계**
   ```
   Discord 메시지 수신
   ├── 봇 멘션 또는 DM 확인
   ├── MainAI.chat_async(message.content) 호출
   ├── AI 응답 받음
   └── Discord 채널에 응답 전송
   ```

3. **명령어 처리 단계**
   ```
   명령어 감지 (!hsms, !tree 등)
   ├── 명령어별 분기
   ├── 해당 기능 실행
   │   ├── !tree: 트리 구조 텍스트 생성
   │   └── !hsms: 일반 대화 처리
   └── 결과를 Discord로 전송
   ```

### 3.6 Search 모드 (python main.py --mode search)

1. **초기화 단계**
   ```
   main.py 실행
   ├── parse_arguments()
   ├── MemoryManager 인스턴스 생성 (읽기 전용)
   └── 무한 루프 시작
   ```

2. **검색 처리 단계**
   ```
   사용자 검색어 입력
   ├── MemoryManager.search_memory(query) 호출
   ├── 관련 노드들 점수순 정렬
   ├── 각 노드의 경로와 요약 추출
   └── 포맷된 검색 결과 출력
   ```

## 4. 핵심 알고리즘

### 4.1 AB 그룹핑 시스템
```
카테고리 수 > fanout_limit일 때:
├── 모든 카테고리 쌍의 유사도 계산
├── GROUP_SIMILARITY_FINE으로 AI 판단
├── 유사한 카테고리들을 그룹으로 묶음
└── 새로운 상위 그룹 노드 생성
```

### 4.2 동적 트리 구조 생성
```
새 대화 입력 시:
├── 깊이 제한 확인 (max_depth)
├── 기존 노드와 유사성 판단
├── 유사 노드 있으면: 기존 노드에 추가
├── 유사 노드 없으면: 새 노드 생성
└── 부모-자식 관계 설정
```

### 4.3 클러스터링 기반 트리 정리
```
TreeCleanupEngine:
├── 유사도 매트릭스 구축 (NODE_SIMILARITY_FINE)
├── 연결 요소 알고리즘으로 클러스터링
├── 각 클러스터를 새 그룹으로 묶음
└── 중복 노드 병합 및 리프 정리
```

### 4.4 병렬 AI 처리
```
call_ai_async_multiple():
├── 요청들을 LOAD_API_KEYS 수만큼 분할
├── 각 API 키로 병렬 처리
├── 실패한 요청은 재시도 큐에 추가
└── 모든 결과 수집 후 반환
```

## 5. 성능 최적화 요소

### 5.1 비동기 병렬 처리
- 최대 30개 API 키 동시 활용
- 순차 처리 대비 10-17배 성능 향상
- ResourceExhausted 예외 시 지수 백오프

### 5.2 Fine Tuning 시스템
- 일관된 AI 판단 기준 제공
- 예시 기반 학습으로 정확도 향상
- 각 기능별 특화된 Fine Tuning 데이터
- Gemini 1.5 Flash-001 서비스 중단으로 Few-Shot 방법 사용

### 5.3 효율적 메모리 관리
- 필요시에만 데이터 로드 (Lazy Loading)
- JSON 직렬화를 통한 효율적 저장
- 자동 백업 시스템으로 데이터 안전성 확보

### 5.4 트리 구조 최적화
- 클러스터링 기반 자동 정리
- 중복 제거 및 유사 노드 병합
- 44% 노드 수 감소 달성

## 6. 수정 필요사항
clean tree에서 카테고리 병합이 제대로 되지 않음.

병렬 작업(비동기)에서 디버그 메시지가 가독성이 좋지 않음.