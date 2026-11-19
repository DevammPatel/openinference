"""
Same agent, three runs, against a mocked OpenAI endpoint (no API key needed):

1. responses-api: Responses API, usage with cached_tokens=0 and reasoning_tokens=0
2. chat-completions: Chat Completions, same usage numbers
3. chat-completions-no-usage: Chat Completions, provider sends no usage at all

Usage: python zero_token_counts.py <project-name>
"""

import asyncio
import sys

import httpx
import respx
from agents import Agent, OpenAIChatCompletionsModel, OpenAIResponsesModel, Runner
from openai import AsyncOpenAI
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk import trace as trace_sdk
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace.export import SimpleSpanProcessor

from openinference.instrumentation.openai_agents import OpenAIAgentsInstrumentor
from openinference.semconv.resource import ResourceAttributes

project_name = sys.argv[1] if len(sys.argv) > 1 else "openai-agents-zero-token-counts"
tracer_provider = trace_sdk.TracerProvider(
    resource=Resource({ResourceAttributes.PROJECT_NAME: project_name})
)
tracer_provider.add_span_processor(
    SimpleSpanProcessor(OTLPSpanExporter("http://localhost:6006/v1/traces"))
)
OpenAIAgentsInstrumentor().instrument(tracer_provider=tracer_provider)

BASE_URL = "https://mock-openai.test/v1"
client = AsyncOpenAI(api_key="sk-mock", base_url=BASE_URL)

CHAT_COMPLETION = {
    "id": "chatcmpl-1",
    "object": "chat.completion",
    "created": 0,
    "model": "mock-model",
    "choices": [
        {
            "index": 0,
            "finish_reason": "stop",
            "message": {"role": "assistant", "content": "Hello!"},
        }
    ],
}
CHAT_USAGE = {
    "prompt_tokens": 12,
    "completion_tokens": 3,
    "total_tokens": 15,
    "prompt_tokens_details": {"cached_tokens": 0},
    "completion_tokens_details": {"reasoning_tokens": 0},
}
RESPONSE = {
    "id": "resp-1",
    "object": "response",
    "created_at": 0,
    "model": "mock-model",
    "status": "completed",
    "output": [
        {
            "type": "message",
            "id": "msg-1",
            "status": "completed",
            "role": "assistant",
            "content": [{"type": "output_text", "text": "Hello!", "annotations": []}],
        }
    ],
    "parallel_tool_calls": True,
    "tool_choice": "auto",
    "tools": [],
    "usage": {
        "input_tokens": 12,
        "output_tokens": 3,
        "total_tokens": 15,
        "input_tokens_details": {"cached_tokens": 0},
        "output_tokens_details": {"reasoning_tokens": 0},
    },
}


async def run(name: str, model: object, route: str, body: dict) -> None:
    with respx.mock(assert_all_called=True) as mock:
        mock.post(f"{BASE_URL}/{route}").mock(return_value=httpx.Response(200, json=body))
        await Runner.run(Agent(name=name, model=model), "Say hello")  # type: ignore[arg-type]


async def main() -> None:
    await run("responses-api", OpenAIResponsesModel("mock-model", client), "responses", RESPONSE)
    await run(
        "chat-completions",
        OpenAIChatCompletionsModel("mock-model", client),
        "chat/completions",
        {**CHAT_COMPLETION, "usage": CHAT_USAGE},
    )
    await run(
        "chat-completions-no-usage",
        OpenAIChatCompletionsModel("mock-model", client),
        "chat/completions",
        CHAT_COMPLETION,
    )


if __name__ == "__main__":
    asyncio.run(main())
    tracer_provider.force_flush()
