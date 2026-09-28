import subprocess
import sys
import time
import os

def main():
    print("Starting all Loam services (Single Port Unified Mode)...")
    
    python_exe = sys.executable
    
    try:
        # Start the 3 backend processes
        p_loam = subprocess.Popen([python_exe, "-m", "loam", "run"])
        time.sleep(1) 
        
        p_proxy = subprocess.Popen([python_exe, "bridge/forced_flow_proxy.py"])
        p_admin = subprocess.Popen([python_exe, "scripts/admin.py"])
        
        # Start the Unified Gateway (Reverse Proxy)
        p_gateway = subprocess.Popen([python_exe, "scripts/unified_gateway.py"])
        time.sleep(1)
        
        print("\n" + "="*50)
        print("🎉 ALL-IN-ONE SINGLE PORT MODE ACTIVE 🎉")
        print("="*50)
        print("Everything is now running on ONE single port (8783)!\n")
        print("🌐 Admin UI (Browser) : http://127.0.0.1:8783/")
        print("🤖 LLM API (Client)   : http://127.0.0.1:8783/v1")
        print("==================================================")
        print("Press Ctrl+C to safely stop all services.\n")
        
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\nShutting down all services...")
        p_gateway.terminate()
        p_admin.terminate()
        p_proxy.terminate()
        p_loam.terminate()
        
        p_gateway.wait()
        p_admin.wait()
        p_proxy.wait()
        p_loam.wait()
        print("All services stopped. Goodbye!")

if __name__ == "__main__":
    main()
