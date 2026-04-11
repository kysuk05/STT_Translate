# STT Translate GPU 상세 설계서 (v1)

## 1. 문서 목적
본 문서는 현재 프로젝트를 재구현 가능한 수준으로 구체화한 소프트웨어 상세 설계서입니다.  
목표는 다음 3가지입니다.

- 기능 요구사항(`REQUIREMENTS.md`)을 코드 수준 구조로 연결
- 예외/보안/성능 요구(`ERROR_HANDLING_DESIGN.md`)를 레이어별 책임으로 분리
- 개발자가 빠르게 이해하고 확장할 수 있는 가독성 높은 구조 제시

## 2. 설계 원칙

### 2.1 계층 분리
- **API 레이어**: 요청/응답 계약, HTTP 상태코드 결정
- **서비스 레이어**: 업로드 검증, STT, 번역 흐름 오케스트레이션
- **인프라 레이어**: 모델 라이브러리 호출, 파일 I/O
- **설정 레이어**: 실행 정책(용량, timeout, 허용 포맷) 중앙 관리

### 2.2 실패 우선(Fail-fast)
- 잘못된 입력은 모델 호출 전 차단
- 용량 초과는 저장 도중 즉시 중단
- 타임아웃은 단계별(STT/번역)로 분리해 원인 명확화

### 2.3 관측가능성 우선
- 에러는 클라이언트에는 안전한 메시지, 서버에는 상세 로그
- 단계별 예외 유형을 HTTP 코드로 명시적 매핑

### 2.4 확장 친화성
- 모델 선택 정책, 업로드 정책, 에러 정책을 독립 모듈화
- 추후 큐 기반 처리/프로세스 격리 도입 가능한 형태 유지

## 3. 시스템 컨텍스트

### 3.1 핵심 유스케이스
1. 사용자가 오디오 파일 업로드
2. 서버가 파일 검증 및 저장
3. STT 수행
4. 언어 감지
5. 영어 번역 및 품질 폴백
6. 결과 반환 + 임시파일 정리

### 3.2 비유스케이스(현 범위 제외)
- 인증/인가
- 장기 저장소(DB/S3) 저장
- 비동기 작업 큐(예: Celery)
- 멀티 테넌시

## 4. API 계약 설계

### 4.1 Endpoint
- `POST /voice-to-prompt`
- Content-Type: `multipart/form-data`
- 필수 필드: `file`

### 4.2 성공 응답(200)
```json
{
  "detected_lang": "ko",
  "stt_text": "안녕하세요",
  "prompt_en": "Hello"
}
```

### 4.3 실패 응답 표준
```json
{
  "error_code": "FILE_TOO_LARGE",
  "message": "업로드 파일이 너무 큽니다.",
  "detail": "max_bytes=26214400"
}
```

### 4.4 에러 코드 매핑
- `400` : 요청 필드/형식 자체 오류
- `413` : 용량 초과
- `415` : 확장자/MIME 불허
- `422` : STT 결과 비어있음
- `504` : STT/번역 timeout
- `500` : 모델 내부 예외 또는 미분류 서버 오류

## 5. 모듈 설계(재구현 기준)

### 5.1 권장 디렉터리
```text
app_v2/
  main.py
  core/
    config.py
    errors.py
  api/
    schemas.py
    routes.py
  services/
    upload_guard.py
    stt_service.py
    translation_service.py
    pipeline_service.py
```

### 5.2 모듈 책임
- `core/config.py`
  - 모든 정책값 중앙화
  - 환경 변수 override 가능 구조
- `core/errors.py`
  - 도메인 예외(`AppError`)와 코드(`error_code`) 표준화
- `api/schemas.py`
  - 성공/실패 응답 스키마(Pydantic)
- `services/upload_guard.py`
  - 파일명 정규화
  - 확장자/MIME/크기 검증
  - 파일 저장 + cleanup
- `services/stt_service.py`
  - Whisper 래퍼
  - STT timeout 대상 함수
- `services/translation_service.py`
  - 번역/품질검증/fallback 로직
- `services/pipeline_service.py`
  - endpoint에서 호출하는 유스케이스 단위 orchestration
- `api/routes.py`
  - HTTP 입력 파싱, 서비스 호출, 오류를 HTTP로 매핑

## 6. 예외 처리 상세 설계

### 6.1 예외 클래스 표준
- `AppError(code, message, status_code, detail)`
- `ValidationError` (`415`, `413`, `400`)
- `ProcessingTimeoutError` (`504`)
- `ProcessingFailureError` (`500`)

### 6.2 예외 전파 원칙
- 서비스는 `AppError`를 우선적으로 발생
- API는 `AppError`를 JSON 오류 스키마로 변환
- 미분류 예외는 `INTERNAL_ERROR`로 래핑

### 6.3 단계별 예외
- 업로드 검증 실패 -> 즉시 4xx
- STT timeout -> 504
- 번역 timeout -> 504
- STT/번역 내부 예외 -> 500

## 7. 성능 및 자원 설계

### 7.1 기본 정책
- 파일 읽기: 1MB 청크
- 업로드 최대 크기: 25MB
- STT/번역 timeout: 각 120초
- 모델 인스턴스: 프로세스 내 싱글톤 재사용

### 7.2 운영 확장(권장)
- 동시 요청 제한(세마포어)
- timeout 이후 스레드 잔존 문제를 줄이기 위한 프로세스 격리
- GPU OOM 보호를 위한 요청 큐

## 8. 보안 설계

### 8.1 입력 파일
- 파일명 정규화(path traversal 방지)
- 허용 확장자 화이트리스트
- MIME 점검(단, `application/octet-stream` 예외 허용)

### 8.2 후속 강화 항목
- 파일 시그니처(매직넘버) 확인
- ffprobe 기반 디코딩 검증
- API rate limiting

## 9. 테스트 설계

### 9.1 필수 테스트 케이스
- 정상 오디오 업로드 -> 200
- 확장자 불허 -> 415
- 초과 크기 -> 413
- STT timeout 시뮬레이션 -> 504
- 번역 timeout 시뮬레이션 -> 504
- STT 빈 결과 -> 422

### 9.2 회귀 테스트 대상
- `lang=None` 경로
- `lang=="en"` bypass 경로
- fallback(`score < threshold`) 경로

## 10. 재구현 절차
1. `app_v2/core` 먼저 작성(정책 + 에러 타입)
2. `services` 작성(업로드/STT/번역/파이프라인)
3. `api` 작성(스키마 + 라우트)
4. `main.py`에서 앱 조립
5. 문서 기준으로 동작 비교

## 11. 결정 로그(Architecture Decision)
- ADR-01: 서버가 최종 검증 권한 보유(프론트 검증은 UX 보조)
- ADR-02: timeout은 단계별 분리(STT/번역)
- ADR-03: 모델 예외는 내부 로그 상세, 외부 응답 축약
- ADR-04: 기존 코드 보존 + `app_v2` 병행 구성으로 비교 가능성 확보

