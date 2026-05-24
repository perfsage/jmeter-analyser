"""Generates synthetic JTL/CSV files for testing across JMeter versions.

Usage:
    from tests.fixtures.generate_jtl import make_csv_jtl, make_xml_jtl
"""

from __future__ import annotations

import csv
import io
from typing import Literal

JMeterVersion = Literal["2.x", "3.x", "4.x", "5.x", "5.6"]

# Base epoch-ms timestamp: 2023-11-14 22:13:20 UTC
_BASE_TS = 1_700_000_000_000

# ─── CSV format ──────────────────────────────────────────────────────────────

_HEADERS: dict[JMeterVersion, list[str]] = {
    "2.x": [
        "timeStamp", "elapsed", "label", "responseCode", "responseMessage",
        "threadName", "dataType", "success", "bytes",
    ],
    "3.x": [
        "timeStamp", "elapsed", "label", "responseCode", "responseMessage",
        "threadName", "dataType", "success", "bytes",
        "sentBytes", "grpThreads", "allThreads", "URL", "Latency", "IdleTime", "Connect",
    ],
    "4.x": [
        "timeStamp", "elapsed", "label", "responseCode", "responseMessage",
        "threadName", "dataType", "success", "failureMessage", "bytes",
        "sentBytes", "grpThreads", "allThreads", "URL", "Latency", "IdleTime", "Connect",
    ],
    "5.x": [
        "timeStamp", "elapsed", "label", "responseCode", "responseMessage",
        "threadName", "dataType", "success", "failureMessage", "bytes",
        "sentBytes", "grpThreads", "allThreads", "URL", "Latency", "IdleTime", "Connect",
    ],
    "5.6": [
        "timeStamp", "elapsed", "label", "responseCode", "responseMessage",
        "threadName", "dataType", "success", "failureMessage", "bytes",
        "sentBytes", "grpThreads", "allThreads", "URL", "latency", "IdleTime", "Connect",
    ],
}

_ALL_FIELDS: list[str] = [
    "timeStamp", "elapsed", "label", "responseCode", "responseMessage",
    "threadName", "dataType", "success", "failureMessage", "bytes",
    "sentBytes", "grpThreads", "allThreads", "URL", "Latency", "latency",
    "IdleTime", "Connect",
]


def _make_row(index: int, include_errors: bool, headers: list[str]) -> dict[str, str]:
    is_error = include_errors and (index % 5 == 0)
    values: dict[str, str] = {
        "timeStamp": str(_BASE_TS + index * 1000),
        "elapsed": str(100 + index % 900),
        "label": f"Transaction {index % 5 + 1}",
        "responseCode": "500" if is_error else "200",
        "responseMessage": "Internal Server Error" if is_error else "OK",
        "threadName": f"Thread Group 1-{(index % 10) + 1}",
        "dataType": "text",
        "success": "false" if is_error else "true",
        "failureMessage": "Connection refused" if is_error else "",
        "bytes": str(1024 + index % 4096),
        "sentBytes": str(256 + index % 512),
        "grpThreads": str((index % 50) + 1),
        "allThreads": str((index % 100) + 1),
        "URL": f"http://example.com/api/endpoint{index % 5}",
        "Latency": str(80 + index % 100),
        "latency": str(80 + index % 100),
        "IdleTime": "0",
        "Connect": str(10 + index % 50),
    }
    return {h: values.get(h, "") for h in headers}


def make_csv_jtl(
    n_rows: int = 100,
    version: JMeterVersion = "5.6",
    include_errors: bool = False,
    delimiter: str = ",",
    has_header: bool = True,
) -> str:
    """Return CSV JTL content as a string."""
    headers = _HEADERS[version]
    buf = io.StringIO()
    writer = csv.DictWriter(
        buf,
        fieldnames=headers,
        delimiter=delimiter,
        lineterminator="\n",
    )
    if has_header:
        writer.writeheader()
    for i in range(n_rows):
        writer.writerow(_make_row(i, include_errors, headers))
    return buf.getvalue()


# ─── XML format ──────────────────────────────────────────────────────────────


def make_xml_jtl(
    n_rows: int = 100,
    version: JMeterVersion = "5.6",
    include_errors: bool = False,
) -> str:
    """Return XML JTL content as a string."""
    lines: list[str] = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<testResults version="1.2">',
    ]
    for i in range(n_rows):
        is_error = include_errors and (i % 5 == 0)
        ts = _BASE_TS + i * 1000
        elapsed = 100 + i % 900
        latency = 80 + i % 100
        connect = 10 + i % 50
        by = 1024 + i % 4096
        sby = 256 + i % 512
        grp = (i % 50) + 1
        na = (i % 100) + 1
        success = "false" if is_error else "true"
        rc = "500" if is_error else "200"
        rm = "Internal Server Error" if is_error else "OK"
        label = f"Transaction {i % 5 + 1}"
        tn = f"Thread Group 1-{(i % 10) + 1}"

        attrs = (
            f't="{elapsed}" lt="{latency}" ct="{connect}" ts="{ts}" '
            f's="{success}" lb="{label}" rc="{rc}" rm="{rm}" '
            f'tn="{tn}" dt="text" by="{by}" sby="{sby}" '
            f'ng="{grp}" na="{na}"'
        )
        tag = "httpSample" if i % 2 == 0 else "sample"
        if is_error:
            lines.append(f"  <{tag} {attrs}>")
            lines.append(
                "    <failureMessage>Connection refused</failureMessage>"
            )
            lines.append(f"  </{tag}>")
        else:
            lines.append(f"  <{tag} {attrs}/>")
    lines.append("</testResults>")
    return "\n".join(lines)
