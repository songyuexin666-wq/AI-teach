import json
import os
import re
from typing import Dict, List, Union

import numpy as np
import torch
from tokenizers import AddedToken
from transformers import PreTrainedTokenizer


def _create_token_regex(tokens: List[str]) -> re.Pattern:
    escaped_tokens = [re.escape(token) for token in tokens]
    escaped_tokens.sort(key=len, reverse=True)
    pattern = r"^(" + "|".join(escaped_tokens) + r")"
    return re.compile(pattern)


class GreedyMathUTF16InnerTokenizer:
    def __init__(
        self,
        special_tokens: Dict[str, list],
        math_vocab: Dict[str, int],
    ):
        self.special_tokens = special_tokens
        self.math_vocab = math_vocab
        self.reverse_math_vocab = {v: k for k, v in math_vocab.items()}
        self.math_vocab_size = len(math_vocab)

        all_special_tokens = special_tokens.get("all", [])
        self.SPECIAL_TOKEN_MAPPING = {}
        for idx, tag in enumerate(all_special_tokens):
            if tag not in self.SPECIAL_TOKEN_MAPPING:
                self.SPECIAL_TOKEN_MAPPING[tag] = self.math_vocab_size + 65536 + idx

        self.REVERSE_SPECIAL_TOKEN_MAPPING = {
            v: k for k, v in self.SPECIAL_TOKEN_MAPPING.items()
        }
        self.SPECIAL_TOKEN_OFFSET = len(self.SPECIAL_TOKEN_MAPPING)

        self.FORMAT_TAG_PATTERN = _create_token_regex(special_tokens["formatting"])
        self.MATH_TAG_PATTERN = _create_token_regex(special_tokens["math_external"])
        self.SYSTEM_TAG_PATTERN = _create_token_regex(special_tokens.get("system", []))

        self.MATH_TAG_START = "<math"
        self.MATH_END_TAG = "</math>"
        self.sorted_math_tokens = sorted(math_vocab.keys(), key=len, reverse=True)
        self.utf16_offset = self.math_vocab_size
        self.special_offset = self.math_vocab_size + 65536

    @property
    def vocab_size(self):
        return self.math_vocab_size + 65536 + self.SPECIAL_TOKEN_OFFSET

    def _tokenize_math(self, text: str) -> List[int]:
        tokens = []
        while text:
            matched = False
            for token in self.sorted_math_tokens:
                if text.startswith(token):
                    tokens.append(self.math_vocab[token])
                    text = text[len(token) :]
                    matched = True
                    break
            if matched:
                continue

            utf16_tokens = self.text_to_utf16_numbers(text[0])
            tokens.extend([t + self.utf16_offset for t in utf16_tokens])
            text = text[1:]

        return tokens

    def _tokenize(self, text: str) -> List[int]:
        tokens = []
        in_math = False

        while text:
            match = self.SYSTEM_TAG_PATTERN.search(text)
            if match:
                tag = match.group(1)
                tokens.append(self.SPECIAL_TOKEN_MAPPING[tag])
                text = text[match.end() :]
                continue

            match = self.MATH_TAG_PATTERN.search(text)
            if match:
                tag = match.group(1)
                if tag.startswith(self.MATH_TAG_START):
                    in_math = True
                elif tag == self.MATH_END_TAG:
                    in_math = False
                tokens.append(self.SPECIAL_TOKEN_MAPPING[tag])
                text = text[match.end() :]
                continue

            if in_math:
                math_end_position = text.find(self.MATH_END_TAG)
                math_str = text if math_end_position == -1 else text[:math_end_position]
                tokens.extend(self._tokenize_math(math_str))
                text = "" if math_end_position == -1 else text[math_end_position:]
                continue

            match = self.FORMAT_TAG_PATTERN.search(text)
            if match:
                tag = match.group(1)
                tokens.append(self.SPECIAL_TOKEN_MAPPING[tag])
                text = text[match.end() :]
                continue

            utf16_tokens = self.text_to_utf16_numbers(text[0])
            tokens.extend([t + self.utf16_offset for t in utf16_tokens])
            text = text[1:]

        return tokens

    def text_to_utf16_numbers(self, text: str) -> List[int]:
        utf16_bytes = text.encode("utf-16le")
        numbers = []
        for i in range(0, len(utf16_bytes), 2):
            number = utf16_bytes[i] + (utf16_bytes[i + 1] << 8)
            numbers.append(number)
        return numbers

    def utf16_numbers_to_text(self, numbers: List[int]) -> str:
        byte_array = bytearray()
        for number in numbers:
            byte_array.append(number & 0xFF)
            byte_array.append((number >> 8) & 0xFF)
        try:
            return byte_array.decode("utf-16le", errors="ignore")
        except Exception:
            return ""

    def __call__(
        self, texts: Union[str, List[str]], **kwargs
    ) -> Dict[str, List[List[int]]]:
        tokenized = []
        if isinstance(texts, str):
            texts = [texts]
        for text in texts:
            tokenized.append(self._tokenize(text))
        return {"input_ids": tokenized}

    def decode(self, token_ids, **kwargs) -> str:
        if isinstance(token_ids, (np.ndarray, torch.Tensor)):
            token_ids = token_ids.tolist()

        decoded_text = ""
        utf16_buffer: List[int] = []

        def flush_utf16():
            nonlocal decoded_text, utf16_buffer
            if utf16_buffer:
                decoded_text += self.utf16_numbers_to_text(utf16_buffer)
                utf16_buffer = []

        for token_id in token_ids:
            if token_id in self.REVERSE_SPECIAL_TOKEN_MAPPING:
                flush_utf16()
                decoded_text += self.REVERSE_SPECIAL_TOKEN_MAPPING[token_id]
            elif token_id < self.math_vocab_size:
                flush_utf16()
                decoded_text += self.reverse_math_vocab.get(token_id, "")
            elif token_id < self.special_offset:
                utf16_buffer.append(token_id - self.utf16_offset)
            else:
                flush_utf16()

        flush_utf16()
        return decoded_text


class GreedyMathUTF16TokenizerCompat(PreTrainedTokenizer):
    def __init__(
        self,
        special_tokens: Dict[str, list] | None = None,
        model_checkpoint: str | None = None,
        **kwargs,
    ):
        if special_tokens is None:
            special_tokens = {}

        checkpoint_path = model_checkpoint or ""
        if checkpoint_path.startswith("s3://"):
            checkpoint_path = os.path.join(
                os.environ.get("XDG_CACHE_HOME", ""),
                "datalab",
                "datalab",
                "Cache",
                "models",
                checkpoint_path.replace("s3://", ""),
            )

        vocab_math_path = os.path.join(checkpoint_path, "vocab_math.json")
        if not os.path.exists(vocab_math_path):
            raise FileNotFoundError(
                f"未找到 GreedyMathUTF16Tokenizer 所需的 vocab_math.json: {vocab_math_path}"
            )

        with open(vocab_math_path, "r", encoding="utf-8") as f:
            math_vocab = json.load(f)

        self.special_tokens = special_tokens
        self.ocr_tokenizer = GreedyMathUTF16InnerTokenizer(
            special_tokens=special_tokens,
            math_vocab=math_vocab,
        )
        self.system_tokens = {
            value: self.ocr_tokenizer._tokenize(value)[0]
            for value in special_tokens.get("system", [])
        }
        self.SPECIAL_TOKEN_MAPPING = self.ocr_tokenizer.SPECIAL_TOKEN_MAPPING

        super().__init__(
            bos_token=None,
            eos_token=AddedToken("</S>", lstrip=False, rstrip=False, special=True),
            pad_token=AddedToken("<PAD>", lstrip=False, rstrip=False, special=True),
            unk_token=None,
            clean_up_tokenization_spaces=False,
            **kwargs,
        )

    @property
    def vocab_size(self):
        return self.ocr_tokenizer.vocab_size

    def get_vocab(self) -> Dict[str, int]:
        vocab = {
            token: token_id
            for token, token_id in self.ocr_tokenizer.math_vocab.items()
        }
        vocab.update(self.SPECIAL_TOKEN_MAPPING)
        return vocab

    def _tokenize(self, text: str, **kwargs):
        return self.ocr_tokenizer._tokenize(text)

    def __call__(
        self,
        texts: Union[str, List[str]],
        tasks: Union[str, List[str]] = None,
        **kwargs,
    ) -> Dict[str, List[List[int]]]:
        if isinstance(texts, str):
            texts = [texts]
        return {"input_ids": [self._tokenize(text) for text in texts]}

    def decode(self, token_ids, **kwargs):
        return self.ocr_tokenizer.decode(token_ids)


def apply_surya_tokenizer_compat() -> None:
    try:
        import surya.common.surya.processor.tokenizer as tokenizer_module
    except ImportError:
        return

    try:
        import surya.recognition.loader as loader_module
    except ImportError:
        loader_module = None

    # Old surya versions hard-coded Qwen2Tokenizer and need a patch.
    # Newer versions changed the package layout and can handle the newer
    # tokenizer/model format directly, so we leave them untouched.
    tokenizer_module.SuryaOCRTokenizer = GreedyMathUTF16TokenizerCompat
    if loader_module is not None:
        loader_module.SuryaOCRTokenizer = GreedyMathUTF16TokenizerCompat
