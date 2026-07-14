import json
import logging
import time

logger = logging.getLogger(__name__)

class AuditPublishError(Exception):
    pass

class AuditPublisher:
    def publish(self, fragment: dict) -> bool:
        raise NotImplementedError

class MockAuditPublisher(AuditPublisher):
    def __init__(self):
        self.should_fail = False

    def publish(self, fragment: dict) -> bool:
        # Simulate blocking synchronous write
        time.sleep(0.01) # Small delay to simulate I/O
        if self.should_fail:
            raise AuditPublishError("Message broker failed to acknowledge the audit log")
        
        # Log to stdout as proof of audit
        logger.info(f"AUDIT_FRAGMENT: {json.dumps(fragment)}")
        return True

_publisher = MockAuditPublisher()

def emit_audit_fragment(request_payload: dict, response_payload: dict, formula_weights: dict, rule_matched: int):
    fragment = {
        "request": request_payload,
        "response": response_payload,
        "formula_weights": formula_weights,
        "rule_matched": rule_matched,
        "timestamp": time.time()
    }
    
    try:
        _publisher.publish(fragment)
    except Exception as e:
        logger.error(f"Failed to publish audit log: {e}")
        raise AuditPublishError(f"Synchronous audit transaction failed: {e}")

def set_publisher_failure(should_fail: bool):
    _publisher.should_fail = should_fail
