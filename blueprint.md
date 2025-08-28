# HSMS (Hierarchical Semantic Memory System) 상세 설계도 v2.0

이 문서는 HSMS의 아키텍처, 데이터 흐름, 핵심 알고리즘, 그리고 각 모듈의 구체적인 역할과 구현에 대해 기술한다. 이 설계도는 시스템의 복제 및 확장을 위한 기술적 지침을 제공하는 것을 목표로 한다.

---

## 1. 시스템 아키텍처 (System Architecture)

HSMS는 5개의 핵심 컴포넌트가 유기적으로 상호작용하는 구조로 설계되었다.

- **`MemoryNode`**: 데이터의 기본 단위. 모든 정보 조각을 표현하는 데이터 클래스.
- **`DataManager`**: 데이터의 영속성(Persistence)을 담당. 메모리 트리 구조를 JSON 파일로 저장하고 불러온다.
- **`AIManager`**: 외부 AI 모델(Google Gemini)과의 통신을 전담. 텍스트 임베딩, 요약, 유사도 계산 등 지능적 연산을 수행한다.
- **`MemoryManager`**: 인메모리(In-memory) 트리 구조를 관리. 노드의 추가, 검색, 삭제 등 메모리의 핵심 CRUD(Create, Read, Update, Delete) 연산을 담당한다.
- **`TreeCleanupEngine`**: 트리의 구조적 효율성과 의미적 일관성을 유지하기 위한 백그라운드 프로세스. 주기적으로 트리를 순회하며 재클러스터링 및 요약을 수행한다.

### 1.1. 컴포넌트 상호작용
```
+------------------+      +------------------+      +----------------------+
|   User/Client    |----->|   main.py /      |----->|    MemoryManager     |
| (Input/Query)    |      | hsms_discord.py  |      | (Core Logic)         |
+------------------+      +------------------+      +----------+-----------+
                                                         ^      |
                                                         |      |
                                                         |      v
                                                +--------+-----------+
                                                |     AIManager      |
                                                | (AI Operations)    |
                                                +--------------------+
                                                         ^      |
                                                         |      |
                                                         |      v
                                                +--------+-----------+
                                                |     DataManager    |
                                                | (Data Persistence) |
                                                +--------------------+
                                                         ^      |
                                                         |      |
                                                         |      v
                                                +--------------------+
                                                | hierarchical_...json|
                                                +--------------------+
```
- **데이터 흐름 (쓰기)**: `Client` -> `MemoryManager.add_memory()` -> `AIManager.get_embedding/get_summary()` -> `MemoryManager`가 트리 위치 결정 및 노드 추가 -> `DataManager.save_memory()`
- **데이터 흐름 (읽기)**: `Client` -> `MemoryManager.search()` -> `AIManager.get_embedding()` -> `MemoryManager`가 트리 탐색 -> 결과 반환

---

## 2. 데이터 모델 (Data Model)

### 2.1. `MemoryNode` (HSMS/MemoryNode.py)
메모리의 최소 단위.

- **속성 (Attributes):**
  - `id: str`: UUID로 생성된 노드의 고유 식별자.
  - `content: str`: 사용자가 입력한 원본 텍스트. 리프 노드에만 존재.
  - `summary: str`: `content`의 요약본. 중간 노드의 경우, 자식 노드들의 `summary`를 종합하여 생성된 요약.
  - `embedding: list[float]`: `summary`를 기반으로 생성된 텍스트 임베딩 벡터.
  - `parent_id: str | None`: 부모 노드의 `id`. `root` 노드는 `None`.
  - `children_ids: list[str]`: 자식 노드들의 `id` 리스트.
  - `timestamp: float`: 생성 또는 마지막 수정 시각.

---

## 3. 핵심 컴포넌트 상세 구현

### 3.1. `DataManager` (HSMS/DataManager.py)
- **역할**: 메모리 구조의 파일 입출력 담당.
- **주요 메서드:**
  - `__init__(self, file_path: str)`: 메모리 덤프 파일의 경로를 초기화.
  - `save_memory(self, memory_data: dict)`: `MemoryManager`로부터 받은 메모리 딕셔너리(`{node_id: MemoryNode}`)를 JSON 형식으로 파일에 저장.
  - `load_memory(self) -> dict`: JSON 파일을 읽어 메모리 딕셔너리를 재구성하여 반환. 파일이 없으면 초기 `root` 노드만 있는 딕셔너리를 생성.

### 3.2. `AIManager` (HSMS/AIManager.py)
- **역할**: Google Gemini API와의 모든 상호작용을 캡슐화.
- **주요 메서드:**
  - `__init__(self, api_key: str)`: API 키를 사용하여 Gemini 클라이언트 초기화.
  - `get_embedding(self, text: str) -> list[float]`: 주어진 텍스트에 대한 임베딩 벡터를 생성. `models/text-embedding-004` 모델 사용.
  - `get_summary(self, text: str, context: str = None) -> str`: 주어진 텍스트를 요약. `context`가 주어지면 요약의 방향을 제어.
  - `calculate_similarity(self, vec1: list[float], vec2: list[float]) -> float`: 두 임베딩 벡터 간의 코사인 유사도를 계산. (numpy 사용)

### 3.3. `MemoryManager` (HSMS/MemoryManager.py)
- **역할**: 메모리 트리의 핵심 로직. 노드 관리 및 검색 수행.
- **주요 속성:**
  - `nodes: dict[str, MemoryNode]`: 모든 `MemoryNode` 객체를 `id`를 키로 하여 저장하는 딕셔너리.
  - `root_id: str`: 트리의 시작점인 `root` 노드의 `id`.
- **주요 메서드:**
  - `add_memory(self, content: str)`:
    1. `AIManager`를 호출하여 `content`의 `summary`와 `embedding`을 얻는다.
    2. `_find_most_similar_node_path(embedding)`를 호출하여 새 노드를 추가할 최적의 부모 노드를 찾는다.
    3. 새 `MemoryNode`를 생성하고 `nodes` 딕셔너리에 추가한다.
    4. 찾은 부모 노드의 `children_ids`에 새 노드의 `id`를 추가한다.
    5. `DataManager`를 통해 변경사항을 파일에 저장한다.
  - `search(self, query: str, top_k: int = 5) -> list[MemoryNode]`:
    1. `AIManager`를 호출하여 `query`의 `embedding`을 얻는다.
    2. `_find_most_similar_node_path(embedding)`를 호출하여 가장 관련성 높은 노드까지의 경로를 찾는다.
    3. 최종적으로 도달한 노드와 그 형제 노드(siblings)들을 후보군으로 선정한다.
    4. 후보군과 쿼리 간의 유사도를 다시 계산하여 가장 높은 `top_k`개의 노드를 반환한다.
  - `_find_most_similar_node_path(self, target_embedding: list[float]) -> list[MemoryNode]`:
    1. `root` 노드에서 시작. 경로 리스트에 `root`를 추가.
    2. 현재 노드의 자식들이 없으면 탐색을 종료하고 현재까지의 경로를 반환.
    3. 현재 노드의 모든 자식 노드들의 `embedding`과 `target_embedding` 간의 코사인 유사도를 계산.
    4. 가장 높은 유사도를 가진 자식 노드를 다음 탐색 노드로 선택하고 경로 리스트에 추가.
    5. 2번으로 돌아가 과정을 반복 (재귀적 하강).

---

## 4. 트리 구조 최적화 (Tree Cleanup)

### 4.1. `TreeCleanupEngine` (HSMS/TreeCleanupEngine.py)
- **역할**: 트리의 비대칭 성장 및 의미적 중복을 해결하여 검색 효율성을 유지.
- **트리거**: 주기적 실행 (예: 매 100회 쓰기 연산 후 또는 하루에 한 번).
- **핵심 알고리즘**:
  1. **대상 선정**: 특정 깊이(depth) 이상이고, 특정 개수 이상의 자식을 가진 노드를 스캔 대상으로 선정.
  2. **자식 그룹 클러스터링**:
     - 대상 노드의 모든 자식 노드들의 임베딩 벡터를 수집.
     - `sklearn.cluster.AgglomerativeClustering`과 같은 계층적 군집화 알고리즘을 사용하여 자식 노드들을 의미적으로 유사한 그룹으로 나눈다.
     - `distance_threshold`를 사용하여 클러스터의 개수를 동적으로 결정.
  3. **중간 노드 생성 및 재구성**:
     - 각 클러스터에 대해:
       a. 클러스터에 속한 모든 자식 노드들의 `summary`를 하나로 합친다.
       b. `AIManager.get_summary()`를 호출하여 합쳐진 텍스트에 대한 새로운 상위 요약(super-summary)을 생성한다.
       c. 이 요약을 기반으로 새로운 임베딩을 생성하여 **새로운 중간 노드**를 만든다.
       d. 기존 부모 노드와 클러스터 멤버 노드 간의 연결을 끊는다.
       e. 새로운 중간 노드를 기존 부모 노드의 자식으로 연결한다.
       f. 클러스터에 속했던 멤버 노드들을 모두 새로운 중간 노드의 자식으로 연결한다.
  4. **변경사항 저장**: 재구성된 트리 구조를 `DataManager`를 통해 저장.

- **기대 효과**:
  - **탐색 경로 최적화**: 관련 정보들이 명확한 중간 노드 아래로 묶여, 탐색 시 불필요한 분기(branch)를 줄인다.
  - **의미적 계층성 강화**: "고양이 사진", "고양이 울음소리" -> "고양이 관련 정보" 와 같은 자연스러운 의미 계층이 형성된다.

---

## 5. 유사도 판단 AI 파인튜닝 (상세 가이드)

현재 시스템은 범용 `text-embedding-004` 모델을 사용하지만, 특정 도메인(예: 의료, 법률, 개인 일기)에 특화된 성능을 위해 파인튜닝이 필요할 수 있다.

- **1. 데이터셋 구축 (Triplet-based)**:
  - **형태**: `(Anchor, Positive, Negative)` 튜플 수집.
  - **수집 방법**:
    - 시스템 사용 로그 분석: 사용자가 특정 쿼리(`Anchor`)를 입력했을 때 최종적으로 선택하거나 만족한 결과(`Positive`)와, 관련 없어 보였던 다른 검색 결과(`Negative`)를 기록.
    - 수동 레이블링: 특정 주제(`Anchor`)에 대해, 전문가가 관련 있는 문서(`Positive`)와 관련 없는 문서(`Negative`)를 직접 쌍으로 만든다.
  - **예시 (개인 일기 도메인)**:
    - `Anchor`: "작년 여름 휴가 때 갔던 바다"
    - `Positive`: "해변에서 친구들과 수영하며 즐거운 시간을 보냈다."
    - `Negative`: "겨울에 스키장에 가서 눈썰매를 탔다."

- **2. 모델 학습 (Sentence-BERT 기반)**:
  - **기반 모델**: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` 와 같이 가볍고 성능 좋은 다국어 모델로 시작.
  - **Loss 함수**: `TripletLoss`
    - `loss = max(0, distance(anchor, positive) - distance(anchor, negative) + margin)`
    - 이 손실 함수는 `anchor-positive` 간 거리를 최소화하고, `anchor-negative` 간 거리를 최대화하도록 모델의 가중치를 업데이트한다. `margin`은 두 거리 간의 최소한의 차이를 강제하는 하이퍼파라미터.
  - **학습 과정**: 준비된 Triplet 데이터셋을 사용하여 모델을 학습. 수만 건 이상의 데이터가 필요할 수 있다.

- **3. 시스템 통합**:
  - `AIManager`의 `get_embedding` 메서드가 파인튜닝된 모델을 사용하도록 교체. 모델은 로컬에 저장하거나 Hugging Face Hub에 업로드하여 로드할 수 있다.

---
## 6. 설정 (Configuration)

- **`config.py`**: 시스템의 모든 주요 설정을 관리.
  - `API_KEY`: Google Gemini API 키.
  - `MEMORY_FILE_PATH`: 메모리 JSON 파일의 경로.
  - `EMBEDDING_MODEL`: 사용할 임베딩 모델 이름.
  - `SUMMARY_MODEL`: 사용할 요약 생성 모델 이름.
  - `CLEANUP_THRESHOLD`: 트리 재정렬을 트리거하는 노드 수 또는 작업 횟수.
  - `SIMILARITY_THRESHOLD`: 노드를 동일 클러스터로 묶기 위한 최소 유사도 임계값.