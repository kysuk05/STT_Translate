import torch

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

WHISPER_MODEL_SIZE = "base"
# WHISPER_COMPUTE_TYPE = "float16" if DEVICE == "cuda" else "int8"
WHISPER_COMPUTE_TYPE = "int8"

TRANSLATE_MODEL_NAME = "Helsinki-NLP/opus-mt-ko-en"
