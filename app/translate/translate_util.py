import torch
from transformers import MarianMTModel, MarianTokenizer
from app.config import DEVICE, TRANSLATE_MODEL_NAME

class TranslateUtil:
    def __init__(self):
        self.tokenizer = MarianTokenizer.from_pretrained(
            TRANSLATE_MODEL_NAME
        )
        self.model = MarianMTModel.from_pretrained(
            TRANSLATE_MODEL_NAME
        ).to(DEVICE)

    def translate(self, text: str) -> str:
        inputs = self.tokenizer(
            text,
            return_tensors="pt",
            padding=True
        ).to(DEVICE)

        with torch.no_grad():
            outputs = self.model.generate(**inputs)

        return self.tokenizer.decode(
            outputs[0],
            skip_special_tokens=True
        )
