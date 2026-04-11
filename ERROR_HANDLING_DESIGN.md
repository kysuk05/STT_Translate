# ERROR_HANDLING_DESIGN.md

## 목적
악성/이상 입력(특히 대용량 업로드, 잘못된 확장자/콘텐츠, STT/번역 단계에서의 무거운 예외)을
안정적으로 차단하고, 장애 발생 시 원인을 서버 로그로 추적 가능하게 만드는 것을 목표로 합니다.

본 문서는 다음 구현을 기준으로 설명합니다.
- API: `app/main.py` (`POST /voice-to-prompt`)
- 설정: `app/config.py` (업로드 제한, 타임아웃, 허용 형식)
- 모델/로직 로깅:
  - `app/stt/whisper_service.py` (`WhisperService.transcribe`)
  - `app/translate/translate_util.py` (`TranslateUtil.smart_translate`)

## 적용 위치(레이어 구분)
이 프로젝트의 방어는 “요청 수집(ingestion) → STT → 언어감지 → 번역 → 정리(cleanup)” 순서로 계층화되어 있습니다.

1. **요청 수집(업로드 처리) 레이어**
   - 크기 제한(즉시 중단)
   - 확장자/MIME 검증(사전 차단)
   - 파일명 정규화(경로 탐색 방지)
2. **모델 호출(STT/번역) 레이어**
   - API 레벨 타임아웃 적용(요청 지연/멈춤 방어)
   - 예외를 HTTP 에러 코드로 매핑
3. **로직/모델 내부 예외 로깅 레이어**
   - STT/번역 내부 예외 발생 시 `logger.exception()`으로 콘솔/로그에 스택트레이스를 남김
4. **정리(cleanup) 레이어**
   - 성공/실패 여부와 무관하게 `tmp/` 업로드 파일을 best-effort로 삭제

## 설정(구성 값) - `app/config.py`
예외 처리/방어 동작은 상수 기반으로 구성되어 있으며, 주요 값은 아래와 같습니다.

- 업로드 크기 제한
  - `MAX_UPLOAD_SIZE_MB = 25`
  - `MAX_UPLOAD_BYTES = MAX_UPLOAD_SIZE_MB * 1024 * 1024`
  - 목적: 대용량 입력으로 인한 디스크/메모리 압박 완화
- 업로드 읽기 청크 크기
  - `UPLOAD_READ_CHUNK_BYTES = 1024 * 1024` (1MB)
  - 목적: 한 번에 너무 큰 데이터를 읽지 않고 루프에서 초과 여부를 즉시 판단
- 모델 처리 타임아웃(초)
  - `MAX_TRANSCRIBE_SECONDS = 120`
  - `MAX_TRANSLATE_SECONDS = 120`
  - 목적: STT/번역 단계에서 비정상적으로 오래 걸리는 요청을 504로 중단
- 허용 오디오 포맷
  - `ALLOWED_AUDIO_FILE_EXTENSIONS` (예: `wav`, `mp3`, `m4a`, `mp4`, `webm`, `ogg`, `aac`)
  - `ALLOWED_AUDIO_MIME_TYPES` (예: `audio/wav`, `audio/mpeg`, `audio/mp3`, ...)
  - `main.py`에서는 `application/octet-stream`은 “클라이언트가 애매하게 보내는 경우”를 고려해 허용하는 로직이 들어가 있습니다.

## API 레이어 예외 처리 구조 - `app/main.py`
핵심은 `/voice-to-prompt` 핸들러 안에서 단계별로 예외를 잡고, HTTP 응답 코드로 변환하는 방식입니다.

### 1) 입력 검증/정규화
- 파일명 정규화: `_sanitize_filename()`
  - `os.path.basename()`으로 경로를 제거하고,
  - 허용 문자 집합(`_SAFE_FILENAME_CHARS`) 밖의 문자는 `_`로 치환합니다.
  - 목적: 업로드 파일명 기반의 경로 탐색(path traversal) 위험을 줄입니다.
- 형식/크기 검증: `_validate_upload()`
  - 선제적으로 `content-length` 헤더가 있는 경우 `MAX_UPLOAD_BYTES` 초과를 413으로 차단합니다.
  - `ext`(확장자)와 `content_type`(MIME)을 검사하여 415로 차단합니다.
  - MIME이 애매한 경우(`application/octet-stream`)에는 확장자가 허용이면 통과시킵니다.

### 2) 업로드 저장(읽는 중 크기 제한)
업로드 저장은 다음 특징을 갖습니다.
- `while True` + `await file.read(UPLOAD_READ_CHUNK_BYTES)` 루프로 청크 단위 읽기
- `size_bytes` 누적
- 누적 크기가 `MAX_UPLOAD_BYTES`를 넘으면 즉시 `HTTPException(413)` 발생

이 방식의 장점은 “요청 시작 후 초과 입력을 읽는 시간을 최소화”하는 것입니다.
단, `UploadFile.read()` 자체가 청크 단위로 동작하므로,
초과 판정 직전까지는 해당 청크가 이미 메모리에 올라올 수 있다는 점은 한계로 남습니다(구조상 완전한 0-읽기 차단은 불가능).

### 3) STT 단계 예외 매핑
- STT는 블로킹 모델 호출이므로 `asyncio.to_thread()`로 별도 스레드에서 실행한 뒤
  `asyncio.wait_for(..., timeout=MAX_TRANSCRIBE_SECONDS)`로 타임아웃을 걸었습니다.
- 예외 매핑:
  - `asyncio.TimeoutError` → `HTTPException(504, "STT 처리 시간이 초과되었습니다.")`
  - 기타 예외 → `HTTPException(500, "STT 처리에 실패했습니다.")`
- 추가 가드:
  - `text`가 비어있거나 공백만 있는 경우 → `HTTPException(422, "STT 결과가 비어 있습니다.")`
  - 목적: 이후 언어감지/번역에서 불필요한 모델 호출을 줄이고, 클라이언트에 명확한 실패 이유를 전달

### 4) 언어 감지 단계 예외 처리
- `detect_language_with_prob(text)` 호출은 try/except로 감싸되,
  - 실패 시 `lang = None`으로 “언어 감지 실패 상태”를 허용합니다.
  - 결과적으로 번역 단계는 fallback 로직(현재는 `src="auto"` 경로)을 타게 됩니다.

### 5) 번역 단계 예외 매핑
- 번역 역시 블로킹 모델 호출이므로 STT와 동일하게:
  - `asyncio.to_thread(translate_util.smart_translate, ...)`
  - `asyncio.wait_for(..., timeout=MAX_TRANSLATE_SECONDS)`
- 예외 매핑:
  - `TimeoutError` → `HTTPException(504, "번역 처리 시간이 초과되었습니다.")`
  - 기타 예외 → `HTTPException(500, "번역 처리에 실패했습니다.")`

### 6) cleanup (정리) - always 실행
- `finally:` 블록에서 업로드된 임시 파일을 삭제합니다(best-effort).
- 삭제 실패는 요청 성공/실패와 무관하게 무시합니다.

## 모델/로직 내부 예외 로깅 - 스택트레이스 확보
API 레이어가 HTTP 에러를 반환하는 것과 별개로,
모델 내부/로직 내부에서 예외가 날 때 스택트레이스를 남기도록 보강했습니다.

### `WhisperService.transcribe()`
- `try/except`로 `self.model.transcribe(audio_path)` 예외를 캐치하고,
  - `self.logger.exception("Whisper transcribe failed: %s", audio_path)`
  - 다시 `raise` 합니다.
- 장점: API에서 500/504로 끝나더라도 서버 로그에서 정확히 어느 단계에서 터졌는지 확인 가능

### `TranslateUtil.smart_translate()`
- 내부 전체를 try/except로 감싸서,
  - `logger.exception("[SMART_TRANSLATE] failed (src=%s tgt=%s)", src, tgt)`
  - 다시 `raise`
- 장점: translation pipeline이
  - 1차 번역
  - back translation
  - embedding 기반 score
  - fallback(nllb)
  중 어디에서 터졌는지 스택트레이스로 확인 가능

## 개발자 관점 주의점(타임아웃의 한계)
현재 타임아웃은 `asyncio.wait_for` + `asyncio.to_thread` 조합입니다.
이 구조에서 `wait_for`가 타임아웃되어 API는 504로 응답하지만,
`to_thread`가 실행한 실제 모델 연산은 **스레드를 강제 종료하지 못할 수 있습니다**.

즉:
- 클라이언트 관점: 시간 초과로 실패 처리됨(좋음)
- 서버 관점: 실제로는 STT/번역 스레드가 계속 돌아가 GPU/CPU 자원을 점유할 수 있음(주의)

운영 안정성이 더 중요해지면, 아래 중 하나를 검토할 가치가 있습니다.
- 모델 호출을 `Thread`가 아닌 별도 `Process`로 실행(프로세스 단위 kill 가능)
- 동시성 제한(예: 세마포어)로 GPU 점유 폭발 방지
- 요청이 timeout 난 경우 같은 워크 단위를 재사용하지 않도록 워커/큐를 분리

## 프론트 vs 서버: 어디서 막는 것이 좋은가?
현재 구현은 **서버가 최종 권한(authoritative)** 입니다.
프론트에서 용량/형식/시간 제한을 “사전 경고”로 구현하는 것은 사용자 경험에 좋지만,
악의적 요청/우회는 서버에서 무조건 막아야 합니다.

따라서 권장 조합은:
- 프론트: 파일 크기/확장자/MIME 간단 검증 + 즉시 UI 에러
- 서버: `MAX_UPLOAD_BYTES`, 확장자/MIME 검증, STT/번역 타임아웃, 예외 매핑, cleanup

