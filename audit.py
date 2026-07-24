import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError

from pydantic import BaseModel, Field

from settings import get_settings

logger = logging.getLogger(__name__)


class AuditFragment(BaseModel):
    """Validated shape passed synchronously to the configured audit publisher."""

    request: dict
    response: dict
    formula_weights: dict
    rule_matched: int
    original_zone: str
    shifted_zone: str
    posture_metadata: dict = Field(default_factory=dict)
    timestamp: float


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
        
        # Write to JSON file in audit_logs directory
        import os
        os.makedirs("audit_logs", exist_ok=True)
        request_id = fragment.get("request", {}).get("request_id", f"unknown-{int(time.time())}")
        file_path = os.path.join("audit_logs", f"audit_{request_id}.json")
        try:
            with open(file_path, "w") as f:
                json.dump(fragment, f, indent=2)
        except Exception as e:
            raise AuditPublishError(f"Failed to write audit file: {e}")
        
        # Log to stdout as proof of audit
        logger.info(f"AUDIT_FRAGMENT: {json.dumps(fragment)}")
        return True

_publisher = MockAuditPublisher()

def emit_audit_fragment(
    request_payload: dict,
    response_payload: dict,
    formula_weights: dict,
    rule_matched: int,
    posture_metadata: dict | None = None,
    original_zone: str | None = None,
    shifted_zone: str | None = None,
):
    resolved_original_zone = original_zone or response_payload.get("original_zone")
    resolved_shifted_zone = shifted_zone or response_payload.get("shifted_zone")
    if not resolved_original_zone or not resolved_shifted_zone:
        raise AuditPublishError(
            "Audit fragment requires original_zone and shifted_zone"
        )

    fragment = AuditFragment(
        request=request_payload,
        response=response_payload,
        formula_weights=formula_weights,
        rule_matched=rule_matched,
        original_zone=resolved_original_zone,
        shifted_zone=resolved_shifted_zone,
        posture_metadata=posture_metadata or {},
        timestamp=time.time(),
    ).model_dump(mode="json")

    timeout = get_settings().audit_timeout_seconds
    executor = ThreadPoolExecutor(max_workers=1)
    future = executor.submit(_publisher.publish, fragment)
    try:
        future.result(timeout=timeout)
    except FuturesTimeoutError as exc:
        logger.error("Audit publish timed out after %.2fs", timeout)
        raise AuditPublishError(f"Synchronous audit transaction timed out after {timeout}s") from exc
    except Exception as e:
        logger.error(f"Failed to publish audit log: {e}")
        raise AuditPublishError(f"Synchronous audit transaction failed: {e}") from e
    finally:
        executor.shutdown(wait=False)

def set_publisher_failure(should_fail: bool):
    _publisher.should_fail = should_fail
