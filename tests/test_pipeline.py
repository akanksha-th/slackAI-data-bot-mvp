from src.services.llm_service import run_agent
from src.services.cache import CacheService

cache = CacheService()

# question = "show revenue by region for 2025-09-01"
question = "What was the total revenue and total number of orders for each region on 2025-09-02, sorted by highest revenue first?"

cached = cache.get_cached(question)
if cached:
    print("Cache hit:", cached)
else:
    result = run_agent(question)
    print("—"*20)
    print("SQL:", result["sql"])
    print("Rows:", result["result"])
    print("—"*20)
    if not result["error"]:
        cache.set_cached(question, result["result"])