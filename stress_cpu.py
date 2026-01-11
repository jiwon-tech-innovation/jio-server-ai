import time
import math
import multiprocessing

def stress_cpu():
    print("Burn CPU started...")
    start_time = time.time()
    # Stress for 5 minutes
    while time.time() - start_time < 300:
        [math.sqrt(i) for i in range(1000000)]
    print("Burn CPU finished.")

if __name__ == '__main__':
    # Use half of available CPUs or just 2 processes to be safe but effective
    print(f"Starting stress test on {multiprocessing.cpu_count()} cores.")
    processes = []
    # Launch 4 processes to ensure we hit > 50% CPU easily
    for _ in range(4):
        p = multiprocessing.Process(target=stress_cpu)
        p.start()
        processes.append(p)
    
    for p in processes:
        p.join()
