from gtts import gTTS

TARGET_LANGS = {
    "ko",
    "en",
    "ja",
    "zh",
    "es",
    "fr",
    "de",
    "it",
    "pt",
}

# 각 언어별 테스트 문장
TEST_TEXT = {
    "ko": "안녕하세요. 좋은 날씨입니다.",
    "en": "Hello. It is a nice day.",
    "ja": "こんにちは。いい天気ですね。",
    "zh": "你好。今天天气很好。",
    "es": "Hola. Hace buen tiempo.",
    "fr": "Bonjour. Il fait beau aujourd'hui.",
    "de": "Hallo. Das Wetter ist schön.",
    "it": "Ciao. È una bella giornata.",
    "pt": "Olá. Está um ótimo dia.",
}

for lang in TARGET_LANGS:
    try:
        text = TEST_TEXT[lang]
        tts = gTTS(text=text, lang=lang)
        filename = f"test_{lang}.mp3"
        tts.save(filename)
        print(f"{lang} 음성 파일 생성 완료 → {filename}")
    except Exception as e:
        print(f"{lang} 생성 실패: {e}")