"""
Sample test script to call CAS API
Run the FastAPI server first: uvicorn main:app --reload
Then run this script: python test_request.py
"""
import requests
import json

# Sample request payload
payload = {
    "request_id": "req-001",
    "workflow_instance_id": "workflow-123",
    "action_descriptor": {
        "type": "generateLocators",
        "target_scope": "functional-area",
        "knowledge_dependencies": ["USER_STORY", "ACCEPTANCE_CRITERIA"],
        "reversibility_hint": "reversible with cost"
    },
    "context_snapshot_ref": "snapshot-ref-123",
    "caller_service": "qmentis-ui",
    "trace_id": "trace-xyz-789"
}

# Send POST request
response = requests.post(
    "http://localhost:8000/v1/assess",
    json=payload
)

print("Status Code:", response.status_code)
print("\nResponse:")
print(json.dumps(response.json(), indent=2))
