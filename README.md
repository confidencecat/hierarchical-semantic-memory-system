# 계층적 의미 기억 시스템 (HSMS)

![logo](docs/logo.png)

**Hierarchical Semantic Memory System**

대화형 AI를 위한 계층적 의미 기억 시스템입니다. 사용자와의 대화를 의미적으로 분류하여 트리 구조로 저장하고, BFS(너비 우선 탐색) 알고리즘을 통해 효율적으로 관련 기억을 검색합니다.

## 주요 기능

- **계층적 메모리 구조**: 대화 내용을 의미별로 분류하여 트리 형태로 저장
- **AI 기반 유사도 판단**: Google Gemini API를 활용한 의미적 유사도 평가
- **BFS 기반 효율적 검색**: 너비 우선 탐색으로 최적화된 기억 탐색
- **동적 클러스터링**: 유사한 대화들을 자동으로 그룹화
- **병렬 AI 처리**: 여러 API 키를 활용한 동시 처리로 응답 속도 향상
- **실시간 설정 변경**: 대화 중에도 시스템 설정을 즉시 변경 가능
- **상세한 디버깅**: 시스템 동작 과정을 실시간으로 모니터링

## 요구사항

- Python 3.8 이상
- Google Gemini API 키 (최소 1개)
- 필수 패키지: `google-generativeai`, `python-dotenv`, `asyncio`, `uuid`, `argparse`

## 설치 및 설정

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
`.env` 파일을 생성하고 API 키를 설정합니다:
```env
# 메인 AI API 키 (필수)
AI_1=your_gemini_api_key_here

# 추가 로드 밸런싱용 API 키들 (선택사항)
LOAD_1=your_additional_api_key_1
LOAD_2=your_additional_api_key_2
LOAD_3=your_additional_api_key_3
```

### 4. 초기화
프로그램을 처음 실행하면 필요한 JSON 파일들이 자동으로 생성됩니다:
```bash
python hsms.py --mode test
```

## 사용법

### 기본 실행
```bash
# 대화 모드 실행 (기본)
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

**주요 옵션:**
- `--mode [test|chat]`: 실행 모드 설정 (기본값: chat)
- `--debug`: 디버그 모드 활성화
- `--debug-txt`: 디버그 정보를 텍스트 파일로 저장
- `--tree`: 현재 트리 구조 표시
- `--api-info`: 설정된 API 키 정보 표시
- `--search [efficiency|force|no]`: 검색 모드 설정
- `--fanout-limit [1-50]`: 노드당 최대 자식 수 설정
- `--model [MODEL_NAME]`: AI 모델 지정
- `--no-record`: 기록 저장 비활성화

**예시:**
```bash
# 디버그 모드로 대화 시작
python hsms.py --debug

# 트리 구조 확인
python hsms.py --tree

# API 키 정보 확인
python hsms.py --api-info

# 강제 검색 모드로 테스트 실행
python hsms.py --mode test --search force --debug
```

## 대화 모드 명령어

대화 중에 사용할 수 있는 실시간 명령어들:

- `!help` - 사용 가능한 명령어 목록 표시
- `!api-info` - API 키 정보 표시
- `!status` - 현재 시스템 설정 상태 표시
- `!search [efficiency|force|no]` - 검색 모드 변경
- `!debug` - 디버그 모드 토글
- `!debug-text` - 디버그 텍스트 파일 저장 모드 토글
- `!fanout-limit [1-50]` - 노드당 최대 자식 수 설정
- `!model [MODEL_NAME]` - AI 모델 변경
- `!record [ON|OFF]` - 기록 모드 변경
- `!update-topic [always|smart|never]` - 토픽 업데이트 정책 변경
- `!max-summary [100-1000]` - 요약 최대 길이 설정
- `!tree` - 트리 구조 표시
- `exit` - 프로그램 종료

**명령어 사용 예시:**
```
사용자: !debug
AI: 디버그 모드: ON

사용자: !search force
AI: 검색 모드가 'force'로 변경되었습니다.

사용자: !fanout-limit 10
AI: Fanout 제한이 10로 변경되었습니다.

사용자: !status
AI: === 시스템 상태 ===
검색 모드: force
기록 모드: ON
디버그 모드: ON
Fanout 제한: 10
AI 모델: gemini-2.5-flash
```

## 시스템 아키텍처

```
HSMS/
├── hsms.py              # 메인 진입점 및 명령행 인자 처리
├── main_ai.py           # 대화 모드 및 실시간 명령어 처리
├── ai_func.py           # AI 함수 모음 (유사도 판단, 요약, 클러스터링)
├── tree.py              # 계층적 트리 구조 관리 및 BFS 검색
├── memory.py            # JSON 파일 기반 데이터 저장 및 관리
├── config.py            # 환경 변수 로드 및 설정 관리
├── config.json          # 설정 파일 (런타임 설정 저장)
├── requirements.txt     # Python 패키지 의존성 목록
├── memory/              # 메모리 데이터 저장소
│   ├── all_memory.json      # 전체 대화 기록 저장
│   └── hierarchical_memory.json  # 계층적 메모리 트리 구조
└── docs/                # 프로젝트 문서
    ├── logo.png             # 프로젝트 로고
    └── 계층적 의미 기억 시스템 설계.md  # 설계 문서
```

## 주요 모듈 설명

### hsms.py
프로그램의 메인 진입점으로, 명령행 인자를 파싱하고 시스템을 초기화합니다. API 키 정보 표시, 트리 구조 시각화, 환경 검증 등의 기능을 제공합니다.

### main_ai.py
대화 모드의 핵심 처리 로직을 담당합니다. 실시간 명령어 시스템, 사용자 입력 처리, AI 응답 생성, 기억 검색 필요성 판단 등을 수행합니다.

### ai_func.py
Google Gemini AI API 호출 함수들을 제공합니다. 동기/비동기 AI 호출, 병렬 처리, 유사도 판단, 대화 요약, 주제 생성, 클러스터링 등의 기능을 수행합니다.

### tree.py
계층적 메모리 트리 구조를 관리하고 BFS 기반 효율적 검색 알고리즘을 구현합니다. 유사도 임계값 기반 노드 분류와 동적 클러스터링을 수행합니다.

### memory.py
JSON 파일 기반의 안전한 데이터 저장 시스템을 제공합니다. 원자적 파일 쓰기, 백업 및 복구, 데이터 구조 검증 및 초기화 기능을 포함합니다.

### config.py
환경 변수에서 API 키를 로드하고 시스템 설정을 관리합니다. 폴백 로직, 디버그 출력, 타임스탬프 유틸리티, API 호출 통계 관리 등의 기능을 제공합니다.

## 메모리 구조

메모리는 트리 구조로 저장되며, 각 노드는 다음 정보를 포함합니다:

```json
{
  "node_id": "uuid4-string",
  "topic": "노드 주제명",
  "summary": "노드 요약",
  "direct_parent_id": "부모 노드 ID",
  "all_parent_ids": ["부모 ID 목록"],
  "children_ids": ["자식 노드 ID 목록"],
  "all_memory_indexes": [1, 5, 12]
}
```

**트리 구조 예시:**
```
ROOT
├── 프로그래밍
│   ├── Python 기초 [5개 기억]
│   │   ├── 변수와 자료형 [3개 기억]
│   │   └── 제어문 [2개 기억]
│   └── 웹 개발 [4개 기억]
│       ├── Flask 프레임워크 [2개 기억]
│       └── REST API 설계 [2개 기억]
└── 일상 대화
    ├── 취미 활동 [6개 기억]
    └── 일정 관리 [3개 기억]
```

## 검색 알고리즘

### BFS 기반 계층적 검색
1. **루트 노드부터 시작**하여 레벨별로 탐색
2. **유사도 평가**: 각 노드와 현재 대화의 의미적 유사도 계산 (0.0-1.0)
3. **임계값 기반 분기**:
   - `SIMILARITY_THRESHOLD` (0.7): 유사도가 높으면 해당 노드에 추가
   - `EXPLORATION_THRESHOLD` (0.5): 중간 유사도면 하위 노드 계속 탐색
   - 0.5 미만: 해당 브랜치 탐색 중단
4. **클러스터링**: 유사한 노드들을 그룹화하여 새로운 부모 노드 생성

### 검색 모드
- `efficiency`: 기본 모드, 임계값 기반 최적화된 검색
- `force`: 모든 노드 탐색 (정확도 우선)
- `no`: 기억 검색 생략 (현재 대화만으로 응답)

## 설정 파라미터

| 파라미터 | 기본값 | 설명 |
|---------|--------|------|
| `FANOUT_LIMIT` | 5 | 노드당 최대 자식 수 |
| `SIMILARITY_THRESHOLD` | 0.7 | 노드 추가를 위한 최소 유사도 |
| `EXPLORATION_THRESHOLD` | 0.5 | 하위 탐색을 위한 최소 유사도 |
| `MAX_SUMMARY_LENGTH` | 1000 | 노드 요약 최대 길이 |
| `MAX_SEARCH_DEPTH` | 10 | BFS 최대 탐색 깊이 |
| `UPDATE_TOPIC` | "smart" | 토픽 업데이트 정책 |
| `SEARCH_MODE` | "efficiency" | 검색 모드 |
| `GEMINI_MODEL` | "gemini-2.5-flash" | 사용할 AI 모델 |
| `NO_RECORD` | false | 기록 비활성화 모드 |
| `DEBUG` | false | 디버그 모드 |
| `DEBUG_TXT` | false | 디버그 텍스트 파일 저장 모드 |

## 디버그 모드

디버그 모드를 활성화하면 다음 정보를 실시간으로 확인할 수 있습니다:

- AI API 호출 시간 및 응답 길이
- 유사도 점수 분포 (평균, 최대, 최소)
- 트리 구조 변경 과정
- 메모리 검색 결과 및 경로
- 클러스터링 과정 상세 정보
- API 호출 통계 및 응답 시간
- 메모리 사용량 및 검색 효율성
- 노드 생성 및 업데이트 로그

**디버그 출력 예시:**
```
[DEBUG] 대화 처리 시작: 안녕하세요, Python에 대해 알고 싶습니다...
[DEBUG] 기억 검색 시작...
[DEBUG] BFS 검색 시작 (초기 노드: 3개)
[DEBUG] 깊이 1 탐색 중 (3개 노드)
[DEBUG] 기억 발견: 노드 a1b2c3d4... (5개 대화)
[DEBUG] BFS 검색 완료 (발견된 기억: 5개)
[DEBUG] 응답 생성 시작...
[DEBUG] 응답 생성 완료
[DEBUG] 기억 저장 시작...
[DEBUG] 기억 저장 완료
```

**디버그 텍스트 파일 저장:**
`!debug-text` 명령어로 디버그 정보를 텍스트 파일로 저장할 수 있습니다:
- 파일명: `debug_YYYYMMDD_HHMMSS.txt`
- 모든 디버그 출력이 파일에 자동 저장
- 세션 종료 시 자동으로 파일 닫기

## 성능 특징

- **병렬 AI 처리**: 최대 100개의 API 키 로테이션 지원
- **지능적 캐싱**: 계산된 유사도 결과를 재사용
- **메모리 최적화**: 계층적 구조로 검색 공간 대폭 축소
- **확장성**: Rate Limit 자동 대응 및 로드 밸런싱
- **안전성**: 원자적 파일 쓰기 및 자동 백업

## 문제 해결

### 일반적인 문제들

**1. API 키 설정 오류**
```bash
# .env 파일 확인
cat .env

# 올바른 형식 확인
AI_1=your_api_key_here
LOAD_1=your_additional_key
```

**2. 메모리 파일 권한 오류**
```bash
# memory 폴더 생성 및 권한 설정
mkdir -p memory
chmod 755 memory
```

**3. API 호출 제한 초과**
- 추가 API 키를 LOAD 환경 변수로 설정
- 프로그램 재시작으로 Rate Limit 리셋 대기

**4. 디버그 모드 작동 안 함**
```bash
# 명령행에서 디버그 모드 활성화
python hsms.py --debug

# 또는 대화에서 명령어 사용
!debug
```

**5. config.json 파일 손상**
```bash
# config.json 파일 삭제 후 재생성
rm config.json
python hsms.py --mode test
```

### 시스템 상태 확인
```bash
# 트리 구조 확인
python hsms.py --tree

# API 키 정보 확인
python hsms.py --api-info

# 시스템 전체 상태 확인
python hsms.py --mode test --debug
```

## 업데이트 및 마이그레이션

### 버전 업데이트 시 주의사항
1. **config.json 백업**: 설정 변경사항 보존
2. **memory/ 폴더 백업**: 기존 대화 기록 보존
3. **API 키 재설정**: .env 파일 확인
4. **의존성 업데이트**: `pip install -r requirements.txt --upgrade`

### 데이터 마이그레이션
```bash
# 메모리 데이터 백업
cp -r memory/ memory_backup/

# 설정 파일 백업
cp config.json config_backup.json

# 업데이트 후 데이터 검증
python -c "from memory import initialize_json_files; initialize_json_files()"
```

## 라이센스

이 프로젝트는 MIT 라이센스 하에 공개되어 있습니다.

## 기여하기

프로젝트에 기여를 환영합니다:

1. **Issues 제보**: 버그 발견 시 GitHub Issues에 제보
2. **Feature 제안**: 새로운 기능 아이디어 제안
3. **Pull Request**: 코드 개선사항 제출
4. **문서화**: README, 주석, 예제 개선

### 개발 환경 설정
```bash
# 개발용 저장소 클론
git clone https://github.com/confidencecat/hierarchical-semantic-memory-system.git
cd hierarchical-semantic-memory-system

# 개발 브랜치 생성
git checkout -b feature/your-feature-name

# 의존성 설치
pip install -r requirements.txt

# 테스트 실행
python hsms.py --mode test --debug
```