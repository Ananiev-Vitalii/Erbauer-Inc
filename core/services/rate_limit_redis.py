import hashlib
import logging

from django.core.cache import caches
from django.core.cache.backends.redis import RedisCache
from redis.exceptions import ConnectionError, NoScriptError, ResponseError, TimeoutError

logger = logging.getLogger(__name__)


class RateLimitUnavailable(RuntimeError):
    pass


SCRIPT = """
local operation = ARGV[1]
if operation == 'reset' then
    for i = 1, #KEYS do
        redis.call('DEL', KEYS[i])
    end
    return {0, 0}
end
local now = tonumber(ARGV[2])
local remaining = 0
local matched = 0
for i = 2, #KEYS, 2 do
    local until_time = tonumber(redis.call('GET', KEYS[i]) or '0')
    local seconds = math.max(0, until_time - now)
    if seconds > remaining then
        remaining = seconds
        matched = i / 2
    end
end
if remaining > 0 or operation == 'read' then
    return {remaining, matched}
end
local limit = tonumber(ARGV[3])
local window = tonumber(ARGV[4])
local cooldown = tonumber(ARGV[5])
local counts = {}
local triggered = 0
for i = 1, #KEYS, 2 do
    local count = tonumber(redis.call('GET', KEYS[i]) or '0') + 1
    counts[i] = count
    if count >= limit and triggered == 0 then
        triggered = (i + 1) / 2
    end
end
for i = 1, #KEYS, 2 do
    if triggered > 0 then
        if cooldown > 0 then
            redis.call('SET', KEYS[i + 1], now + cooldown, 'EX', cooldown)
        else
            redis.call('DEL', KEYS[i + 1])
        end
        redis.call('DEL', KEYS[i])
    elseif window > 0 then
        redis.call('SET', KEYS[i], counts[i], 'EX', window)
    else
        redis.call('DEL', KEYS[i])
    end
end
if triggered > 0 then
    return {cooldown, triggered}
end
return {0, 0}
"""
SCRIPT_SHA = hashlib.sha1(SCRIPT.encode(), usedforsecurity=False).hexdigest()


def execute_rate_limit(
        *,
        keys: list[str],
        operation: str,
        now: int,
        attempts_limit: int = 0,
        window_seconds: int = 0,
        cooldown_seconds: int = 0,
) -> tuple[int, int]:
    backend = caches["default"]
    if not isinstance(backend, RedisCache):
        logger.error("Rate limiting requires Django RedisCache.")
        raise RateLimitUnavailable("Redis cache backend is required.")

    redis_keys = [backend.make_and_validate_key(key) for key in keys]
    arguments = [operation, now, attempts_limit, window_seconds, cooldown_seconds]

    try:
        client = backend._cache.get_client(write=True)
        pool = client.connection_pool
        connection = pool.get_connection()
        try:
            connection.send_command(
                "EVALSHA", SCRIPT_SHA, len(redis_keys), *redis_keys, *arguments
            )
            try:
                result = connection.read_response()
            except NoScriptError:
                connection.send_command(
                    "EVAL", SCRIPT, len(redis_keys), *redis_keys, *arguments
                )
                result = connection.read_response()
        except (ConnectionError, TimeoutError, ResponseError):
            connection.disconnect()
            raise
        finally:
            pool.release(connection)
    except (ConnectionError, TimeoutError, ResponseError) as error:
        if isinstance(error, ResponseError) and (
                "user_script:" in str(error)
                or "Error compiling script" in str(error)
                or str(error).startswith("WRONGTYPE")
        ):
            raise
        logger.error("Rate limit Redis operation failed (%s).", type(error).__name__)
        raise RateLimitUnavailable("Rate limit storage is unavailable.") from error

    return int(result[0]), int(result[1])
