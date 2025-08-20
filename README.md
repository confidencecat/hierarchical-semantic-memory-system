# 계층적 의미 기억 시스템 (Hierarchical Semantic Memory System)

## 1. 개요

### 1.1 목적
AI 기반 대화형 시스템에서 장기 기억을 효율적으로 관리하고 검색할 수 있는 계층적 의미 기억 시스템이다. 기존의 선형적 기억 저장 방식의 한계를 극복하고, 의미적 연관성에 기반한 계층적 구조를 통해 더욱 효율적이고 맥락적인 기억 관리를 실현한다.

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

## 2. 파일별 상세 분석

### 2.1 main.py (메인 실행 파일)

#### 2.1.1 주요 함수
- **`parse_arguments()`**: 명령줄 인수를 파싱한다
  - `--mode`: 실행 모드 선택 (test/chat/discord/search)
  - `--api-info`: API 키 정보 표시
  - `--tree`: 트리 구조 도식화 표시
  - `--force-search`: 모든 대화에서 기억 검색 강제
  - `--force-record`: AI 응답 없이 정보만 기록
  - `--debug`: 디버그 모드 활성화
  - `--max-depth`: 트리 최대 깊이 설정 (기본값: 4)
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