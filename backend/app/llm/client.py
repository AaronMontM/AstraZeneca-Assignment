import logging

from typing import Any, Mapping, Optional, Sequence

from ollama import Client, ChatResponse


logger = logging.getLogger(__name__)


class OllamaClient:

    def __init__(
        self,
        model: str,
        host: str,
        num_ctx: int = 8192,
        num_predict: int = 4096,
    ):
        self.model = model
        self.client = Client(host=host)
        self.num_ctx = num_ctx
        self.num_predict = num_predict

    def chat(
        self,
        messages: Sequence[Mapping[str, Any]],
        tools: Optional[Sequence[Mapping[str, Any]]] = None,
        temperature: float = 0.0,
        format: Optional[Mapping[str, Any]] = None
    ) -> ChatResponse:

        response = self.client.chat(
            model=self.model,
            messages=messages,
            tools=tools,
            format=format,
            options={
                "temperature": temperature,
                "num_ctx": self.num_ctx,
                "num_predict": self.num_predict,
            },
            think=False,
            stream=False
        )

        logger.info(
            "Ollama generation: model=%s, done=%s, done_reason=%s, "
            "prompt_tokens=%s, completion_tokens=%s, content_length=%s",
            response.model,
            response.done,
            response.done_reason,
            response.prompt_eval_count,
            response.eval_count,
            len(response.message.content or ""),
        )

        return response