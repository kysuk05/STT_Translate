# stt_translate_gpu 코드 분석

## 대상 범위 (요청하신 파일)
- `app/main.py`
- `app/stt/whisper_service.py`
- `app/translate/translate_util.py`
- `app/utils/lang_detect.py`
- `app/config.py`
- `run.sh`
- `test_file.py`
- `requirements.txt` (의존성 체크)

## 전체 동작 흐름 (End-to-End)
1. 클라이언트가 `POST /voice-to-prompt` 로 오디오 파일을 `multipart/form-data` (`UploadFile`) 형태로 전송합니다.
2. 서버가 업로드된 오디오를 `tmp/<원본파일명>` 경로에 저장합니다.
3. `WhisperService.transcribe()` 가 `faster-whisper`로 음성을 텍스트(STT)로 변환합니다.
4. `detect_language_with_prob()` 가 변환된 텍스트의 언어를 확률 기반으로 추정합니다.
5. 추정된 언어/상태에 따라 `TranslateUtil.smart_translate()` 로 영어 “프롬프트”를 만듭니다.
   - 언어가 감지되면: `src=<감지된 언어>` → `tgt=en` 번역
   - 언어가 감지되지 않으면: 현재 `smart_translate(..., src="auto", tgt="en")` 를 호출합니다(아래 리스크 참고)

## `app/main.py` (FastAPI 엔트리 + 파이프라인)
### 서버 설정
- `app = FastAPI(title="STT → Translate → Prompt (GPU)")`
- `CORSMiddleware` 추가: `allow_origins=["*"]`, `allow_credentials=True`
- import/시작 시점에 싱글톤 생성
  - `stt_service = WhisperService()`
  - `translate_util = TranslateUtil()`

### 엔드포인트: `POST /voice-to-prompt`
- 시그니처: `async def voice_to_prompt(file: UploadFile = File(...))`
- 처리 흐름:
  1. 업로드 저장
     - `audio_path = f"{UPLOAD_DIR}/{file.filename}"`
     - `UPLOAD_DIR = "tmp"` 를 `os.makedirs(UPLOAD_DIR, exist_ok=True)`로 생성
  2. STT
     - `text = stt_service.transcribe(audio_path)`
  3. 언어 감지
     - `lang = detect_language_with_prob(text)`
  4. 번역 로직
     - `lang is None` 인 경우
       - `prompt = translate_util.smart_translate(text, src="auto", tgt="en")`
     - `lang == "en"` 인 경우
       - `prompt = text` (그대로 사용)
     - 그 외 언어
       - `prompt = translate_util.smart_translate(text, src=lang, tgt="en")`
  5. 응답 JSON
     - `detected_lang`, `stt_text`, `prompt_en`

## `app/stt/whisper_service.py` (STT)
### 모델 초기화
- `faster_whisper.WhisperModel` 사용
- 설정값( `app/config.py` 기반):
  - `WHISPER_MODEL_SIZE`: `"base"`
  - `device`: `DEVICE` (`"cuda"` 가능 시 GPU, 아니면 `"cpu"`)
  - `compute_type`: `WHISPER_COMPUTE_TYPE` : `"int8"`

### 음성 변환(전사)
- `transcribe(audio_path) -> str`
- `segments, _ = self.model.transcribe(audio_path)`
- 반환: `" ".join(segment.text for segment in segments)`

## `app/utils/lang_detect.py` (언어 감지)
### 대상 언어
- `TARGET_LANGS = {"ko","en","ja","zh","es","fr","de","it","pt"}`

### 로직
- `MIN_LENGTH = 5`
- `detect_language_with_prob(text, threshold=0.80) -> Optional[str]`
  - 공백 제거 후 너무 짧으면 `None` 반환
  - `langdetect.detect_langs(text)` 결과에서 1순위(top)만 사용:
    - `top.lang` 이 `TARGET_LANGS`에 있고, `top.prob >= threshold` 이면 `top.lang` 반환
    - 아니면 `None` 반환

## `app/translate/translate_util.py` (번역 + “smart” 폴백)
### 설정 기반 번역 모델
- 번역 모델은 `app/config.py`에서 가져옵니다.
  - `"m2m100": "facebook/m2m100_418M"`
  - `"nllb": "facebook/nllb-200-distilled-600M"`
- 품질 점수용 임베딩 모델
  - `EMBEDDING_MODEL = "sentence-transformers/LaBSE"`

### 주요 구성요소
1. `TranslateUtil.load_model(name)`
   - `self.models` 에 `(tokenizer, model)` 캐시
   - 로드:
     - `AutoTokenizer.from_pretrained(model_name)`
     - `AutoModelForSeq2SeqLM.from_pretrained(model_name).to(DEVICE)`
2. `select_model(src, tgt)`
   - 현재는 무조건 `"m2m100"`을 반환합니다.
3. `translate_with_model(text, src, tgt, model_name)`
   - 문자열 앞뒤 공백 제거
   - `"m2m100"` 경로:
     - `tokenizer.src_lang = src` 설정
     - `forced_bos_token_id=tokenizer.get_lang_id(tgt)` 로 생성
   - `"nllb"` 경로:
     - `NLLB_LANG_MAP` 으로 `src/tgt` 를 NLLB 코드로 매핑
     - `tokenizer.src_lang = src_code` 설정
     - `forced_bos_token_id=tokenizer.convert_tokens_to_ids(tgt_code)` 로 생성
   - 공통:
     - `max_length=256`
     - `num_beams=5`
4. `smart_translate(text, src, tgt="en")`
   - `src is None`이면 내부에서 `src="en"`으로 강제합니다(단, 호출부에서는 언어 감지 실패 시 `src="auto"`를 넘김).
   - 번역 + back-translation 기반 품질 검증:
     1. `result = translate_with_model(text, src, tgt, model_name)`
     2. `back = translate_with_model(result, tgt, src, model_name)`
     3. 품질 점수:
        - `score = cosine_similarity(embed(text), embed(back))`
     4. 폴백:
        - `score < SCORE_THRESHOLD` (config: `0.7`) 이면 `"nllb"`로 재번역
   - 최종 `result` 반환

## `run.sh` (서버 실행 커맨드)
- `python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload`
- FastAPI 앱을 실행하고 auto-reload을 활성화합니다.

## `test_file.py` (TTS 로컬 테스트 유틸)
- `gTTS`로 `TARGET_LANGS`에 있는 여러 언어의 MP3를 생성합니다.
- 생성 파일:
  - `test_<lang>.mp3` (예: `test_ko.mp3`, `test_en.mp3`, ...)
- 이 스크립트는 API 코드에서 호출/참조되지 않습니다.

## `requirements.txt` (의존성 체크)
현재 항목:
- `fastapi`, `uvicorn`, `faster-whisper`, `transformers`, `sentencepiece`, `torch`, `python-multipart`

하지만 코드에서 추가로 import 하는 패키지:
- `sentence_transformers` ( `TranslateUtil` 에서 사용)
- `sklearn` ( `cosine_similarity` 에 사용)
- `langdetect` ( `lang_detect.py` 에서 사용)
- `gTTS` ( `test_file.py` 에서 사용)

## 리스크 / 개선 이슈
1. **언어 감지가 `None`일 때 번역 실패 가능성**
   - `app/main.py`에서 `lang is None`이면 `smart_translate(text, src="auto", tgt="en")` 호출
   - `TranslateUtil.select_model()`은 현재 항상 `"m2m100"` 사용
   - `"m2m100"` 경로에서는 `translate_with_model()`에서 `tokenizer.src_lang = src`로 넣음
   - 만약 `src="auto"`가 M2M100 토크나이저가 허용하는 언어 코드가 아니라면, 런타임에서 크래시가 날 수 있습니다.
   - 더 안전한 방식은 `src=None`을 넘기거나(코드 기본값 사용) `auto`에 대한 실제 매핑 로직을 추가하는 것입니다.

2. **CORS 설정 잠재 충돌**
   - `allow_origins=["*"]` 와 `allow_credentials=True` 조합은 브라우저 쪽 제한을 유발할 수 있습니다.
   - `allow_credentials=False` 또는 명시적인 `origins` 지정이 필요할 수 있습니다.

3. **임시 파일 누적**
   - 업로드된 오디오는 `tmp/`에 저장되지만 삭제 로직이 없습니다.
   - 장시간 사용 시 디스크가 가득 찰 수 있습니다.

4. **파일명 안전성**
   - `audio_path = f"{UPLOAD_DIR}/{file.filename}"` 에서 원본 파일명을 그대로 경로로 사용합니다.
   - `file.filename`을 정규화/샌드박싱해서 경로 탐색(path traversal)이나 잘못된 경로를 막는 것을 권장합니다.

5. **서버 시작 비용/메모리 사용량**
   - `WhisperService()`와 `TranslateUtil()`가 import 시점에 생성됩니다.
   - 서버 시작 시 모델을 로드하므로 초기 로딩이 느리고 메모리를 많이 사용할 수 있습니다.

## 요약 (각 파일이 하는 일)
- `app/main.py`: HTTP API 오케스트레이션 (업로드 → STT → 감지 → 번역)
- `whisper_service.py`: `faster-whisper` 기반 음성→텍스트 변환
- `lang_detect.py`: 확률 임계값을 이용한 언어 분류
- `translate_util.py`: 모델 캐시 + back-translation 점수 기반 폴백을 포함한 번역
- `config.py`: 디바이스/모델/점수/임베딩 설정
- `run.sh`: FastAPI 서버 실행
- `test_file.py`: 로컬에서 언어별 TTS MP3를 생성

