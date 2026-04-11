# STT Translate GPU 시스템 다이어그램 (v1 / v2)

본 문서는 현재 프로젝트의 두 버전(`app`, `app_v2`)을 큰 틀 관점에서 비교 가능한 형태로 다이어그램화한 문서입니다.  
Mermaid 기반으로 작성되어 IDE/Markdown 뷰어에서 시각화할 수 있습니다.

---

## 1) Version 1 (`app`) 다이어그램

### 1-1. 유즈케이스 다이어그램
```mermaid
flowchart LR
    User[사용자/클라이언트]
    API[FastAPI /voice-to-prompt]
    UC1[오디오 업로드]
    UC2[파일 검증 및 저장]
    UC3[STT 변환]
    UC4[언어 감지]
    UC5[영어 프롬프트 생성]
    UC6[결과 반환]
    UC7[예외/타임아웃 처리]
    UC8[임시파일 정리]

    User --> UC1 --> API
    API --> UC2 --> UC3 --> UC4 --> UC5 --> UC6
    API --> UC7
    API --> UC8
```

### 1-2. 도메인 다이어그램
```mermaid
flowchart TD
    Request[UploadFile Request]
    TempFile[tmp/audio]
    STTText[STT Text]
    Lang[Detected Language]
    Prompt[English Prompt]
    Response[API Response JSON]
    Policy[Config Policy\nsize/mime/ext/timeout]

    Request --> TempFile
    TempFile --> STTText
    STTText --> Lang
    STTText --> Prompt
    Lang --> Prompt
    Prompt --> Response
    Lang --> Response
    STTText --> Response
    Policy -.applies to.-> Request
    Policy -.applies to.-> TempFile
    Policy -.applies to.-> Prompt
```

### 1-3. 시퀀스 다이어그램
```mermaid
sequenceDiagram
    participant C as Client
    participant A as app.main (Endpoint)
    participant W as WhisperService
    participant L as lang_detect
    participant T as TranslateUtil
    participant FS as tmp file

    C->>A: POST /voice-to-prompt (file)
    A->>A: validate_upload()
    A->>FS: chunk write with size limit
    A->>W: transcribe(audio_path) with timeout
    W-->>A: stt_text
    A->>L: detect_language_with_prob(stt_text)
    L-->>A: lang or None
    alt lang == en
        A->>A: prompt = stt_text
    else lang is None or non-en
        A->>T: smart_translate(text, src, "en") with timeout
        T-->>A: prompt_en
    end
    A-->>C: {detected_lang, stt_text, prompt_en}
    A->>FS: cleanup (finally)
```

### 1-4. 클래스 다이어그램 (큰 틀)
```mermaid
classDiagram
    class FastAPIEndpointV1 {
      +voice_to_prompt(file, request)
      -_validate_upload(file, request)
      -_sanitize_filename(filename)
      -_get_audio_extension(filename)
    }

    class WhisperService {
      +transcribe(audio_path) str
    }

    class TranslateUtil {
      +smart_translate(text, src, tgt) str
      +translate_with_model(text, src, tgt, model) str
      +score_similarity(text1, text2) float
    }

    class LangDetect {
      +detect_language_with_prob(text, threshold) Optional[str]
    }

    class ConfigV1 {
      +MAX_UPLOAD_BYTES
      +ALLOWED_AUDIO_FILE_EXTENSIONS
      +ALLOWED_AUDIO_MIME_TYPES
      +MAX_TRANSCRIBE_SECONDS
      +MAX_TRANSLATE_SECONDS
    }

    FastAPIEndpointV1 --> WhisperService
    FastAPIEndpointV1 --> TranslateUtil
    FastAPIEndpointV1 --> LangDetect
    FastAPIEndpointV1 --> ConfigV1
```

---

## 2) Version 2 (`app_v2`) 다이어그램

### 2-1. 유즈케이스 다이어그램
```mermaid
flowchart LR
    User[사용자/클라이언트]
    Route[api.routes]
    Pipeline[VoicePipelineService]
    Guard[Upload Guard]
    STT[SttService]
    Translate[TranslationService]
    Error[표준 오류 응답]
    Success[표준 성공 응답]

    User --> Route
    Route --> Pipeline
    Pipeline --> Guard
    Pipeline --> STT
    Pipeline --> Translate
    Route --> Success
    Route --> Error
```

### 2-2. 도메인 다이어그램
```mermaid
flowchart TD
    UploadRequest[Upload Request]
    UploadMeta[Upload Metadata\nfilename/content-length/mime]
    TempAudio[Temporary Audio File]
    Transcript[Transcript Text]
    Language[Detected Language]
    PromptEn[Prompt in English]
    SuccessResp[VoiceToPromptResponse]
    ErrorResp[ErrorResponse]
    AppError[AppError Domain]
    Settings[Settings Domain\nconfig policy]

    UploadRequest --> UploadMeta
    UploadRequest --> TempAudio
    TempAudio --> Transcript
    Transcript --> Language
    Transcript --> PromptEn
    Language --> PromptEn
    PromptEn --> SuccessResp
    Language --> SuccessResp
    Transcript --> SuccessResp
    AppError --> ErrorResp
    Settings -.constraint.-> UploadMeta
    Settings -.constraint.-> TempAudio
    Settings -.constraint.-> PromptEn
```

### 2-3. 시퀀스 다이어그램
```mermaid
sequenceDiagram
    participant C as Client
    participant R as api.routes
    participant P as VoicePipelineService
    participant G as upload_guard
    participant S as SttService
    participant T as TranslationService
    participant LD as lang_detect

    C->>R: POST /voice-to-prompt(file)
    R->>P: run(file, request)
    P->>G: validate_upload_meta()
    P->>G: save_upload_with_limit()
    P->>S: transcribe() with timeout
    S-->>P: stt_text
    P->>LD: detect_language_with_prob()
    LD-->>P: lang or None
    alt lang == en
        P->>P: prompt = stt_text
    else
        P->>T: smart_translate(text, src, "en") with timeout
        T-->>P: prompt_en
    end
    P->>G: cleanup_file()
    P-->>R: result dict
    R-->>C: VoiceToPromptResponse
    Note over R: AppError 발생 시\nErrorResponse로 변환
```

### 2-4. 클래스 다이어그램 (큰 틀)
```mermaid
classDiagram
    class Settings {
      +max_upload_bytes
      +upload_read_chunk_bytes
      +max_transcribe_seconds
      +max_translate_seconds
      +allowed_audio_extensions
      +allowed_audio_mime_types
    }

    class AppError {
      +error_code
      +message
      +status_code
      +detail
    }

    class VoicePipelineService {
      +run(file, request) dict
    }

    class SttService {
      +transcribe(audio_path) str
    }

    class TranslationService {
      +smart_translate(text, src, tgt) str
      -_translate_with_model(text, src, tgt, model) str
      -_similarity(text1, text2) float
    }

    class UploadGuard {
      +validate_upload_meta(file, request)
      +save_upload_with_limit(file, target_path)
      +sanitize_filename(filename)
      +cleanup_file(path)
    }

    class Routes {
      +voice_to_prompt(file, request)
      +build_router(pipeline_service)
    }

    Routes --> VoicePipelineService
    VoicePipelineService --> UploadGuard
    VoicePipelineService --> SttService
    VoicePipelineService --> TranslationService
    VoicePipelineService --> Settings
    Routes --> AppError
```

---

## 3) 해석 포인트 (요약)
- `v1`은 endpoint(`app/main.py`)에 오케스트레이션 책임이 집중된 구조입니다.
- `v2`는 `Routes -> Pipeline -> Services`로 분리되어 변경 영향 범위가 작고 테스트 경계가 명확합니다.
- 두 버전 모두 핵심 유스케이스(업로드 -> STT -> 감지 -> 번역 -> 응답)는 동일합니다.

