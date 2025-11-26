# """
# Quick manual test for new agents via Swagger UI.
# Start the server and test the routing.
# """

# print("""
# ╔═══════════════════════════════════════════════════════════╗
# ║   Testing WeatherAgent & TimeAgent Routing                ║
# ╚═══════════════════════════════════════════════════════════╝

# 1. Start the server:
#    python main_new.py

# 2. Open Swagger UI:
#    http://127.0.0.1:8100/docs

# 3. Test these messages in /chat endpoint:

#    ┌─────────────────────────────────────────────────────┐
#    │ WEATHER TESTS                                       │
#    ├─────────────────────────────────────────────────────┤
#    │ • "What's the weather in New York?"                 │
#    │ • "Tell me the temperature in London"               │
#    │ • "How's the weather in Tel Aviv?"                  │
#    │                                                     │
#    │ Expected: weather_agent                             │
#    └─────────────────────────────────────────────────────┘

#    ┌─────────────────────────────────────────────────────┐
#    │ TIME TESTS                                          │
#    ├─────────────────────────────────────────────────────┤
#    │ • "What time is it in Tokyo?"                       │
#    │ • "What's the current time in New York?"            │
#    │ • "Tell me the time in Tel Aviv"                    │
#    │                                                     │
#    │ Expected: time_agent                                │
#    └─────────────────────────────────────────────────────┘

#    ┌─────────────────────────────────────────────────────┐
#    │ TEST CASE TESTS                                     │
#    ├─────────────────────────────────────────────────────┤
#    │ • "Generate test cases for login page"              │
#    │ • "Create test scenarios for user registration"     │
#    │                                                     │
#    │ Expected: test_case_agent                           │
#    └─────────────────────────────────────────────────────┘

# 4. Check the logs to see which agent was selected by the router

# 5. Verify the responses are relevant to each agent's purpose

# ═══════════════════════════════════════════════════════════

# Or run automated test:
#    python test_routing.py

# ═══════════════════════════════════════════════════════════
# """)
