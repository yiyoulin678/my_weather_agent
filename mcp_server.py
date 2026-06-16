"""
SYSTEM PROMPT:
你是出行助手，专注于帮助用户查询城市当前温度和天气预警信息。
"""

from __future__ import annotations

import urllib.error
import urllib.parse
import urllib.request

import anyio
from pydantic import BaseModel

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types


SYSTEM_PROMPT = """你是出行助手，专注于帮助用户查询城市当前温度和天气预警信息。"""


class TemperatureParams(BaseModel):
    city: str


class WeatherAlertParams(BaseModel):
    city: str


def fetch_wttr(city: str, fmt: str) -> str:
    encoded_city = urllib.parse.quote(city, safe="")
    url = f"https://wttr.in/{encoded_city}?format={fmt}"
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (compatible; MCP Weather Agent)"},
    )

    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.read().decode("utf-8").strip()
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"HTTP error {exc.code} fetching weather for {city}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"网络错误：{exc.reason}") from exc
    except Exception as exc:
        raise RuntimeError(f"获取天气失败：{exc}") from exc


def format_weather_alert(description: str) -> str:
    normalized = description.lower()
    if "rain" in normalized or "storm" in normalized:
        return "有预警"
    return "无预警"


server = Server(
    name="weather_agent",
    version="1.0.0",
    instructions=SYSTEM_PROMPT,
)


@server.list_tools()
async def list_tools():
    return [
        types.Tool(
            name="get_temperature",
            title="get_temperature",
            description="获取指定城市当前温度。",
            inputSchema={
                "type": "object",
                "properties": {
                    "city": {"type": "string"},
                },
                "required": ["city"],
                "additionalProperties": False,
            },
        ),
        types.Tool(
            name="get_weather_alert",
            title="get_weather_alert",
            description="获取指定城市天气状况描述并判断是否有预警。",
            inputSchema={
                "type": "object",
                "properties": {
                    "city": {"type": "string"},
                },
                "required": ["city"],
                "additionalProperties": False,
            },
        ),
    ]


@server.call_tool()
async def handle_tool_call(tool_name: str, arguments: dict | None):
    if arguments is None:
        arguments = {}

    if tool_name == "get_temperature":
        params = TemperatureParams.model_validate(arguments)
        temperature = fetch_wttr(params.city, "%t")
        return types.CallToolResult(
            content=[types.TextContent(type="text", text=temperature)],
            structuredContent=None,
            isError=False,
        )

    if tool_name == "get_weather_alert":
        params = WeatherAlertParams.model_validate(arguments)
        description = fetch_wttr(params.city, "%C")
        alert = format_weather_alert(description)
        return types.CallToolResult(
            content=[types.TextContent(type="text", text=alert)],
            structuredContent=None,
            isError=False,
        )

    return types.CallToolResult(
        content=[types.TextContent(type="text", text=f"Unknown tool: {tool_name}")],
        structuredContent=None,
        isError=True,
    )


async def main():
    initialization_options = server.create_initialization_options()
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, initialization_options)


if __name__ == "__main__":
    anyio.run(main)