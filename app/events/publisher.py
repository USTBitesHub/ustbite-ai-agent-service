import json
import aio_pika
from app.config import settings

async def publish_event(routing_key: str, message: dict):
    if not settings.rabbitmq_url:
        return
    connection = await aio_pika.connect_robust(settings.rabbitmq_url)
    async with connection:
        channel = await connection.channel()
        exchange = await channel.declare_exchange("ustbite_events", aio_pika.ExchangeType.TOPIC)
        await exchange.publish(
            aio_pika.Message(body=json.dumps(message).encode()),
            routing_key=routing_key,
        )
