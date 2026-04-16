from __future__ import annotations
import io
import json
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from athena_beaver.api.schemas import ExportRequest
from athena_beaver.api.dependencies import get_athena_service
from athena_beaver.services.athena_service import AthenaService

router = APIRouter(prefix="/export", tags=["export"])

MIME_TYPES = {
    "csv": "text/csv",
    "json": "application/json",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "parquet": "application/octet-stream",
}

EXTENSIONS = {
    "csv": "csv",
    "json": "json",
    "xlsx": "xlsx",
    "parquet": "parquet",
}


def _fetch_all_results(svc: AthenaService, query_id: str) -> tuple[list[str], list[list[str]]]:
    """Fetch all pages of query results. Returns (headers, rows)."""
    headers: list[str] = []
    rows: list[list[str]] = []
    next_token = None
    first = True

    while True:
        resp = svc.get_query_results(query_id, max_results=1000, next_token=next_token)
        result_set = resp.get("ResultSet", {})
        raw_rows = result_set.get("Rows", [])

        if first and raw_rows:
            headers = [cell.get("VarCharValue", "") for cell in raw_rows[0].get("Data", [])]
            raw_rows = raw_rows[1:]
            first = False

        for row in raw_rows:
            rows.append([cell.get("VarCharValue", "") for cell in row.get("Data", [])])

        next_token = resp.get("NextToken")
        if not next_token:
            break

    return headers, rows


@router.post("/{query_id}")
def export_results(
    query_id: str,
    body: ExportRequest,
    svc: Annotated[AthenaService, Depends(get_athena_service)],
):
    fmt = body.format.lower()
    if fmt not in MIME_TYPES:
        raise HTTPException(status_code=400, detail=f"Unsupported format: {fmt}. Use csv, json, xlsx, or parquet.")

    try:
        headers, rows = _fetch_all_results(svc, query_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    filename = f"query_{query_id[:8]}.{EXTENSIONS[fmt]}"

    if fmt == "csv":
        import csv
        buf = io.StringIO()
        writer = csv.writer(buf, delimiter=body.delimiter)
        writer.writerow(headers)
        writer.writerows(rows)
        content = buf.getvalue().encode("utf-8")
        return StreamingResponse(
            io.BytesIO(content),
            media_type=MIME_TYPES[fmt],
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    elif fmt == "json":
        data = [dict(zip(headers, row)) for row in rows]
        if body.pretty:
            content = json.dumps(data, indent=2).encode("utf-8")
        else:
            content = json.dumps(data).encode("utf-8")
        return StreamingResponse(
            io.BytesIO(content),
            media_type=MIME_TYPES[fmt],
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    elif fmt == "xlsx":
        import pandas as pd
        df = pd.DataFrame(rows, columns=headers)
        buf = io.BytesIO()
        df.to_excel(buf, index=False, engine="openpyxl")
        buf.seek(0)
        return StreamingResponse(
            buf,
            media_type=MIME_TYPES[fmt],
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    elif fmt == "parquet":
        import pandas as pd
        df = pd.DataFrame(rows, columns=headers)
        buf = io.BytesIO()
        df.to_parquet(buf, index=False, engine="pyarrow")
        buf.seek(0)
        return StreamingResponse(
            buf,
            media_type=MIME_TYPES[fmt],
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
