from __future__ import annotations
import asyncio
import json
from typing import AsyncGenerator
from argus.services.athena_service import AthenaService


async def query_status_stream(
    query_execution_id: str,
    athena_service: AthenaService,
    poll_interval: float = 1.5,
) -> AsyncGenerator[dict, None]:
    """Yield SSE events with query status updates until terminal state."""
    terminal_states = {"SUCCEEDED", "FAILED", "CANCELLED"}
    while True:
        try:
            resp = athena_service.get_query_execution(query_execution_id)
            qe = resp["QueryExecution"]
            status = qe["Status"]
            state = status["State"]
            stats = qe.get("Statistics", {})
            event_data = {
                "query_execution_id": query_execution_id,
                "state": state,
                "state_change_reason": status.get("StateChangeReason"),
                "data_scanned_bytes": stats.get("DataScannedInBytes"),
                "total_execution_time_ms": stats.get("TotalExecutionTimeInMillis"),
            }
            yield event_data
            if state in terminal_states:
                break
        except Exception as e:
            yield {"error": str(e), "state": "ERROR"}
            break
        await asyncio.sleep(poll_interval)
