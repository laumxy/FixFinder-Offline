"""
Report Generator — produces JSON, CSV, and plain-text diagnostic reports.

PDF generation requires 'reportlab' which is optional. If not installed,
PDF requests fall back to plain-text. All other formats use stdlib only.
"""
from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.database.db import (
    fetch_analytics_summary,
    fetch_reports,
    get_connection,
    insert_report,
)
from app.utils.logger import get_logger
from fixfinder_engine.config import settings


logger = get_logger(__name__)


class ReportGenerator:
    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or settings.database_path
        self.reports_dir = settings.reports_dir
        self.reports_dir.mkdir(parents=True, exist_ok=True)

    # ── Diagnostic Report ─────────────────────────────────────────────────────

    def create_diagnostic_report(
        self,
        diagnosis: dict[str, Any],
        fmt: str = "json",
        user_id: int | None = None,
        organization_id: int | None = None,
        save: bool = True,
    ) -> dict[str, Any]:
        title = f"Diagnostic: {diagnosis.get('problem', 'Unknown')} [{diagnosis.get('category', '')}]"
        content = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "category": diagnosis.get("category"),
            "problem": diagnosis.get("problem"),
            "top_cause": diagnosis.get("ranked_causes", ["unknown"])[0] if diagnosis.get("ranked_causes") else "unknown",
            "confidence": (
                diagnosis.get("confidence_scores", [{}])[0].get("confidence", "0%")
                if diagnosis.get("confidence_scores") else "0%"
            ),
            "repair_steps": diagnosis.get("repair_steps", []),
            "tools": diagnosis.get("tools", []),
            "safety": diagnosis.get("safety", []),
            "final_answer": diagnosis.get("final_answer", ""),
        }

        if fmt == "csv":
            rendered = self._to_csv([content])
        elif fmt == "txt":
            rendered = self._to_text(content)
        elif fmt == "pdf":
            rendered = self._to_pdf(title, content)
        else:
            rendered = json.dumps(content, indent=2, ensure_ascii=False)

        report_id = None
        file_path = ""
        if save:
            ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            fname = f"diagnostic_{ts}.{fmt}"
            fpath = self.reports_dir / fname
            fpath.write_text(rendered, encoding="utf-8")
            file_path = str(fpath)
            report_id = insert_report(
                self.db_path,
                report_type="diagnostic",
                title=title,
                content=content,
                fmt=fmt,
                file_path=file_path,
                user_id=user_id,
                organization_id=organization_id,
            )

        return {
            "report_id": report_id,
            "title": title,
            "format": fmt,
            "file_path": file_path,
            "content": content,
            "rendered": rendered,
        }

    # ── Analytics Report ──────────────────────────────────────────────────────

    def create_analytics_report(
        self,
        fmt: str = "json",
        user_id: int | None = None,
        organization_id: int | None = None,
        save: bool = True,
    ) -> dict[str, Any]:
        summary = fetch_analytics_summary(self.db_path)
        title = f"Analytics Summary — {datetime.now(timezone.utc).strftime('%Y-%m-%d')}"

        if fmt == "csv":
            rows = summary.get("top_categories", [])
            rendered = self._to_csv(rows)
        elif fmt == "txt":
            rendered = self._analytics_to_text(summary)
        else:
            rendered = json.dumps(summary, indent=2, ensure_ascii=False)

        report_id = None
        file_path = ""
        if save:
            ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            fname = f"analytics_{ts}.{fmt}"
            fpath = self.reports_dir / fname
            fpath.write_text(rendered, encoding="utf-8")
            file_path = str(fpath)
            report_id = insert_report(
                self.db_path,
                report_type="analytics",
                title=title,
                content=summary,
                fmt=fmt,
                file_path=file_path,
                user_id=user_id,
                organization_id=organization_id,
            )

        return {
            "report_id": report_id,
            "title": title,
            "format": fmt,
            "file_path": file_path,
            "content": summary,
        }

    # ── Workshop Report ───────────────────────────────────────────────────────

    def create_workshop_report(
        self,
        jobs: list[dict[str, Any]],
        summary: dict[str, Any],
        fmt: str = "json",
        user_id: int | None = None,
        organization_id: int | None = None,
        save: bool = True,
    ) -> dict[str, Any]:
        title = f"Workshop Report — {datetime.now(timezone.utc).strftime('%Y-%m-%d')}"
        content = {"summary": summary, "jobs": jobs}

        if fmt == "csv":
            flat = [
                {
                    "job_id": j["id"],
                    "customer_id": j["customer_id"],
                    "category": j["category"],
                    "status": j["status"],
                    "actual_cost": j["actual_cost"],
                    "opened_at": j["opened_at"],
                    "closed_at": j.get("closed_at", ""),
                }
                for j in jobs
            ]
            rendered = self._to_csv(flat)
        elif fmt == "txt":
            rendered = self._workshop_to_text(summary, jobs)
        else:
            rendered = json.dumps(content, indent=2, ensure_ascii=False)

        report_id = None
        file_path = ""
        if save:
            ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            fname = f"workshop_{ts}.{fmt}"
            fpath = self.reports_dir / fname
            fpath.write_text(rendered, encoding="utf-8")
            file_path = str(fpath)
            report_id = insert_report(
                self.db_path,
                report_type="workshop",
                title=title,
                content=content,
                fmt=fmt,
                file_path=file_path,
                user_id=user_id,
                organization_id=organization_id,
            )

        return {
            "report_id": report_id,
            "title": title,
            "format": fmt,
            "file_path": file_path,
            "content": content,
        }

    # ── Fetch saved reports ───────────────────────────────────────────────────

    def list_reports(
        self,
        report_type: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        return fetch_reports(self.db_path, report_type=report_type, limit=limit)

    # ── Renderers ─────────────────────────────────────────────────────────────

    @staticmethod
    def _to_csv(rows: list[dict[str, Any]]) -> str:
        if not rows:
            return ""
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()), extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
        return buf.getvalue()

    @staticmethod
    def _to_text(content: dict[str, Any]) -> str:
        lines = [
            f"FIXFINDER DIAGNOSTIC REPORT",
            f"Generated: {content.get('generated_at', '')}",
            "=" * 60,
            f"Category:   {content.get('category', '')}",
            f"Problem:    {content.get('problem', '')}",
            f"Top Cause:  {content.get('top_cause', '')}",
            f"Confidence: {content.get('confidence', '')}",
            "",
            "REPAIR STEPS:",
        ]
        for i, step in enumerate(content.get("repair_steps", []), 1):
            lines.append(f"  {i}. {step}")
        lines += ["", "SAFETY WARNINGS:"]
        for w in content.get("safety", []):
            lines.append(f"  • {w}")
        lines += ["", "FINAL ANSWER:", content.get("final_answer", ""), ""]
        return "\n".join(lines)

    @staticmethod
    def _analytics_to_text(summary: dict[str, Any]) -> str:
        lines = [
            "FIXFINDER ANALYTICS REPORT",
            f"Total Events:       {summary.get('total_events', 0)}",
            f"Average Confidence: {summary.get('average_confidence', 0)}%",
            "",
            "TOP CATEGORIES:",
        ]
        for cat in summary.get("top_categories", []):
            lines.append(f"  {cat['category']:<20} {cat['count']} diagnoses")
        lines += ["", "EVENTS BY TYPE:"]
        for ev in summary.get("events_by_type", []):
            lines.append(f"  {ev['event_type']:<20} {ev['count']}")
        return "\n".join(lines)

    @staticmethod
    def _workshop_to_text(summary: dict[str, Any], jobs: list[dict]) -> str:
        lines = [
            "FIXFINDER WORKSHOP REPORT",
            f"Total Jobs:    {summary.get('total_jobs', 0)}",
            f"Open Jobs:     {summary.get('open_jobs', 0)}",
            f"Closed Jobs:   {summary.get('closed_jobs', 0)}",
            f"Total Revenue: {summary.get('total_revenue', 0)}",
            "",
            "RECENT JOBS:",
        ]
        for j in jobs[:20]:
            lines.append(
                f"  #{j['id']}  [{j['status']}]  {j['category']}  "
                f"Cost:{j['actual_cost']}  Opened:{j['opened_at'][:10]}"
            )
        return "\n".join(lines)

    def _to_pdf(self, title: str, content: dict[str, Any]) -> str:
        """Generate a PDF using reportlab if available, else fall back to text."""
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.styles import getSampleStyleSheet
            from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
            from reportlab.lib.units import cm

            ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            pdf_path = self.reports_dir / f"report_{ts}.pdf"
            doc = SimpleDocTemplate(str(pdf_path), pagesize=A4)
            styles = getSampleStyleSheet()
            story = [
                Paragraph(title, styles["Title"]),
                Spacer(1, 0.5 * cm),
                Paragraph(f"Category: {content.get('category', '')}", styles["Normal"]),
                Paragraph(f"Problem: {content.get('problem', '')}", styles["Normal"]),
                Paragraph(f"Confidence: {content.get('confidence', '')}", styles["Normal"]),
                Spacer(1, 0.3 * cm),
                Paragraph("Repair Steps:", styles["Heading2"]),
            ]
            for step in content.get("repair_steps", []):
                story.append(Paragraph(f"• {step}", styles["Normal"]))
            story += [
                Spacer(1, 0.3 * cm),
                Paragraph("Safety:", styles["Heading2"]),
            ]
            for warn in content.get("safety", []):
                story.append(Paragraph(f"• {warn}", styles["Normal"]))
            story += [
                Spacer(1, 0.3 * cm),
                Paragraph("Final Answer:", styles["Heading2"]),
                Paragraph(content.get("final_answer", ""), styles["Normal"]),
            ]
            doc.build(story)
            return str(pdf_path)
        except ImportError:
            logger.info("reportlab not installed — falling back to plain text for PDF request.")
            return self._to_text(content)
