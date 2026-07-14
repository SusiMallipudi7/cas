import threading
import time
from config import config

def test_config_singleton():
    from config import ConfigCache
    config2 = ConfigCache()
    assert config is config2

def test_config_rw_lock():
    # Simulate multiple readers and a writer
    reads = []
    
    def reader():
        time.sleep(0.01) # stagger
        val = config.get_system_risk("core_db")
        reads.append(val)
        
    def writer():
        config.update_system_risk("core_db", 0.95)
        
    # Reset
    config.update_system_risk("core_db", 0.9)
    
    threads = []
    for _ in range(5):
        t = threading.Thread(target=reader)
        threads.append(t)
        t.start()
        
    wt = threading.Thread(target=writer)
    threads.append(wt)
    wt.start()
    
    for _ in range(5):
        t = threading.Thread(target=reader)
        threads.append(t)
        t.start()
        
    for t in threads:
        t.join()
        
    # Final value should be 0.95
    assert config.get_system_risk("core_db") == 0.95
    
    # Reads should be either 0.9 or 0.95, no crashes
    assert all(r in (0.9, 0.95) for r in reads)
