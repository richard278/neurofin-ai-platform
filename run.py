import os
import subprocess
import sys
import threading
import time

def pipe_output(process, prefix):
    """Pipes standard output/error from a process with a clean prefix."""
    try:
        for line in iter(process.stdout.readline, ''):
            if not line:
                break
            # Print with prefix
            sys.stdout.write(f"{prefix} {line}")
            sys.stdout.flush()
    except Exception as e:
        sys.stderr.write(f"[{prefix} Logging Error] {e}\n")
    finally:
        process.stdout.close()

def main():
    workspace_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Path to virtual env python/uvicorn
    backend_dir = os.path.join(workspace_dir, "backend")
    venv_dir = os.path.join(backend_dir, ".venv")
    
    # Resolve backend command
    if os.name == 'nt':
        uvicorn_bin = os.path.join(venv_dir, "Scripts", "uvicorn.exe")
        python_bin = os.path.join(venv_dir, "Scripts", "python.exe")
    else:
        uvicorn_bin = os.path.join(venv_dir, "bin", "uvicorn")
        python_bin = os.path.join(venv_dir, "bin", "python")
        
    if os.path.exists(uvicorn_bin):
        backend_cmd = [uvicorn_bin, "app.main:app", "--reload"]
    elif os.path.exists(python_bin):
        backend_cmd = [python_bin, "-m", "uvicorn", "app.main:app", "--reload"]
    else:
        # Fall back to system uvicorn
        backend_cmd = ["uvicorn", "app.main:app", "--reload"]
        
    # Resolve frontend command
    frontend_dir = os.path.join(workspace_dir, "frontend")
    
    # Use npm running in shell (necessary for npm on Windows)
    shell_mode = os.name == 'nt'
    frontend_cmd = ["npm", "run", "dev"]
    
    print("\n" + "="*60)
    print("      NEUROFIN AI PLATFORM - CONCURRENT RUNNER")
    print("="*60)
    print(f"Backend path:  {backend_dir}")
    print(f"Frontend path: {frontend_dir}")
    print(f"Backend cmd:   {' '.join(backend_cmd)}")
    print(f"Frontend cmd:  {' '.join(frontend_cmd)}")
    print("Press Ctrl+C to terminate both servers.")
    print("="*60 + "\n")
    
    try:
        # Spawn backend
        backend_proc = subprocess.Popen(
            backend_cmd,
            cwd=backend_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            shell=shell_mode
        )
        
        # Spawn frontend
        frontend_proc = subprocess.Popen(
            frontend_cmd,
            cwd=frontend_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            shell=shell_mode
        )
        
        # Threading for concurrent logs
        # Light green for backend, light blue/cyan for frontend (ANSI sequences if supported)
        # Using plain text tags for reliability
        t_backend = threading.Thread(target=pipe_output, args=(backend_proc, "[Backend] "), daemon=True)
        t_frontend = threading.Thread(target=pipe_output, args=(frontend_proc, "[Frontend]"), daemon=True)
        
        t_backend.start()
        t_frontend.start()
        
        # Keep main thread alive and monitor processes
        while True:
            # Check if any process terminated unexpectedly
            b_status = backend_proc.poll()
            f_status = frontend_proc.poll()
            
            if b_status is not None:
                print(f"\n[System] Backend exited with status {b_status}")
                break
            if f_status is not None:
                print(f"\n[System] Frontend exited with status {f_status}")
                break
                
            time.sleep(0.5)
            
    except KeyboardInterrupt:
        print("\n[System] Shutdown requested. Terminating processes...")
    finally:
        # Gracefully terminate
        try:
            if 'backend_proc' in locals():
                backend_proc.terminate()
                backend_proc.wait(timeout=2)
        except Exception:
            try:
                backend_proc.kill()
            except Exception:
                pass
                
        try:
            if 'frontend_proc' in locals():
                # On Windows npm creates child processes that might survive direct termination, 
                # but terminate is the best portable way.
                frontend_proc.terminate()
                frontend_proc.wait(timeout=2)
        except Exception:
            try:
                frontend_proc.kill()
            except Exception:
                pass
                
        print("[System] Both servers stopped. Goodbye!")

if __name__ == '__main__':
    main()
