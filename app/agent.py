import json
import logging
import ollama
from app.config import settings
from app.models import ChatResponse, ToolCallInfo
from app.tools import TOOLS, execute_tool

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are USTBites AI assistant for a food delivery app.
Help users order food using the available tools.

Tool usage rules:
- search_restaurants(cuisine, max_price): use this FIRST to find restaurants and get their IDs
- search_menu(restaurant_id, query): use AFTER getting a restaurant_id from search_restaurants
- add_to_cart(item_id, item_name, qty, price): requires item_id from search_menu result
- Never guess item_id or restaurant_id - always get them from tool results first
- For quantities, use exactly what the user says (e.g "2 burgers" → qty=2, single call)
- Never call the same tool twice for the same item
- Confirm actions after tool calls in a friendly tone
- Keep responses concise
- If a tool fails, tell the user politely
"""

MAX_ITERATIONS = 5


async def run_agent(message: str, session_id: str, auth_header: str) -> ChatResponse:
    client = ollama.AsyncClient(host=settings.OLLAMA_HOST)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": message},
    ]

    tool_calls_made: list[ToolCallInfo] = []

    for iteration in range(MAX_ITERATIONS):
        logger.info("Agent iteration %d | session: %s", iteration + 1, session_id)

        response = await client.chat(
            model=settings.OLLAMA_MODEL,
            messages=messages,
            tools=TOOLS,
        )

        assistant_msg = response.message
        messages.append({
            "role": "assistant",
            "content": assistant_msg.content or "",
            "tool_calls": [tc.model_dump() for tc in (assistant_msg.tool_calls or [])],
        })

        if not assistant_msg.tool_calls:
            logger.info("Agent done after %d iterations", iteration + 1)
            return ChatResponse(
                response=assistant_msg.content or "Done.",
                tool_calls_made=tool_calls_made,
            )

        for tool_call in assistant_msg.tool_calls:
            fn_name = tool_call.function.name
            fn_args = tool_call.function.arguments
            if isinstance(fn_args, str):
                fn_args = json.loads(fn_args)

            result = await execute_tool(fn_name, fn_args, auth_header)

            tool_calls_made.append(ToolCallInfo(tool=fn_name, args=fn_args, result=result))

            messages.append({
                "role": "tool",
                "content": json.dumps(result),
            })

    logger.warning("Agent hit max_iterations=%d for session %s", MAX_ITERATIONS, session_id)
    return ChatResponse(
        response="I've processed your request. Let me know if you need anything else!",
        tool_calls_made=tool_calls_made,
    )
