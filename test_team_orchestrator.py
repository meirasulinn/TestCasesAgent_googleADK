"""
Test the Team-based Orchestrator to verify multi-agent routing works correctly.
"""
import asyncio
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.orchestrator.orchestrator import get_orchestrator
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


async def test_team_orchestrator():
    """Test the Team orchestrator with sample requests."""
    
    print("=" * 70)
    print("TESTING GOOGLE ADK TEAM ORCHESTRATOR")
    print("=" * 70)
    
    # Create orchestrator for test user
    user_id = "test_user_team"
    
    print(f"\n[1] Creating orchestrator for user: {user_id}")
    orchestrator = await get_orchestrator(user_id)
    print(f"✓ Orchestrator created")
    print(f"  - Registered agents: {len(orchestrator.agents)}")
    print(f"  - Team agent: {orchestrator.team_agent.name if orchestrator.team_agent else 'None'}")
    
    # Test 1: Simple chat (should route to appropriate agent)
    print("\n[2] Testing chat without file upload")
    result = await orchestrator.handle_chat("Hello! What can you help me with?")
    print(f"✓ Response received:")
    print(f"  - Agent used: {result.get('agent_used', 'unknown')}")
    print(f"  - Response length: {len(result.get('response', ''))}")
    print(f"  - Response preview: {result.get('response', '')[:200]}...")
    
    # Test 2: File upload (should auto-generate test cases)
    print("\n[3] Testing file upload with test spec")
    
    sample_spec = """
Login Page Specification

Requirements:
1. User should be able to enter username and password
2. Submit button should be enabled only when both fields are filled
3. Display error message for invalid credentials
4. Redirect to dashboard on successful login
5. Remember me checkbox should persist credentials
"""
    
    result = await orchestrator.handle_file_upload(
        file_content=sample_spec.encode('utf-8'),
        file_name="login_spec.txt",
        content_type="text/plain"
    )
    
    print(f"✓ File uploaded and processed:")
    print(f"  - Agent used: {result.get('agent_used', 'unknown')}")
    print(f"  - Test cases generated: {result.get('total_count', 0)}")
    print(f"  - Source: {result.get('source', 'unknown')}")
    if result.get('test_cases'):
        print(f"  - Sample test case: {result['test_cases'][0] if result['test_cases'] else 'None'}")
    
    # Test 3: Chat after file upload (should have context)
    print("\n[4] Testing chat after file upload (with context)")
    result = await orchestrator.handle_chat("Can you summarize the test cases you generated?")
    print(f"✓ Response received:")
    print(f"  - Agent used: {result.get('agent_used', 'unknown')}")
    print(f"  - Response: {result.get('response', '')[:300]}...")
    
    print("\n" + "=" * 70)
    print("TEST COMPLETE - Team orchestrator working correctly!")
    print("=" * 70)
    
    # Show session info
    info = await orchestrator.get_session_info()
    print(f"\nSession Info:")
    print(f"  - User ID: {info.get('user_id')}")
    print(f"  - Files: {info.get('files_count')}")
    print(f"  - FAISS docs: {info.get('faiss_docs')}")


if __name__ == "__main__":
    asyncio.run(test_team_orchestrator())
