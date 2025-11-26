# """
# Test script to verify agent routing in orchestrator.
# Tests WeatherAgent, TimeAgent, and TestCaseAgent routing.
# """
# import asyncio
# import sys
# sys.path.insert(0, ".")

# from src.orchestrator.orchestrator import get_orchestrator


# async def test_routing():
#     """Test the orchestrator's routing capabilities."""
    
#     print("=" * 80)
#     print("TESTING ORCHESTRATOR ROUTING")
#     print("=" * 80)
#     print()
    
#     # Get orchestrator for test user
#     user_id = "test_routing_user"
#     orchestrator = await get_orchestrator(user_id)
    
#     # Test cases
#     test_cases = [
#         {
#             "name": "Weather Query",
#             "message": "What's the weather like in New York?",
#             "expected_agent": "weather_agent"
#         },
#         {
#             "name": "Time Query",
#             "message": "What time is it in Tokyo right now?",
#             "expected_agent": "time_agent"
#         },
#         {
#             "name": "Test Case Generation",
#             "message": "Generate test cases for a login page",
#             "expected_agent": "test_case_agent"
#         },
#         {
#             "name": "Weather Query 2",
#             "message": "Tell me the temperature in London",
#             "expected_agent": "weather_agent"
#         },
#         {
#             "name": "Time Query 2",
#             "message": "What's the current time in Tel Aviv?",
#             "expected_agent": "time_agent"
#         }
#     ]
    
#     # Run tests
#     results = []
#     for i, test_case in enumerate(test_cases, 1):
#         print(f"\n{'=' * 80}")
#         print(f"TEST {i}: {test_case['name']}")
#         print(f"{'=' * 80}")
#         print(f"Message: {test_case['message']}")
#         print(f"Expected Agent: {test_case['expected_agent']}")
#         print()
        
#         try:
#             # Send message to orchestrator
#             result = await orchestrator.handle_chat(test_case['message'])
            
#             # Extract agent used
#             agent_used = result.get('agent_used', 'unknown')
#             response = result.get('response', '')
            
#             # Check if routing was correct
#             success = agent_used == test_case['expected_agent']
            
#             print(f"✓ Agent Used: {agent_used}")
#             print(f"✓ Routing: {'✅ CORRECT' if success else '❌ WRONG'}")
#             print(f"✓ Response Preview: {response[:200]}...")
            
#             results.append({
#                 'test': test_case['name'],
#                 'expected': test_case['expected_agent'],
#                 'actual': agent_used,
#                 'success': success
#             })
            
#         except Exception as e:
#             print(f"❌ ERROR: {e}")
#             results.append({
#                 'test': test_case['name'],
#                 'expected': test_case['expected_agent'],
#                 'actual': 'error',
#                 'success': False
#             })
    
#     # Summary
#     print(f"\n\n{'=' * 80}")
#     print("TEST SUMMARY")
#     print(f"{'=' * 80}")
#     print()
    
#     total = len(results)
#     passed = sum(1 for r in results if r['success'])
    
#     for result in results:
#         status = "✅ PASS" if result['success'] else "❌ FAIL"
#         print(f"{status} | {result['test']:<30} | Expected: {result['expected']:<20} | Actual: {result['actual']:<20}")
    
#     print()
#     print(f"Results: {passed}/{total} tests passed ({passed/total*100:.1f}%)")
#     print(f"{'=' * 80}")


# if __name__ == "__main__":
#     asyncio.run(test_routing())
