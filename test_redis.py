import redis.asyncio as aioredis
import asyncio

async def test():
    r = await aioredis.from_url('redis://localhost:6381/0', decode_responses=True)
    result = await r.ping()
    print(f'Redis connection OK: {result}')
    await r.close()

asyncio.run(test())
