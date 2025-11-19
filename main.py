"""
Main entry point for Test Case Agent.
Use: python -m uvicorn src.api:app --host 127.0.0.1 --port 8100
"""
import subprocess
import sys

if __name__ == "__main__":
    # Start the FastAPI server
    subprocess.run([
        sys.executable, "-m", "uvicorn",
        "src.api:app",
        "--host", "127.0.0.1",
        "--port", "8100"
    ])