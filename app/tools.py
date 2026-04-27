import logging
import httpx
from app.config import settings

logger = logging.getLogger(__name__)

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_restaurants",
            "description": "Search for restaurants by cuisine type and maximum price per item",
            "parameters": {
                "type": "object",
                "properties": {
                    "cuisine": {"type": "string", "description": "Type of cuisine e.g. South Indian, North Indian, Café"},
                    "max_price": {"type": "integer", "description": "Maximum price per item in INR"},
                },
                "required": ["cuisine", "max_price"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_menu",
            "description": "Search menu items of a specific restaurant",
            "parameters": {
                "type": "object",
                "properties": {
                    "restaurant_id": {"type": "string", "description": "The restaurant ID"},
                    "query": {"type": "string", "description": "Search query e.g. burger, veg, spicy"},
                },
                "required": ["restaurant_id", "query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_to_cart",
            "description": "Add an item to the user's cart",
            "parameters": {
                "type": "object",
                "properties": {
                    "item_id": {"type": "string", "description": "The menu item ID"},
                    "item_name": {"type": "string", "description": "The name of the item"},
                    "qty": {"type": "integer", "description": "Quantity to add"},
                    "price": {"type": "number", "description": "Price per unit in INR"},
                    "restaurant_id": {"type": "string", "description": "Restaurant ID for the item"},
                    "restaurant_name": {"type": "string", "description": "Restaurant name"},
                    "description": {"type": "string", "description": "Item description"},
                    "image_url": {"type": "string", "description": "Item image URL"},
                    "is_vegetarian": {"type": "boolean", "description": "Whether the item is vegetarian"},
                    "category_name": {"type": "string", "description": "Menu category name"},
                },
                "required": ["item_id", "item_name", "qty", "price"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_cart",
            "description": "Get the current contents of the user's cart",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "remove_from_cart",
            "description": "Remove an item from the user's cart",
            "parameters": {
                "type": "object",
                "properties": {
                    "item_id": {"type": "string", "description": "The menu item ID to remove"},
                },
                "required": ["item_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "place_order",
            "description": "Place an order with the current cart contents",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_order_status",
            "description": "Get the status of a specific order",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {"type": "string", "description": "The order ID"},
                },
                "required": ["order_id"],
            },
        },
    },
]


def _build_cart_payload(args: dict) -> dict | None:
    if "menuItem" in args:
        return {
            "menuItem": args["menuItem"],
            "restaurantName": args.get("restaurantName", "Unknown Restaurant"),
            "qty": int(args.get("qty", 1)),
        }

    if "menu_item" in args:
        return {
            "menuItem": args["menu_item"],
            "restaurantName": args.get("restaurant_name", "Unknown Restaurant"),
            "qty": int(args.get("qty", 1)),
        }

    menu_item = {
        "id": args.get("item_id", ""),
        "restaurantId": args.get("restaurant_id", ""),
        "name": args.get("item_name", ""),
        "description": args.get("description", "") or "",
        "price": float(args.get("price", 0)),
        "image": args.get("image_url", "") or "",
        "veg": bool(args.get("is_vegetarian", True)),
        "category": args.get("category_name", "Mains") or "Mains",
    }

    if not menu_item["id"] or not menu_item["restaurantId"]:
        return None

    return {
        "menuItem": menu_item,
        "restaurantName": args.get("restaurant_name", "Unknown Restaurant"),
        "qty": int(args.get("qty", 1)),
    }


async def execute_tool(name: str, args: dict, auth_header: str) -> dict:
    logger.info("Executing tool: %s | args: %s", name, args)
    headers = {}
    if auth_header:
        headers["Authorization"] = auth_header

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            if name == "search_restaurants":
                r = await client.get(
                    f"{settings.RESTAURANT_SERVICE_URL}/restaurants",
                    params={"cuisine": args.get("cuisine", ""), "max_price": args.get("max_price", 9999)},
                    headers=headers,
                )
                r.raise_for_status()
                return r.json()

            elif name == "search_menu":
                r = await client.get(
                    f"{settings.RESTAURANT_SERVICE_URL}/restaurants/{args['restaurant_id']}/menu",
                    params={"query": args.get("query", "")},
                    headers=headers,
                )
                r.raise_for_status()
                return r.json()

            elif name == "add_to_cart":
                payload = _build_cart_payload(args)
                if payload is None:
                    return {"error": "Missing menu item data for cart request"}

                r = await client.post(
                    f"{settings.CART_SERVICE_URL}/cart/items",
                    json=payload,
                    headers=headers,
                )
                r.raise_for_status()
                return r.json()

            elif name == "get_cart":
                r = await client.get(f"{settings.CART_SERVICE_URL}/cart", headers=headers)
                r.raise_for_status()
                return r.json()

            elif name == "remove_from_cart":
                r = await client.delete(
                    f"{settings.CART_SERVICE_URL}/cart/items/{args['item_id']}",
                    headers=headers,
                )
                r.raise_for_status()
                return r.json()

            elif name == "place_order":
                r = await client.post(f"{settings.ORDER_SERVICE_URL}/orders", headers=headers)
                r.raise_for_status()
                return r.json()

            elif name == "get_order_status":
                r = await client.get(
                    f"{settings.ORDER_SERVICE_URL}/orders/{args['order_id']}",
                    headers=headers,
                )
                r.raise_for_status()
                return r.json()

            else:
                return {"error": f"Unknown tool: {name}"}

    except httpx.HTTPStatusError as e:
        logger.error("Tool %s HTTP error: %s", name, e)
        return {"error": f"Service returned {e.response.status_code}", "detail": e.response.text}
    except Exception as e:
        logger.error("Tool %s failed: %s", name, e)
        return {"error": str(e)}
