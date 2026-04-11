import torch
import logging

from transformers import (
    AutoTokenizer,
    AutoModelForSeq2SeqLM,
)

from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

from app.config import (
    DEVICE,
    TRANSLATE_MODELS,
    DEFAULT_MODEL,
    ASIA_LANGS,
    SCORE_THRESHOLD,
    EMBEDDING_MODEL,
)

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


# =========================
# NLLB language map
# =========================

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


# =========================
# TranslateUtil
# =========================

class TranslateUtil:

    def __init__(self):

        self.models = {}

        logger.info("Loading embedding model")

        self.embedder = SentenceTransformer(
            EMBEDDING_MODEL,
            device=DEVICE,
        )

    # =========================
    # model select
    # =========================

    def select_model(self, src, tgt):

        return "m2m100"

    # =========================
    # load model (cache)
    # =========================

    def load_model(self, name):

        if name in self.models:
            return self.models[name]

        model_name = TRANSLATE_MODELS[name]

        logger.info(f"Loading model: {model_name}")

        tokenizer = AutoTokenizer.from_pretrained(
            model_name
        )

        model = AutoModelForSeq2SeqLM.from_pretrained(
            model_name
        ).to(DEVICE)

        self.models[name] = (tokenizer, model)

        return tokenizer, model

    # =========================
    # translate core
    # =========================

    def translate_with_model(
        self,
        text,
        src,
        tgt,
        model_name,
    ):

        tokenizer, model = self.load_model(
            model_name
        )

        text = text.strip()

        # --------------------
        # M2M100
        # --------------------

        if model_name == "m2m100":

            tokenizer.src_lang = src

            encoded = tokenizer(
                text,
                return_tensors="pt",
            ).to(DEVICE)

            with torch.no_grad():

                generated = model.generate(
                    **encoded,
                    forced_bos_token_id=tokenizer.get_lang_id(
                        tgt
                    ),
                    max_length=256,
                    num_beams=5,
                )

            result = tokenizer.decode(
                generated[0],
                skip_special_tokens=True,
            )

        # --------------------
        # NLLB
        # --------------------

        elif model_name == "nllb":

            src_code = NLLB_LANG_MAP.get(
                src,
                "eng_Latn"
            )

            tgt_code = NLLB_LANG_MAP.get(
                tgt,
                "eng_Latn"
            )

            tokenizer.src_lang = src_code

            encoded = tokenizer(
                text,
                return_tensors="pt",
            ).to(DEVICE)

            with torch.no_grad():

                generated = model.generate(
                    **encoded,
                    forced_bos_token_id=tokenizer.convert_tokens_to_ids(
                        tgt_code
                    ),
                    max_length=256,
                    num_beams=5,
                )

            result = tokenizer.decode(
                generated[0],
                skip_special_tokens=True,
            )

        else:

            raise ValueError(
                f"Unknown model {model_name}"
            )

        logger.info(
            f"[TRANSLATE] {model_name} | {src}->{tgt} | {result}"
        )

        return result

    # =========================
    # score check
    # =========================

    def score_similarity(
        self,
        text1,
        text2,
    ):

        v1 = self.embedder.encode([text1])
        v2 = self.embedder.encode([text2])

        score = cosine_similarity(
            v1,
            v2,
        )[0][0]

        return score

    # =========================
    # smart translate
    # =========================

    def smart_translate(
        self,
        text,
        src,
        tgt="en",
    ):

        try:
            if src is None:
                src = "en"

            model_name = self.select_model(
                src,
                tgt,
            )

            logger.info(
                f"[MODEL] selected={model_name}"
            )

            # 1차 번역
            result = self.translate_with_model(
                text,
                src,
                tgt,
                model_name,
            )

            # back translation
            back = self.translate_with_model(
                result,
                tgt,
                src,
                model_name,
            )

            score = self.score_similarity(
                text,
                back,
            )

            logger.info(
                f"[SCORE] {score}"
            )

            # fallback
            if score < SCORE_THRESHOLD:
                logger.info(
                    "[FALLBACK] -> nllb"
                )

                result = self.translate_with_model(
                    text,
                    src,
                    tgt,
                    "nllb",
                )

            return result
        except Exception:
            logger.exception(
                "[SMART_TRANSLATE] failed (src=%s tgt=%s)",
                src,
                tgt,
            )
            raise