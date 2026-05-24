"""arq background task: full JMeter file ingestion pipeline."""

from __future__ import annotations

import json
import time
from datetime import UTC, datetime
from pathlib import Path

import duckdb

from perfsage.config import get_settings
from perfsage.core.parsing.csv_loader import load_csv_to_parquet
from perfsage.core.parsing.detect import JTLFormat, detect_csv_delimiter, detect_format
from perfsage.core.parsing.xml_loader import load_xml_to_parquet
from perfsage.core.storage.db import Job, JobStatus, Report, ReportStatus, get_engine, get_session
from perfsage.core.storage.files import FileStore
from perfsage.core.storage.repos import JobRepo, ReportRepo


async def ingest_report_task(
    ctx: dict[str, object],
    job_id: str,
    report_id: str,
    upload_path: str,
    delimiter: str = ",",
) -> None:
    """Main ingestion pipeline executed by the arq worker.

    Phases: detect → parse → aggregate → done
    Emits progress via Redis pubsub channel ``job:{job_id}``.
    Also persists progress to the Job row after each phase.
    """
    from arq.connections import ArqRedis

    redis: ArqRedis = ctx["redis"]  # type: ignore[assignment]
    settings = get_settings()
    engine = get_engine(settings.database_url)
    fs = FileStore(settings.data_dir)

    async def emit(pct: float, phase: str, message: str = "") -> None:
        payload = json.dumps({"pct": pct, "phase": phase, "message": message})
        await redis.publish(f"job:{job_id}", payload)
        with get_session(engine) as session:
            JobRepo(session).update_progress(job_id, pct, phase, message)

    start = time.monotonic()
    src = Path(upload_path)

    try:
        await emit(5, "detect", "Detecting file format...")
        fmt = detect_format(src)
        if fmt == JTLFormat.UNKNOWN:
            raise ValueError(f"Unknown file format for {src.name!r}; expected CSV or XML JTL")
        await emit(10, "detect", f"Detected format: {fmt.value}")

        samples_path = fs.samples_parquet(report_id)
        quarantine_path = fs.quarantine_parquet(report_id)
        samples_path.parent.mkdir(parents=True, exist_ok=True)

        await emit(15, "parse", "Parsing samples...")

        if fmt == JTLFormat.CSV:
            eff_delimiter = detect_csv_delimiter(src) if delimiter == "," else delimiter
            parsed_rows, error_rows = load_csv_to_parquet(
                src, samples_path, quarantine_path, delimiter=eff_delimiter
            )
        else:
            parsed_rows, error_rows = load_xml_to_parquet(src, samples_path, quarantine_path)

        with get_session(engine) as session:
            ReportRepo(session).update_stats(
                report_id,
                parsed_row_count=parsed_rows,
                error_row_count=error_rows,
                row_count=parsed_rows + error_rows,
                status=ReportStatus.PROCESSING,
            )

        await emit(80, "aggregate", "Computing aggregates...")
        agg_path = fs.agg_parquet(report_id, "summary")
        _compute_aggregates(samples_path, agg_path)

        duration = time.monotonic() - start
        with get_session(engine) as session:
            report = session.get(Report, report_id)
            if report:
                report.status = ReportStatus.READY
                report.duration_seconds = duration
            job = session.get(Job, job_id)
            if job:
                job.status = JobStatus.DONE
                job.ended_at = datetime.now(UTC)
                job.progress_pct = 100.0
                job.phase = "done"
            session.commit()

        src.unlink(missing_ok=True)
        await emit(100, "done", "Analysis complete")

    except Exception as exc:
        error_msg = str(exc)
        await redis.publish(
            f"job:{job_id}",
            json.dumps({"pct": 0, "phase": "error", "message": error_msg}),
        )
        with get_session(engine) as session:
            JobRepo(session).mark_failed(job_id, error_msg)
            ReportRepo(session).update_status(report_id, ReportStatus.FAILED)
        raise


def _compute_aggregates(samples_path: Path, agg_path: Path) -> None:
    """Compute per-label aggregate statistics from the samples parquet.

    Output columns: label, count, mean_elapsed, p50, p90, p95, p99,
                    error_rate, min_elapsed, max_elapsed
    """
    agg_path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    try:
        # Check which columns are available before running aggregate query.
        schema_df = con.execute(
            f"DESCRIBE SELECT * FROM read_parquet('{samples_path!s}') LIMIT 0"
        ).df()
        available = set(schema_df["column_name"].tolist()) if not schema_df.empty else set()

        if "elapsed" not in available or "label" not in available:
            # Write an empty aggregate parquet with the expected schema.
            import polars as pl

            pl.DataFrame(
                {
                    "label": pl.Series([], dtype=pl.Utf8),
                    "count": pl.Series([], dtype=pl.Int64),
                    "mean_elapsed": pl.Series([], dtype=pl.Float64),
                    "p50": pl.Series([], dtype=pl.Float64),
                    "p90": pl.Series([], dtype=pl.Float64),
                    "p95": pl.Series([], dtype=pl.Float64),
                    "p99": pl.Series([], dtype=pl.Float64),
                    "error_rate": pl.Series([], dtype=pl.Float64),
                    "min_elapsed": pl.Series([], dtype=pl.Int64),
                    "max_elapsed": pl.Series([], dtype=pl.Int64),
                }
            ).write_parquet(agg_path)
            return

        success_expr = (
            "avg(CASE WHEN success = false THEN 1.0 ELSE 0.0 END)::DOUBLE"
            if "success" in available
            else "0.0::DOUBLE"
        )

        con.execute(f"""
            COPY (
                SELECT
                    label,
                    count(*)::BIGINT                                     AS count,
                    avg(elapsed)::DOUBLE                                  AS mean_elapsed,
                    quantile_cont(elapsed, 0.50)::DOUBLE                  AS p50,
                    quantile_cont(elapsed, 0.90)::DOUBLE                  AS p90,
                    quantile_cont(elapsed, 0.95)::DOUBLE                  AS p95,
                    quantile_cont(elapsed, 0.99)::DOUBLE                  AS p99,
                    {success_expr}                                        AS error_rate,
                    min(elapsed)::BIGINT                                  AS min_elapsed,
                    max(elapsed)::BIGINT                                  AS max_elapsed
                FROM read_parquet('{samples_path!s}')
                GROUP BY label
            ) TO '{agg_path!s}' (FORMAT PARQUET)
        """)
    except Exception:
        # Safety net: if DuckDB query fails (e.g. empty file), write empty schema.
        import polars as pl

        pl.DataFrame(
            {
                "label": pl.Series([], dtype=pl.Utf8),
                "count": pl.Series([], dtype=pl.Int64),
                "mean_elapsed": pl.Series([], dtype=pl.Float64),
                "p50": pl.Series([], dtype=pl.Float64),
                "p90": pl.Series([], dtype=pl.Float64),
                "p95": pl.Series([], dtype=pl.Float64),
                "p99": pl.Series([], dtype=pl.Float64),
                "error_rate": pl.Series([], dtype=pl.Float64),
                "min_elapsed": pl.Series([], dtype=pl.Int64),
                "max_elapsed": pl.Series([], dtype=pl.Int64),
            }
        ).write_parquet(agg_path)
    finally:
        con.close()
