import json
import logging
import re
import ollama
from typing import Any
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

If the user asks to add items to the cart:
- Always call search_menu after you have a restaurant_id
- Then always call add_to_cart for the best matching item from search_menu
- If no matching items are found, ask a short clarification question
"""

MAX_ITERATIONS = 5


def _is_add_to_cart_intent(message: str) -> bool:
    text = message.lower()
    return "add to cart" in text or ("add" in text and "cart" in text)


def _extract_quantity(message: str) -> int:
    match = re.search(r"\b(\d+)\b", message)
    if match:
        return max(1, int(match.group(1)))

    word_map = {
        "one": 1,
        "two": 2,
        "three": 3,
        "four": 4,
        "five": 5,
        "six": 6,
        "seven": 7,
        "eight": 8,
        "nine": 9,
        "ten": 10,
    }
    for word, value in word_map.items():
        if re.search(rf"\b{word}\b", message.lower()):
            return value

    return 1


def _tokenize(text: str) -> list[str]:
    return [t for t in re.split(r"[^a-z0-9]+", text.lower()) if t]


def _extract_menu_items(result: Any) -> list[dict[str, Any]]:
    if isinstance(result, dict) and isinstance(result.get("data"), list):
        return result["data"]
    if isinstance(result, list):
        return result
    return []


def _extract_restaurants(result: Any) -> list[dict[str, Any]]:
    if isinstance(result, dict) and isinstance(result.get("data"), list):
        return result["data"]
    if isinstance(result, list):
        return result
    return []


def _coerce_price(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _select_menu_item(items: list[dict[str, Any]], query: str) -> dict[str, Any] | None:
    if not items:
        return None

    query_text = query.lower().strip()
    query_tokens = _tokenize(query_text)
    best_item: dict[str, Any] | None = None
    best_score = -1

    for item in items:
        name = str(item.get("name", "")).lower()
        if not name:
            continue

        score = 0
        if query_text and query_text in name:
            score += 5
        for token in query_tokens:
            if token in name:
                score += 1
        if not query_tokens:
            score += 1
        if item.get("is_available") is False:
            score -= 100

        if score > best_score:
            best_score = score
            best_item = item

    return best_item


async def run_agent(message: str, session_id: str, auth_header: str) -> ChatResponse:
    client = ollama.AsyncClient(host=settings.OLLAMA_HOST)
    add_intent = _is_add_to_cart_intent(message)
    requested_qty = _extract_quantity(message)
    auto_add_done = False
    restaurant_name_by_id: dict[str, str] = {}

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

            if fn_name == "search_restaurants":
                for item in _extract_restaurants(result):
                    rest_id = str(item.get("id", ""))
                    if rest_id:
                        restaurant_name_by_id[rest_id] = str(item.get("name", ""))

            if fn_name == "search_menu" and add_intent and not auto_add_done:
                if any(tc.tool == "add_to_cart" for tc in tool_calls_made):
                    continue

                menu_items = _extract_menu_items(result)
                if not menu_items:
                    return ChatResponse(
                        response="I couldn't find a matching menu item. Which item should I add?",
                        tool_calls_made=tool_calls_made,
                    )

                query = str(fn_args.get("query", ""))
                chosen = _select_menu_item(menu_items, query)
                if not chosen:
                    return ChatResponse(
                        response="I couldn't find a matching menu item. Which item should I add?",
                        tool_calls_made=tool_calls_made,
                    )

                restaurant_id = str(chosen.get("restaurant_id", ""))
                restaurant_name = restaurant_name_by_id.get(restaurant_id, "Unknown Restaurant")

                add_args = {
                    "item_id": str(chosen.get("id", "")),
                    "item_name": str(chosen.get("name", "")),
                    "qty": requested_qty,
                    "price": _coerce_price(chosen.get("price")),
                    "restaurant_id": restaurant_id,
                    "restaurant_name": restaurant_name,
                    "description": chosen.get("description") or "",
                    "image_url": chosen.get("image_url") or "",
                    "is_vegetarian": chosen.get("is_vegetarian", True),
                    "category_name": chosen.get("category_name") or "Mains",
                }

                add_result = await execute_tool("add_to_cart", add_args, auth_header)
                tool_calls_made.append(ToolCallInfo(tool="add_to_cart", args=add_args, result=add_result))
                messages.append({
                    "role": "tool",
                    "content": json.dumps(add_result),
                })
                auto_add_done = True

                if isinstance(add_result, dict) and add_result.get("error"):
                    return ChatResponse(
                        response="Sorry, I couldn't add that item to your cart.",
                        tool_calls_made=tool_calls_made,
                    )

                return ChatResponse(
                    response=f"Added {requested_qty} x {add_args['item_name']} to your cart.",
                    tool_calls_made=tool_calls_made,
                )

    logger.warning("Agent hit max_iterations=%d for session %s", MAX_ITERATIONS, session_id)
    return ChatResponse(
        response="I've processed your request. Let me know if you need anything else!",
        tool_calls_made=tool_calls_made,
    )
