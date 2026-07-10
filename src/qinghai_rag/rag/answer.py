from __future__ import annotations

import os
from typing import Any, Protocol

import requests

REFUSAL = "当前数据集中没有足够依据回答。"
CONSERVATIVE_INTENTS = (
    "游客数量",
    "客流量",
    "门票",
    "票价",
    "营业收入",
    "开放时间",
    "实时天气",
)


class LLMBackend(Protocol):
    def generate(self, query: str, evidence: list[dict[str, Any]]) -> str: ...


class OpenAICompatibleBackend:
    def __init__(
        self, api_key: str | None = None, base_url: str | None = None, model: str | None = None
    ):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY", "")
        self.base_url = (base_url or os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")).rstrip(
            "/"
        )
        self.model = model or os.getenv("LLM_MODEL", "")
        if not self.api_key or not self.model:
            raise ValueError(
                "OPENAI_API_KEY and LLM_MODEL are required for the optional LLM backend"
            )

    def generate(self, query: str, evidence: list[dict[str, Any]]) -> str:
        context = "\n".join(f"[{item['source_id']}] {item['text']}" for item in evidence)
        prompt = (
            "只依据下列证据回答。每个事实后用[source_id]引用；证据不足则原样回答“当前数据集中没有足够依据回答。”\n"
            f"问题：{query}\n证据：\n{context}"
        )
        response = requests.post(
            f"{self.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            json={
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0,
            },
            timeout=90,
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]


class EvidenceAnswerer:
    def __init__(self, backend: LLMBackend | None = None, minimum_score: float = 0.2):
        self.backend = backend
        self.minimum_score = minimum_score

    def answer(self, query: str, evidence: list[dict[str, Any]]) -> dict[str, Any]:
        reliable = [item for item in evidence if float(item.get("score", 0)) >= self.minimum_score]
        unsupported_intent = next(
            (
                intent
                for intent in CONSERVATIVE_INTENTS
                if intent in query and not any(intent in item.get("text", "") for item in reliable)
            ),
            None,
        )
        if not reliable or unsupported_intent:
            return {"answer": REFUSAL, "evidence": [], "refused": True}
        if self.backend:
            answer = self.backend.generate(query, reliable)
        else:
            lines = ["当前数据集中检索到以下可溯源证据："]
            for item in reliable:
                url = item.get("source_url", "")
                lines.append(f"- {item['text']} [{item['source_id']}]({url})")
            answer = "\n".join(lines)
        return {"answer": answer, "evidence": reliable, "refused": False}
