import subprocess
import time
import sys
from simple_demo import main

def test_demo():
    server_process = None
    try:
        print("[SETUP] Starting working MCP servers...")
        server_process = subprocess.Popen([
            sys.executable, "working_mcp_servers.py"
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        time.sleep(2)
        print("[SETUP] Servers started, running demo...")
        main()
        
    finally:
        if server_process:
            server_process.terminate()
            print("[CLEANUP] Servers stopped")

if __name__ == "__main__":
    test_demo()