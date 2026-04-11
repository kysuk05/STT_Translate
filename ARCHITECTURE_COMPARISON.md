# 기존 구조 vs 재구현(app_v2) 비교

## 비교 목적
`DETAILED_SOFTWARE_DESIGN.md`를 기준으로 재구현한 `app_v2`가 기존 `app` 대비 어떤 점이 달라졌는지,
개발자 생산성/가독성/유지보수성 관점에서 비교합니다.

## 1) 디렉터리 구조

### 기존
- `app/main.py`에 요청 처리, 업로드 검증, 파일 저장, STT/번역 제어가 집중
- `stt`, `translate`, `utils` 모듈은 있으나 endpoint orchestration 책임이 큼

### 신규(`app_v2`)
- `core`: 설정/공통 에러 타입
- `services`: 업로드 가드, STT, 번역, 파이프라인 오케스트레이션
- `api`: 라우트 + 응답 스키마
- `main.py`: 앱 조립(composition root)

**효과**: 읽는 경로가 “API -> pipeline -> service”로 정형화되어 신규 개발자 온보딩이 쉬워짐.

## 2) 예외 처리 방식

### 기존
- `HTTPException`을 endpoint 내부에서 직접 다수 발생
- 모델 내부 에러는 일부 로깅만 존재
- 에러 응답 포맷이 성공 응답과 분리 설계되지 않음

### 신규
- `AppError(error_code, message, status_code, detail)` 표준 도입
- 서비스는 `AppError` 중심으로 실패를 표현
- API 라우터가 표준 오류 스키마(`ErrorResponse`)로 변환

**효과**: 에러 코드 체계가 일관돼 프론트/운영 대응이 쉬움.

## 3) 정책값 관리

### 기존
- 정책값이 `app/config.py`에 존재하지만 API 레이어 로직과 강결합

### 신규
- `app_v2/core/config.py`의 `Settings` dataclass에서 정책값 관리
- 환경변수 override를 고려한 구조

**효과**: 운영 환경별 정책 튜닝이 간단해짐.

## 4) 가독성/유지보수성

### 기존
- 단일 파일(`app/main.py`)에서 많은 책임을 처리

### 신규
- 함수/클래스 단위 책임 분리
  - `upload_guard`: 파일 검증/저장/정리
  - `pipeline_service`: 유스케이스 흐름
  - `stt_service`, `translation_service`: 모델 처리

**효과**: 테스트 포인트가 모듈별로 분리되고, 변경 영향 범위를 예측하기 쉬움.

## 5) 동일점(행동 호환성)
- 기본 endpoint: `POST /voice-to-prompt`
- 흐름: 업로드 -> STT -> 언어감지 -> 번역 -> 응답
- timeout/용량 제한/임시파일 정리의 핵심 동작 유지

## 6) 차이점(주의)
- 신규는 오류 응답이 표준 JSON(`error_code`, `message`, `detail`)로 반환됨
- 신규 실행 포트 기본값은 `run_v2.sh` 기준 `8010`
- 번역 정책(`lang=None` 시 `src="auto"`)은 기존 동작과 동일하게 유지했으나, 이는 후속 개선 후보

## 7) 개발자에게 유리한 지점
- 책임 분리로 코드 리뷰 범위 축소
- 정책/에러/라우트가 독립돼 변경 난이도 감소
- 구조화된 오류로 디버깅 커뮤니케이션 비용 감소

## 8) 다음 리팩터 권장
- `lang=None` 경로의 모델 입력 정책 명확화(`auto` vs 실제 추정값)
- thread-timeout 한계 보완(프로세스 격리 또는 큐)
- ffprobe/매직넘버 기반 파일 검증 강화
- 테스트 코드(`tests/`) 추가

