from redis.asyncio import Redis

# Lua script, atomic!!
RATE_LIMIT_SCRIPT = """
local count = redis.call("INCR", KEYS[1])
local ttl = redis.call("TTL", KEYS[1])

if count == 1 or ttl < 0 then
    local window_seconds = tonumber(ARGV[1])
    redis.call("EXPIRE", KEYS[1], window_seconds)
    ttl = window_seconds
end

return {count, ttl}
"""

async def increment_rate_limit(redis: Redis, key: str, window_seconds: int) -> tuple[int, int]:
    "Increase active window's count, returns final count and ttl"
    result = await redis.eval(RATE_LIMIT_SCRIPT, 1, key, window_seconds)
    count = int(result[0])
    ttl = int(result[1])
    return count,ttl
