Replaced the deprecated `asyncio.get_event_loop()` call inside `/agent/run` with `asyncio.get_running_loop()`.
