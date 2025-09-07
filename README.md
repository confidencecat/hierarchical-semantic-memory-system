# 계층적 의미 기억 시스템 (HSMS)

![logo](docs/logo.png)

**Hierarchical Semantic Memory System**
대화형 AI 시스템을 위한 계층적 의미 기억 시스템으로, 사용자의 대화를 의미적으로 분류하여 트리 구조로 저장하고 BFS 기반 탐색을 통해 효율적인 기억 검색을 제공합니다.


## 🚀 주요 기능

- **계층적 메모리 구조**: 대화를 의미적으로 분류하여 트리 형태로 저장
- **AI 기반 유사도 판단**: Google Gemini AI를 활용한 의미적 유사도 평가 (0.0-1.0 스코어)
- **BFS 기반 효율적 검색**: Breadth-First Search 알고리즘으로 최적화된 기억 탐색
- **동적 클러스터링**: 메모리 구조의 자동 최적화를 통한 성능 향상
- **병렬 AI 처리**: 여러 API 키를 활용한 동시 AI 호출로 응답 시간 단축
- **실시간 디버깅**: 상세한 디버그 정보로 시스템 동작 모니터링
- **안전한 데이터 저장**: JSON 파일 기반의 백업 및 복구 기능

## 📋 요구사항

- Python 3.8 이상
- Google Gemini API 키 (1개 이상)
- 필수 패키지: `google-generativeai`, `python-dotenv`

## 🛠️ 설치 및 설정

### 1. 저장소 클론
```bash
git clone https://github.com/confidencecat/hierarchical-semantic-memory-system.git
cd hierarchical-semantic-memory-system
```

### 2. 의존성 설치
```bash
pip install -r requirements.txt
```

### 3. 환경 변수 설정
`.env` 파일을 생성하고 Google Gemini API 키를 설정하세요:
```env
# 메인 AI API 키 (필수)
AI_1=your_gemini_api_key_here

# 추가 로드 밸런싱용 API 키들 (선택사항, 최대 100개)
LOAD_1=your_additional_api_key_1
LOAD_2=your_additional_api_key_2
LOAD_3=your_additional_api_key_3
```

> **중요**: API 키는 `AI_1`, `LOAD_1`, `LOAD_2` 등의 형식으로 설정해야 합니다.

### 4. 초기화
프로그램을 처음 실행하면 자동으로 필요한 JSON 파일들이 생성됩니다:
```bash
python hsms.py --mode test
```

## 🎯 사용법

### 기본 실행
```bash
# 채팅 모드 실행 (기본)
python hsms.py

# 테스트 모드 실행
python hsms.py --mode test

# 디버그 모드 실행
python hsms.py --debug
```

### 명령행 옵션
```bash
python hsms.py [옵션들]
```

#### 주요 옵션
- `--mode`: 실행 모드 (`chat` 또는 `test`, 기본값: `chat`)
- `--debug`: 디버그 모드 활성화 (기본값: `false`)
- `--tree`: 트리 구조 시각화 및 출력
- `--api-info`: 설정된 API 키 정보 표시 (마스킹 처리)

#### 예시
```bash
# 디버그 모드로 채팅 시작
python hsms.py --debug

# 트리 구조 확인
python hsms.py --tree

# API 키 정보 확인
python hsms.py --api-info

# 테스트 모드 실행
python hsms.py --mode test --debug
```

## 💬 대화 모드 명령어

채팅 모드에서 사용할 수 있는 실시간 명령어들:

- `!help` - 사용 가능한 명령어 목록 표시
- `!debug` - 디버그 모드 토글 (켜기/끄기)
- `!search [mode]` - 검색 모드 변경 (`efficiency`/`force`/`no`)
- `!fanout-limit [num]` - 노드당 최대 자식 수 설정 (기본값: 5)
- `!status` - 현재 시스템 설정 상태 표시
- `exit` - 프로그램 종료

### 명령어 사용 예시
```
사용자: !debug
AI: 디버그 모드가 활성화되었습니다.

사용자: !search efficiency
AI: 검색 모드가 'efficiency'로 변경되었습니다.

사용자: !fanout-limit 3
AI: 팬아웃 제한이 3으로 설정되었습니다.

사용자: !status
AI: 현재 설정 상태:
   - 디버그 모드: 활성화
   - 검색 모드: efficiency
   - 팬아웃 제한: 3
```

## 🏗️ 시스템 아키텍처

```
HSMS/
├── hsms.py              # 메인 진입점 및 명령행 인자 처리
├── main_ai.py           # 채팅 모드 및 실시간 명령어 처리
├── ai_func.py           # AI 함수 모음 (유사도 판단, 요약, 클러스터링)
├── tree.py              # 계층적 트리 구조 관리 및 BFS 검색
├── memory.py            # JSON 파일 기반 데이터 저장 및 관리
├── config.py            # 환경 변수 로드 및 설정 관리
├── memory/              # 메모리 데이터 저장소
│   ├── all_memory.json      # 전체 대화 기록 저장
│   └── hierarchical_memory.json  # 계층적 메모리 트리 구조
└── docs/                # 프로젝트 문서
```

## 🔧 주요 모듈 설명

### hsms.py
- 프로그램의 메인 진입점
- 명령행 인자 파싱 (`--mode`, `--debug`, `--tree`, `--api-info`)
- 시스템 초기화 및 모드별 실행 분기
- API 키 정보 표시 기능 (마스킹 처리)

### main_ai.py
- 채팅 모드의 메인 처리 로직
- 실시간 명령어 시스템 (`!debug`, `!search`, `!fanout-limit` 등)
- 사용자 입력 처리 및 AI 응답 생성
- 기억 검색 필요성 판단 및 메모리 조회

### ai_func.py
- Google Gemini AI API 호출 함수들
- `AI()`: 동기적 단일 AI 호출
- `ASYNC_AI()`: 비동기적 단일 AI 호출
- `ASYNC_MULTI_AI()`: 병렬 AI 호출 (로드 밸런싱 지원)
- 유사도 판단, 대화 요약, 주제 생성, 클러스터링 AI 함수들

### tree.py
- 계층적 메모리 트리 구조 관리
- BFS 기반 효율적 검색 알고리즘 구현
- 유사도 임계값 기반 노드 분류 및 클러스터링
- 트리 구조 시각화 기능

### memory.py
- JSON 파일 기반 안전한 데이터 저장
- 원자적 파일 쓰기 (임시 파일 + 이동)
- 백업 및 복구 기능
- 데이터 구조 검증 및 초기화

### config.py
- 환경 변수에서 API 키 로드 (`AI_1`, `LOAD_1` 등)
- 디버그 출력 및 타임스탬프 유틸리티
- 설정 값 관리

## 📊 메모리 구조

메모리는 트리 구조로 저장되며, 각 노드는 다음 정보를 포함합니다:

```json
{
  "node_id": "uuid4-string",
  "topic": "노드 주제명",
  "summary": "노드 요약",
  "direct_parent_id": "부모 노드 ID",
  "all_parent_ids": ["부모 ID 목록"],
  "children_ids": ["자식 노드 ID 목록"],
  "all_memory_indexes": [1, 5, 12]  // 관련 대화 인덱스
}
```

### 트리 구조 예시
```
ROOT
├── 프로그래밍
│   ├── Python 기초
│   │   ├── 변수와 자료형
│   │   └── 제어문
│   └── 웹 개발
│       ├── Flask 프레임워크
│       └── REST API 설계
└── 일상 대화
    ├── 취미 활동
    └── 일정 관리
```

## 🔍 검색 알고리즘

### BFS 기반 계층적 검색
1. **루트 노드부터 시작**하여 레벨별 탐색
2. **유사도 평가**: 각 노드와 현재 대화의 의미적 유사도 계산 (0.0-1.0)
3. **임계값 기반 분기**:
   - `SIMILARITY_THRESHOLD` (0.7): 유사도가 높으면 해당 노드에 추가
   - `EXPLORATION_THRESHOLD` (0.5): 중간 유사도면 하위 노드 탐색 계속
   - 0.5 미만: 해당 브랜치 탐색 중단
4. **클러스터링**: 유사한 노드들을 그룹화하여 새로운 부모 노드 생성

### 검색 모드
- `efficiency`: 기본 모드, 임계값 기반 최적화된 검색
- `force`: 모든 노드 탐색 (정확도 우선)
- `no`: 기억 검색 생략 (현재 대화만으로 응답)

## ⚙️ 설정 파라미터

| 파라미터 | 기본값 | 설명 |
|---------|--------|------|
| `FANOUT_LIMIT` | 5 | 노드당 최대 자식 수 |
| `SIMILARITY_THRESHOLD` | 0.7 | 노드 추가를 위한 최소 유사도 |
| `EXPLORATION_THRESHOLD` | 0.5 | 하위 탐색를 위한 최소 유사도 |
| `MAX_SUMMARY_LENGTH` | 300 | 노드 요약 최대 길이 |
| `MAX_SEARCH_DEPTH` | 10 | BFS 최대 탐색 깊이 |

## 🚦 디버그 모드

디버그 모드를 활성화하면 다음 정보를 실시간으로 확인할 수 있습니다:

- AI API 호출 시간 및 응답 길이
- 유사도 점수 분포 (평균, 최대, 최소)
- 트리 구조 변경 과정
- 메모리 검색 결과 및 경로
- 클러스터링 과정 상세 정보
- API 호출 통계 (총 호출 수, 병렬 처리 수, 에러 수)

### 디버그 출력 예시
```
[DEBUG] 기억 필요성 판단 중...
[DEBUG] 기억 필요성 판단 결과: true
[DEBUG] 유사도 비교 완료 - 평균: 0.65, 최고: 0.82 (12개 노드)
[DEBUG] AI 호출 완료 (응답 길이: 245자, 소요시간: 1.23초)
```

## 📈 성능 특징

- **병렬 AI 처리**: 최대 100개의 API 키 로테이션 지원
- **지능적 캐싱**: 계산된 유사도 결과를 재사용
- **메모리 최적화**: 계층적 구조로 검색 공간 70% 이상 축소
- **확장성**: Rate Limit 자동 대응 및 로드 밸런싱
- **안전성**: 원자적 파일 쓰기 및 자동 백업

## 🐛 문제 해결

### 일반적인 문제들

1. **API 키 설정 오류**
   ```bash
   # .env 파일 확인
   cat .env
   
   # 올바른 형식 확인
   AI_1=your_api_key_here
   LOAD_1=your_additional_key
   ```

2. **메모리 파일 권한 오류**
   ```bash
   # memory 폴더 생성 및 권한 설정
   mkdir -p memory
   chmod 755 memory
   ```

3. **API 호출 제한 초과**
   - 추가 API 키를 LOAD 환경 변수로 설정
   - 프로그램 재시작으로 Rate Limit 리셋 대기

4. **디버그 모드 작동 안 함**
   ```bash
   # 명령행에서 디버그 모드 활성화
   python hsms.py --debug
   
   # 또는 채팅에서 명령어 사용
   !debug
   ```

### 시스템 상태 확인
```bash
# 트리 구조 확인
python hsms.py --tree

# API 키 정보 확인
python hsms.py --api-info

# 메모리 파일 무결성 검증
python -c "from memory import validate_data_structure; print(validate_data_structure())"
```

