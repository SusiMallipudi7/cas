import threading
from typing import Dict, Any

class ConfigCache:
    _instance = None
    _lock = threading.Lock() # For singleton initialization

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(ConfigCache, cls).__new__(cls)
                cls._instance._init_cache()
            return cls._instance

    def _init_cache(self):
        # Implementation of a simple Read-Write Lock Pattern using threading
        self._rw_lock = threading.Condition(threading.Lock())
        self._readers = 0
        
        self._data = {
            "formula_version": "1.0.0",
            "weights": {
                "system_area_risk": 0.30,
                "action_consequence_scope": 0.25,
                "reversibility": 0.15,
                "precedent_availability": 0.15,
                "stakeholder_visibility": 0.15
            },
            "system_area_risk": {
                "core_db": 0.9,
                "auth_service": 0.8,
                "reporting_ui": 0.2,
                "single-requirement": 0.2,
                "intra-step": 0.1
            }
        }

    def acquire_read(self):
        with self._rw_lock:
            self._readers += 1

    def release_read(self):
        with self._rw_lock:
            self._readers -= 1
            if self._readers == 0:
                self._rw_lock.notify_all()

    def acquire_write(self):
        self._rw_lock.acquire()
        while self._readers > 0:
            self._rw_lock.wait()

    def release_write(self):
        self._rw_lock.notify_all()
        self._rw_lock.release()

    def get_system_risk(self, target_scope: str) -> float:
        """ Returns risk for scope or None if uninitialized. """
        self.acquire_read()
        try:
            return self._data["system_area_risk"].get(target_scope)
        finally:
            self.release_read()

    def get_weights(self) -> Dict[str, float]:
        self.acquire_read()
        try:
            return dict(self._data["weights"])
        finally:
            self.release_read()

    def get_formula_version(self) -> str:
        self.acquire_read()
        try:
            return self._data["formula_version"]
        finally:
            self.release_read()
            
    def update_system_risk(self, target_scope: str, risk: float):
        self.acquire_write()
        try:
            self._data["system_area_risk"][target_scope] = risk
        finally:
            self.release_write()

config = ConfigCache()
