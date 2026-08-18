import json
from collections.abc import Iterator, Sequence
from types import TracebackType
from typing import Literal, overload

import httpx

from industrial_agent.config.settings import Settings
from industrial_agent.llm.errors import (
    LLMConfigurationError,
    LLMConnectionError,
    LLMResponseError,
    LLMServiceError,
)
from industrial_agent.llm.types import (
    ChatMessage,
    CompletionResult,
    FinalAnswerDelta,
    ReasoningDelta,
    ReasoningTruncated,
    StreamItem,
    ToolCall,
    ToolDefinition,
    ToolResult,
)

REASONING_CHARACTER_LIMIT = 16_000


class _ReasoningNormalizer:
    """Separate literal answer-channel reasoning from final-answer text."""

    _OPEN_TAG = "<think>"
    _CLOSE_TAG = "</think>"

    def __init__(self, *, character_limit: int = REASONING_CHARACTER_LIMIT) -> None:
        self._inside_reasoning = False
        self._pending = ""
        self._character_limit = character_limit
        self._reasoning_characters = 0
        self._truncation_emitted = False

    def feed(self, content: str) -> list[StreamItem]:
        self._pending += content
        items: list[StreamItem] = []
        while self._pending:
            marker = (
                self._CLOSE_TAG if self._inside_reasoning else self._OPEN_TAG
            )
            marker_index = self._pending.find(marker)
            if marker_index >= 0:
                self._emit_text(
                    items,
                    self._pending[:marker_index],
                )
                self._pending = self._pending[
                    marker_index + len(marker) :
                ]
                self._inside_reasoning = not self._inside_reasoning
                continue

            suffix_length = self._possible_tag_suffix_length(
                self._pending,
                marker,
            )
            if suffix_length:
                safe = self._pending[:-suffix_length]
                self._pending = self._pending[-suffix_length:]
            else:
                safe = self._pending
                self._pending = ""
            self._emit_text(items, safe)
            break
        return items

    def finish(self) -> list[StreamItem]:
        """Flush text that cannot become a complete tag at stream end."""
        if not self._pending:
            return []
        items: list[StreamItem] = []
        self._emit_text(items, self._pending)
        self._pending = ""
        return items

    def feed_explicit_reasoning(self, content: str) -> list[StreamItem]:
        """Normalize a provider reasoning channel through the same budget."""
        items: list[StreamItem] = []
        self._emit_reasoning(items, content)
        return items

    def _emit_text(self, items: list[StreamItem], text: str) -> None:
        if not text:
            return
        if self._inside_reasoning:
            self._emit_reasoning(items, text)
        else:
            items.append(FinalAnswerDelta(content=text))

    def _emit_reasoning(self, items: list[StreamItem], text: str) -> None:
        if not text:
            return
        remaining = self._character_limit - self._reasoning_characters
        if remaining > 0:
            visible = text[:remaining]
            if visible:
                items.append(ReasoningDelta(content=visible))
                self._reasoning_characters += len(visible)
        if (
            self._reasoning_characters >= self._character_limit
            and not self._truncation_emitted
        ):
            items.append(ReasoningTruncated())
            self._truncation_emitted = True

    @property
    def inside_reasoning(self) -> bool:
        return self._inside_reasoning

    @staticmethod
    def _possible_tag_suffix_length(text: str, marker: str) -> int:
        maximum = min(len(text), len(marker) - 1)
        for length in range(maximum, 0, -1):
            if text.endswith(marker[:length]):
                return length
        return 0


def _clean_final_answer(content: str) -> str:
    normalizer = _ReasoningNormalizer()
    items = normalizer.feed(content)
    items.extend(normalizer.finish())
    if normalizer.inside_reasoning:
        raise LLMResponseError("LLM service returned empty assistant content")
    final_content = "".join(
        item.content
        for item in items
        if isinstance(item, FinalAnswerDelta)
    ).strip()
    if not final_content:
        raise LLMResponseError("LLM service returned empty assistant content")
    return final_content


class OpenAICompatibleChatAdapter:
    def __init__(
        self,
        *,
        model: str,
        client: httpx.Client,
        owns_client: bool = False,
    ) -> None:
        normalized_model = model.strip()
        if not normalized_model:
            raise LLMConfigurationError("LLM model is required")
        self._model = normalized_model
        self._client = client
        self._owns_client = owns_client

    @classmethod
    def from_settings(
        cls,
        settings: Settings,
        *,
        transport: httpx.BaseTransport | None = None,
    ) -> "OpenAICompatibleChatAdapter":
        if settings.llm_model is None:
            raise LLMConfigurationError("LLM_MODEL is required")
        headers = {"Content-Type": "application/json"}
        if settings.llm_api_key is not None:
            headers["Authorization"] = (
                "Bearer " + settings.llm_api_key.get_secret_value()
            )
        client = httpx.Client(
            base_url=settings.llm_base_url,
            headers=headers,
            timeout=settings.llm_timeout_seconds,
            transport=transport,
        )
        return cls(
            model=settings.llm_model,
            client=client,
            owns_client=True,
        )

    @classmethod
    def router_from_settings(
        cls,
        settings: Settings,
        *,
        transport: httpx.BaseTransport | None = None,
    ) -> "OpenAICompatibleChatAdapter":
        """Build a classifier client with its bounded model and timeout."""
        model = settings.resolved_llm_router_model
        if model is None:
            raise LLMConfigurationError("LLM_MODEL or LLM_ROUTER_MODEL is required")
        headers = {"Content-Type": "application/json"}
        if settings.llm_api_key is not None:
            headers["Authorization"] = (
                "Bearer " + settings.llm_api_key.get_secret_value()
            )
        client = httpx.Client(
            base_url=settings.llm_base_url,
            headers=headers,
            timeout=settings.llm_router_timeout_seconds,
            transport=transport,
        )
        return cls(model=model, client=client, owns_client=True)

    def complete(self, messages: Sequence[ChatMessage]) -> str:
        if not messages:
            raise ValueError("At least one chat message is required")
        try:
            response = self._client.post(
                "chat/completions",
                json={
                    "model": self._model,
                    "messages": [
                        {
                            "role": message.role,
                            "content": message.content,
                        }
                        for message in messages
                    ],
                    "stream": False,
                },
            )
        except (httpx.TimeoutException, httpx.TransportError) as error:
            raise LLMConnectionError("Unable to reach LLM service") from error
        if not response.is_success:
            raise LLMServiceError(response.status_code)
        try:
            payload = response.json()
            content = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError, ValueError) as error:
            raise LLMResponseError(
                "LLM service returned an invalid response"
            ) from error
        if not isinstance(content, str) or not content.strip():
            raise LLMResponseError(
                "LLM service returned empty assistant content"
            )
        return _clean_final_answer(content)

    def complete_with_tools(
        self,
        messages: Sequence[ChatMessage],
        *,
        tools: Sequence[ToolDefinition],
        tool_call: ToolResult | None = None,
    ) -> CompletionResult:
        """Return text or one parsed OpenAI-compatible tool call."""
        if not messages:
            raise ValueError("At least one chat message is required")
        request_messages: list[dict[str, object]] = [
            {
                "role": message.role,
                "content": message.content,
            }
            for message in messages
        ]
        if tool_call is not None:
            request_messages.extend(
                [
                    {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": tool_call.call_id,
                                "type": "function",
                                "function": {
                                    "name": tool_call.name,
                                    "arguments": json.dumps(
                                        tool_call.arguments,
                                        separators=(",", ":"),
                                    ),
                                },
                            }
                        ],
                    },
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.call_id,
                        "content": tool_call.content,
                    },
                ]
            )
        try:
            response = self._client.post(
                "chat/completions",
                json={
                    "model": self._model,
                    "messages": request_messages,
                    "tools": [tool.as_payload() for tool in tools],
                    "stream": False,
                },
            )
        except (httpx.TimeoutException, httpx.TransportError) as error:
            raise LLMConnectionError("Unable to reach LLM service") from error
        if not response.is_success:
            raise LLMServiceError(response.status_code)
        try:
            payload = response.json()
            message = payload["choices"][0]["message"]
            raw_tool_calls = message.get("tool_calls", [])
            content = message.get("content")
        except (KeyError, IndexError, TypeError, ValueError) as error:
            raise LLMResponseError(
                "LLM service returned an invalid tool response"
            ) from error
        if not isinstance(raw_tool_calls, list):
            raise LLMResponseError("LLM service returned invalid tool calls")
        if len(raw_tool_calls) > 1:
            raise LLMResponseError("Only one tool call is supported")
        if content is not None and not isinstance(content, str):
            raise LLMResponseError("LLM service returned invalid assistant content")
        if not raw_tool_calls:
            if not isinstance(content, str) or not content.strip():
                raise LLMResponseError(
                    "LLM service returned empty assistant content"
                )
            return CompletionResult(
                content=_clean_final_answer(content)
            )
        try:
            raw_call = raw_tool_calls[0]
            function = raw_call["function"]
            call_id = raw_call["id"]
            name = function["name"]
            arguments = json.loads(function["arguments"])
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise LLMResponseError(
                "LLM service returned invalid tool arguments"
            ) from error
        if (
            not isinstance(call_id, str)
            or not call_id.strip()
            or not isinstance(name, str)
            or not name.strip()
            or not isinstance(arguments, dict)
        ):
            raise LLMResponseError("LLM service returned invalid tool arguments")
        return CompletionResult(
            content=(
                content.strip()
                if isinstance(content, str) and content.strip()
                else None
            ),
            tool_calls=(ToolCall(call_id=call_id, name=name, arguments=arguments),),
        )

    @overload
    def stream(
        self,
        messages: Sequence[ChatMessage],
        *,
        include_reasoning: Literal[False] = False,
    ) -> Iterator[str]: ...

    @overload
    def stream(
        self,
        messages: Sequence[ChatMessage],
        *,
        include_reasoning: Literal[True],
    ) -> Iterator[StreamItem]: ...

    def stream(
        self,
        messages: Sequence[ChatMessage],
        *,
        include_reasoning: bool = False,
    ) -> Iterator[str | StreamItem]:
        """Yield text, or separated reasoning and answer items, from SSE."""
        if not messages:
            raise ValueError("At least one chat message is required")
        try:
            with self._client.stream(
                "POST",
                "chat/completions",
                json={
                    "model": self._model,
                    "messages": [
                        {
                            "role": message.role,
                            "content": message.content,
                        }
                        for message in messages
                    ],
                    "stream": True,
                },
            ) as response:
                yield from self._stream_response(
                    response,
                    include_reasoning=include_reasoning,
                )
        except (httpx.TimeoutException, httpx.TransportError) as error:
            raise LLMConnectionError("Unable to reach LLM service") from error

    @overload
    def stream_with_tool_result(
        self,
        messages: Sequence[ChatMessage],
        *,
        tools: Sequence[ToolDefinition],
        tool_call: ToolResult,
        include_reasoning: Literal[False] = False,
    ) -> Iterator[str]: ...

    @overload
    def stream_with_tool_result(
        self,
        messages: Sequence[ChatMessage],
        *,
        tools: Sequence[ToolDefinition],
        tool_call: ToolResult,
        include_reasoning: Literal[True],
    ) -> Iterator[StreamItem]: ...

    def stream_with_tool_result(
        self,
        messages: Sequence[ChatMessage],
        *,
        tools: Sequence[ToolDefinition],
        tool_call: ToolResult,
        include_reasoning: bool = False,
    ) -> Iterator[str | StreamItem]:
        """Stream a final answer after one OpenAI-compatible tool result."""
        request_messages: list[dict[str, object]] = [
            {"role": message.role, "content": message.content}
            for message in messages
        ]
        request_messages.extend(
            [
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": tool_call.call_id,
                            "type": "function",
                            "function": {
                                "name": tool_call.name,
                                "arguments": json.dumps(
                                    tool_call.arguments,
                                    separators=(",", ":"),
                                ),
                            },
                        }
                    ],
                },
                {
                    "role": "tool",
                    "tool_call_id": tool_call.call_id,
                    "content": tool_call.content,
                },
            ]
        )
        try:
            with self._client.stream(
                "POST",
                "chat/completions",
                json={
                    "model": self._model,
                    "messages": request_messages,
                    "tools": [tool.as_payload() for tool in tools],
                    "stream": True,
                },
            ) as response:
                yield from self._stream_response(
                    response,
                    include_reasoning=include_reasoning,
                )
        except (httpx.TimeoutException, httpx.TransportError) as error:
            raise LLMConnectionError("Unable to reach LLM service") from error

    def _stream_response(
        self,
        response: httpx.Response,
        *,
        include_reasoning: bool,
    ) -> Iterator[str | StreamItem]:
        if not response.is_success:
            raise LLMServiceError(response.status_code)

        normalizer = _ReasoningNormalizer() if include_reasoning else None
        yielded_text = False
        yielded_final_text = False
        saw_done = False
        for line in response.iter_lines():
            if not line or not line.startswith("data:"):
                continue
            payload = line[5:].strip()
            if payload == "[DONE]":
                saw_done = True
                break
            try:
                chunk = json.loads(payload)
                delta = chunk["choices"][0]["delta"]
            except (KeyError, IndexError, TypeError, ValueError) as error:
                raise LLMResponseError(
                    "LLM service returned an invalid streaming response"
                ) from error
            if not isinstance(delta, dict):
                raise LLMResponseError(
                    "LLM service returned an invalid streaming response"
                )

            if normalizer is None:
                content = delta.get("content")
                if isinstance(content, str) and content:
                    yielded_text = yielded_text or bool(content.strip())
                    yield content
                continue

            reasoning = delta.get("reasoning_content")
            if isinstance(reasoning, str) and reasoning:
                yield from normalizer.feed_explicit_reasoning(reasoning)
            content = delta.get("content")
            if isinstance(content, str) and content:
                for item in normalizer.feed(content):
                    if isinstance(item, FinalAnswerDelta):
                        yielded_final_text = (
                            yielded_final_text or bool(item.content.strip())
                        )
                    yield item

        if not saw_done:
            raise LLMResponseError(
                "LLM service returned an incomplete streaming response"
            )

        if normalizer is not None:
            for item in normalizer.finish():
                if isinstance(item, FinalAnswerDelta):
                    yielded_final_text = (
                        yielded_final_text or bool(item.content.strip())
                    )
                yield item
            if normalizer.inside_reasoning:
                raise LLMResponseError(
                    "LLM service returned an incomplete streaming response"
                )

        if not (yielded_final_text if normalizer is not None else yielded_text):
            raise LLMResponseError(
                "LLM service returned an incomplete streaming response"
            )

    @property
    def is_closed(self) -> bool:
        return self._client.is_closed

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> "OpenAICompatibleChatAdapter":
        return self

    def __exit__(
        self,
        _exc_type: type[BaseException] | None,
        _exc_value: BaseException | None,
        _traceback: TracebackType | None,
    ) -> None:
        self.close()
