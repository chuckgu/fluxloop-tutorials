# Customer Support LangGraph Conversion Plan

## 1. 목표
- `customer-support.ipynb` 노트북을 재사용 가능한 Python 예제로 전환한다.
- LangGraph 전용 구조로 리팩터링하면서 콘솔 기반 상호작용(승인/거부 흐름 포함)을 유지한다.
- `uv` 기반 가상환경과 표준 패키지 관리 방식을 도입해 의존성을 일관되게 관리한다.

## 2. 최종 산출물
- `src/` 이하에 배치되는 모듈형 Python 코드:
  - 공통 리소스(`db` 준비, 환경설정, 도구 정의)
  - 그래프 버전(Part 1 ~ Part 4)별 엔트리 모듈
  - 콘솔 실행용 스크립트(최종 Part 4 그래프 구동)
- `pyproject.toml` 및 `uv.lock`을 이용한 패키지 관리 구성
- README 혹은 사용 가이드(실행 방법, 인터럽트 승인 흐름, 예제 대화)

## 3. 작업 범위
1. **환경 정비**
   - `pyproject.toml` 작성 (`langgraph`, `langchain-community`, `langchain-anthropic`, `tavily-python`, `pandas`, `openai`, `sqlite-utils` 등 의존성 명시).
   - `uv` 명령을 이용한 가상환경 초기화 및 설치 스크립트 작성 (`uv sync`, `uv run` 안내).
2. **노트북 코드 모듈화**
   - 데이터베이스 다운로드·리셋 로직을 `db_utils.py` 등으로 분리.
   - 공통 도구 정의를 `tools/policies.py`, `tools/flights.py`, `tools/hotels.py` 등으로 세분화.
   - 공통 유틸리티(`handle_tool_error`, `_print_event`, `create_tool_node_with_fallback`)를 `utils.py`로 이동.
3. **LangGraph 그래프별 구현**
   - Part 1~3 그래프를 `graphs/part1.py` 등으로 분리하여 재현 가능하게 구성.
   - Part 4의 다중 에이전트 그래프를 `graphs/customer_support.py`로 구현하고, 콘솔 승인 흐름을 함수로 정의.
4. **콘솔 실행 진입점**
   - `python -m customer_support.main --demo part4` 형태로 그래프별 실행 지원.
   - 승인 대기 시 `input()`을 호출해 승인을 받고, 거절 시 사유 입력을 받아 그래프에 전달.
5. **문서화 및 예제 제공**
   - README에 실행 순서, API 키 설정 방법, 승인 흐름 설명, 샘플 Q&A를 기재.
   - 필요 시 `scripts/seed_db.py` 등의 편의 스크립트 제공.

## 4. 세부 일정(권장)
1. Day 1: 프로젝트 레이아웃/`uv` 환경/의존성 명세
2. Day 2: 데이터베이스 & 도구 모듈화
3. Day 3: Part 1~3 그래프 코드화
4. Day 4: Part 4 그래프 및 콘솔 승인 로직 구현
5. Day 5: README 및 사용 예시 작성, 테스트/검증

## 5. 기술 세부 고려사항
- **환경 변수 관리**: `dotenv` 사용 고려 또는 `os.environ` 기반 `prompt_for_env()` 유지.
- **데이터베이스**: 노트북의 `update_dates` 함수를 스크립트로 이동하고, 최초 실행 시 DB가 없으면 자동 다운로드하도록 구성.
- **승인 흐름**: `input()` 함수 호출을 별도 헬퍼로 감싸 테스트 가능하도록 설계.
- **로깅/디버깅**: `_print_event` 또는 표준 로깅을 선택적으로 활성화할 수 있도록 옵션화.
- **테스트 전략**: 그래프 핵심 노드(상태 전이, 도구 호출 분기)를 위한 단위 테스트 초안 마련.

## 6. 리스크 및 대응
- **API 키 미설정**: 실행 전 키 누락 시 콘솔 프롬프트(`ensure_env_vars`)로 입력받거나 `--skip-env` 사용 시 실패 메시지를 명확히 안내.
- **도구 예외 처리**: 기존 `create_tool_node_with_fallback`를 유지해 LLM 오류 시 사용자에게 명확히 전달.
- **의존성 충돌**: `pyproject`와 `uv.lock`을 커밋하여 환경 차이를 예방.

## 7. 완료 기준
- CLI에서 Part 4 그래프를 실행하고 튜토리얼 예제 시나리오를 재현할 수 있음.
- 승인 요청이 콘솔에서 정상적으로 동작하고, 승인/거절 흐름이 LangGraph 상태에 반영됨.
- README/문서에 설치·실행 방법이 명확히 기술되어 있음.
- 코드 구조가 노트북 대비 이해하기 쉬운 모듈 단위로 정리되어 있음.

