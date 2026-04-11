import logging

import torch
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

from app_v2.core.config import settings
from app_v2.core.errors import internal_error


NLLB_LANG_MAP = {
    "en": "eng_Latn",
    "ko": "kor_Hang",
    "ja": "jpn_Jpan",
    "zh": "zho_Hans",
    "fr": "fra_Latn",
    "de": "deu_Latn",
    "es": "spa_Latn",
    "it": "ita_Latn",
    "pt": "por_Latn",
}


class TranslationService:
    def __init__(self) -> None:
        self.logger = logging.getLogger(__name__)
        self.models = {}
        self.embedder = SentenceTransformer(settings.embedding_model, device=settings.device)

    def select_model(self, src: str, tgt: str) -> str:
        _ = (src, tgt)
        return "m2m100"

    def load_model(self, name: str):
        if name in self.models:
            return self.models[name]
        model_name = settings.translate_models[name]
        tokenizer = AutoTokenizer.from_pretrained(model_name)
        model = AutoModelForSeq2SeqLM.from_pretrained(model_name).to(settings.device)
        self.models[name] = (tokenizer, model)
        return tokenizer, model

    def _translate_with_model(self, text: str, src: str, tgt: str, model_name: str) -> str:
        tokenizer, model = self.load_model(model_name)
        text = text.strip()

        if model_name == "m2m100":
            tokenizer.src_lang = src
            encoded = tokenizer(text, return_tensors="pt").to(settings.device)
            with torch.no_grad():
                generated = model.generate(
                    **encoded,
                    forced_bos_token_id=tokenizer.get_lang_id(tgt),
                    max_length=256,
                    num_beams=5,
                )
            return tokenizer.decode(generated[0], skip_special_tokens=True)

        if model_name == "nllb":
            src_code = NLLB_LANG_MAP.get(src, "eng_Latn")
            tgt_code = NLLB_LANG_MAP.get(tgt, "eng_Latn")
            tokenizer.src_lang = src_code
            encoded = tokenizer(text, return_tensors="pt").to(settings.device)
            with torch.no_grad():
                generated = model.generate(
                    **encoded,
                    forced_bos_token_id=tokenizer.convert_tokens_to_ids(tgt_code),
                    max_length=256,
                    num_beams=5,
                )
            return tokenizer.decode(generated[0], skip_special_tokens=True)

        raise internal_error(
            code="UNKNOWN_TRANSLATION_MODEL",
            message="알 수 없는 번역 모델입니다.",
            detail=f"model={model_name}",
        )

    def _similarity(self, text1: str, text2: str) -> float:
        v1 = self.embedder.encode([text1])
        v2 = self.embedder.encode([text2])
        return float(cosine_similarity(v1, v2)[0][0])

    def smart_translate(self, text: str, src: str, tgt: str = "en") -> str:
        try:
            if src is None:
                src = "en"
            model_name = self.select_model(src, tgt)
            result = self._translate_with_model(text, src, tgt, model_name)
            back = self._translate_with_model(result, tgt, src, model_name)
            score = self._similarity(text, back)
            self.logger.info("[V2] translation score: %s", score)

            if score < settings.score_threshold:
                self.logger.info("[V2] fallback model: nllb")
                result = self._translate_with_model(text, src, tgt, "nllb")
            return result
        except Exception as exc:
            if hasattr(exc, "error_code"):
                raise
            self.logger.exception("Translation failed: src=%s tgt=%s", src, tgt)
            raise internal_error(
                code="TRANSLATION_FAILED",
                message="번역 처리에 실패했습니다.",
                detail=str(exc),
            )

