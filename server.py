"""Music Creator Agent for a2hmarket.

A shop agent that helps buyers create custom music using AI (Suno API).

Features:
- Understand music requirements via conversation
- Generate custom music with Suno API
- Upload generated music to platform storage
- Deliver the final music file to the buyer
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from anthropic import AsyncAnthropicBedrock
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse

from a2h_agent import (
    A2HClient,
    ChatRequest,
    MEMORY_TOOLS,
    MemoryClient,
    dispatch_memory_tool,
    done,
    error,
    text,
    ui,
)
from suno_client import SunoClient

log = logging.getLogger("music-creator-agent")

# LLM configuration
LLM = AsyncAnthropicBedrock()
MODEL_ID = os.environ.get("A2H_MODEL_ID", "us.anthropic.claude-sonnet-4-6")
MAX_TOKENS = int(os.environ.get("A2H_MAX_TOKENS", "2048"))
MAX_TOOL_ROUNDS = int(os.environ.get("A2H_MAX_TOOL_ROUNDS", "6"))

# Music generation settings
DEFAULT_DURATION = int(os.environ.get("DEFAULT_DURATION", "60"))
SUPPORTED_STYLES = [
    "pop", "rock", "electronic", "classical", "jazz", "hip-hop",
    "r&b", "folk", "country", "ambient", "cinematic", "lo-fi",
    "acoustic", "piano", "orchestral", "world",
]

# Agent identity
AGENT_NAME = os.environ.get("AGENT_NAME", "音乐创作助手")


def build_system_prompt(shop_name: str, memory_index_text: str) -> str:
    """Build the system prompt for the music creator agent."""
    return f"""\
你是 {shop_name} 的音乐创作助理。你帮助买家创建个性化的音乐。

你的职责：
1. 了解买家想要的音乐风格、情绪、用途等需求
2. 确认音乐细节（时长、风格、是否带歌词等）
3. 调用音乐生成工具创建音乐
4. 将完成的音乐文件交付给买家

工作规则：
- 先了解清楚需求再生成音乐，不要急于生成
- 如果买家描述模糊，主动询问细节（风格、情绪、节奏、用途）
- 生成前简要总结确认需求
- 生成时间可能需要 1-3 分钟，告知买家耐心等待
- 交付时说明音乐的特点和使用建议

{memory_index_text}

<capabilities>
你可以生成的音乐类型：
{", ".join(SUPPORTED_STYLES)}

你可以控制：
- 音乐风格 (style)
- 时长 (duration, 30-180秒)
- 是否纯音乐 (instrumental)
- 情绪和氛围描述 (prompt)
</capabilities>

<memory_rules>
You can use memory tools (memory_list / memory_read / memory_write / memory_delete)
to recall user preferences and persist durable facts.
1. NEVER write raw user messages, order amounts, code, or per-turn intermediate state.
2. BEFORE writing, memory_list to dedup; PREFER update (with id) over create.
3. title ≤60 chars, specific: "偏好古风音乐" not "用户有偏好".
4. description = retrieval keywords: "古风 纯乐器 仗剑 江湖".
5. scope=user → per-user forever; scope=chat → this chat, 30d TTL.
</memory_rules>
"""


def inject_memory_index(items: list[dict[str, Any]]) -> str:
    """Render the per-request memory index."""
    if not items:
        return "<available_memories>\n(暂无音乐偏好记忆)\n</available_memories>"
    lines = ["<available_memories>"]
    for m in items:
        lines.append(
            f"- [{m.get('id')} | {m.get('type')}] "
            f"{m.get('title', '')} — {m.get('description', '')}"
        )
    lines.append("</available_memories>")
    return "\n".join(lines)


app = FastAPI(title="music-creator-agent")


@app.get("/health")
def health() -> dict[str, str]:
    """Health check probe."""
    return {"status": "ok"}


@app.post("/chat")
async def chat(request: Request) -> StreamingResponse:
    body = await request.json()
    req = ChatRequest.from_json(body)

    memory_client = MemoryClient()
    suno = SunoClient()
    system_text = build_system_prompt("音乐店铺", inject_memory_index(req.memory_index))
    messages: list[dict[str, Any]] = req.anthropic_messages()

    # Extended tools: memory + music generation
    MUSIC_TOOL = {
        "name": "generate_music",
        "description": "Generate custom music based on user requirements",
        "input_schema": {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "Detailed description of the music to generate (mood, theme, instruments, etc.)",
                },
                "style": {
                    "type": "string",
                    "description": f"Music style. Available: {', '.join(SUPPORTED_STYLES)}",
                },
                "duration": {
                    "type": "integer",
                    "description": "Duration in seconds (30-180)",
                },
                "instrumental": {
                    "type": "boolean",
                    "description": "Whether to generate instrumental-only music",
                },
            },
            "required": ["prompt"],
        },
    }

    ALL_TOOLS = MEMORY_TOOLS + [MUSIC_TOOL]

    async def stream():
        thinking_emitted = False

        for round_index in range(MAX_TOOL_ROUNDS):
            response = await LLM.messages.create(
                model=MODEL_ID,
                max_tokens=MAX_TOKENS,
                system=system_text,
                messages=messages,
                tools=ALL_TOOLS,
            )

            tool_uses: list[Any] = []
            for block in response.content:
                if block.type == "text":
                    if block.text:
                        yield text(block.text)
                        if not thinking_emitted:
                            thinking_emitted = True
                elif block.type == "tool_use":
                    tool_uses.append(block)

            if not tool_uses:
                break

            messages.append({"role": "assistant", "content": response.content})

            tool_results: list[dict[str, Any]] = []
            for tu in tool_uses:
                result = None
                try:
                    if tu.name == "generate_music":
                        # Emit thinking message before long operation
                        if not thinking_emitted:
                            yield text("好的，我正在为您创作音乐，请稍候...\n\n")
                            thinking_emitted = True

                        result = await handle_generate_music(
                            dict(tu.input or {}), suno, req
                        )
                    elif tu.name.startswith("memory_"):
                        result = await dispatch_memory_tool(
                            tu.name,
                            dict(tu.input or {}),
                            client=memory_client,
                            open_id=req.open_id,
                            open_chat_id=req.open_chat_id,
                        )
                    else:
                        result = {"error": f"unknown tool: {tu.name}"}
                except Exception as ex:
                    log.exception("Tool %s failed: %s", tu.name, ex)
                    result = {"error": str(ex)}

                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": tu.id,
                        "content": _as_tool_result_content(result),
                    }
                )

            messages.append({"role": "user", "content": tool_results})
        else:
            yield error(
                "TOOL_LOOP_LIMIT",
                "很抱歉，处理过程中遇到了问题，请再试一次。",
            )

        yield done()
        await suno.close()

    return StreamingResponse(stream(), media_type="text/event-stream")


async def handle_generate_music(
    params: dict[str, Any],
    suno: SunoClient,
    req: ChatRequest,
) -> dict[str, Any]:
    """Handle the generate_music tool call.

    1. Generate music via Suno API
    2. Upload the music file to platform storage
    3. Return the file info for delivery
    """
    prompt = params.get("prompt", "")
    style = params.get("style", "")
    duration = params.get("duration", DEFAULT_DURATION)
    instrumental = params.get("instrumental", False)

    if not prompt:
        return {"error": "请描述您想要的音乐风格、情绪或用途"}

    log.info(
        "Generating music: prompt=%s, style=%s, duration=%d, instrumental=%s",
        prompt, style, duration, instrumental,
    )

    # Generate music (wait for completion)
    try:
        result = await suno.generate_and_wait(
            prompt=prompt,
            style=style,
            duration=duration,
            instrumental=instrumental,
            poll_interval=5,
            max_wait=300,
        )
    except Exception as ex:
        log.exception("Music generation failed")
        return {"error": f"音乐生成失败: {str(ex)}"}

    audio_url = result.get("audio_url", "")
    if not audio_url:
        return {"error": "音乐生成完成，但未能获取音频文件"}

    # Upload to platform storage
    try:
        async with A2HClient() as a2h:
            file_info = await upload_music_file(a2h, audio_url, prompt, style)
            return {
                "status": "success",
                "file_url": file_info.get("url", ""),
                "file_name": file_info.get("name", "music.mp3"),
                "title": result.get("title", "AI Generated Music"),
                "ready_for_delivery": True,
            }
    except Exception as ex:
        log.exception("File upload failed")
        return {
            "status": "generated_but_upload_failed",
            "error": f"音频文件上传失败: {str(ex)}",
            "audio_url": audio_url,
        }


async def upload_music_file(
    a2h: A2HClient,
    audio_url: str,
    prompt: str,
    style: str,
) -> dict[str, Any]:
    """Download audio from Suno and upload to platform storage."""
    # Download the audio file
    import httpx
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.get(audio_url)
        resp.raise_for_status()
        audio_bytes = resp.content

    # Generate a filename
    import hashlib
    file_hash = hashlib.md5(audio_bytes).hexdigest()[:8]
    style_slug = style.lower().replace(" ", "-") if style else "music"
    file_name = f"{style_slug}-{file_hash}.mp3"

    # Upload to platform
    upload_result = await a2h.file_upload(
        file_name=file_name,
        file_content=audio_bytes,
        mime_type="audio/mpeg",
    )

    return {
        "url": upload_result.get("url", ""),
        "name": file_name,
        "size": len(audio_bytes),
    }


def _as_tool_result_content(result: Any) -> str:
    """Coerce any dispatcher return value into string for tool_result."""
    if isinstance(result, str):
        return result
    if result is None:
        return "null"
    try:
        return json.dumps(result, ensure_ascii=False, default=str)
    except Exception:
        return str(result)
