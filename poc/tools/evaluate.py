"""Evaluation pipeline for the resume prompt-injection detector.

Usage:
    python poc/tools/evaluate.py --clean_dir examples/pdfs/clean --injected_dir examples/pdfs/injected --out results.csv

The script runs the full detector pipeline on all PDFs in the two directories
and exports per-file results and aggregate metrics (precision/recall/F1/confusion).
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import os
from typing import Dict, Any, List
from statistics import mean

from poc.detector.pdf_parser import PDFParser
from poc.detector.renderer import PDFRenderer
from poc.detector.ocr import OCRClient
from poc.detector.discrepancy import DiscrepancyEngine
from poc.detector.llm_verifier import LLMVerifier
from poc.detector.risk_engine import RiskEngine

from sklearn.metrics import precision_recall_fscore_support, confusion_matrix


async def analyze_file(path: str, parser: PDFParser, renderer: PDFRenderer, ocr: OCRClient, discrepancy: DiscrepancyEngine, llm: LLMVerifier, risk_engine: RiskEngine, threshold: float = 50.0) -> Dict[str, Any]:
    """Run full pipeline for a single file and return structured result."""
    result: Dict[str, Any] = {"file": path, "error": None}
    try:
        with open(path, "rb") as f:
            data = f.read()

        parsed = await asyncio.to_thread(parser.parse, data)
        page_count = parsed.get("metadata", {}).get("page_count", 0)
        page_img = b""
        if page_count > 0:
            page_img = await asyncio.to_thread(renderer.render_page, data, 0)

        ocr_res = {"text": "", "confidence": 0.0}
        if page_img:
            ocr_res = await ocr.analyze_image(page_img)

        discrepancies = await asyncio.to_thread(discrepancy.analyze, parsed, ocr_res)

        llm_result = await llm.verify({"parsed": parsed, "discrepancies": discrepancies, "ocr": ocr_res, "rendered_image": page_img})

        # Build risk input similar to API
        suspicious_segments = discrepancies.get("suspicious_segments", []) or []
        hidden_text_score = 100.0 if any(s.get("type") in ("missing_in_ocr", "different_in_ocr") for s in suspicious_segments) else 0.0
        page_anomalies = parsed.get("metadata", {}).get("page_anomalies", [])
        pdf_anomaly_score = 0.0
        if page_anomalies:
            vals = []
            for pa in page_anomalies:
                vals.append(1.0 if pa.get("very_small_font") or pa.get("white_text_detected") or pa.get("text_outside_page") else 0.0)
            pdf_anomaly_score = mean(vals) * 100.0

        ocr_discrepancy_score = float(discrepancies.get("discrepancy_score", 0))
        llm_score = float(llm_result.get("confidence", 0.0)) * 100.0 if isinstance(llm_result, dict) else 0.0

        risk_input = {
            "hidden_text_score": hidden_text_score,
            "ocr_discrepancy_score": ocr_discrepancy_score,
            "pdf_anomaly_score": pdf_anomaly_score,
            "llm_score": llm_score,
        }

        risk = await asyncio.to_thread(risk_engine.score, risk_input)

        predicted = 1 if (risk.get("risk_score", 0.0) >= threshold) else 0

        result.update({
            "parsed": parsed,
            "ocr": ocr_res,
            "discrepancies": discrepancies,
            "llm": llm_result,
            "risk": risk,
            "predicted": predicted,
        })
    except Exception as e:
        result["error"] = str(e)
    return result


async def run_evaluation(clean_dir: str, injected_dir: str, out_csv: str, concurrency: int = 4, threshold: float = 50.0) -> None:
    parser = PDFParser()
    renderer = PDFRenderer()
    ocr = OCRClient()
    discrepancy = DiscrepancyEngine()
    llm = LLMVerifier()
    risk_engine = RiskEngine()

    files: List[Dict[str, Any]] = []
    for d, label in ((clean_dir, 0), (injected_dir, 1)):
        if not d:
            continue
        for fname in os.listdir(d):
            if not fname.lower().endswith(".pdf"):
                continue
            files.append({"path": os.path.join(d, fname), "label": label})

    semaphore = asyncio.Semaphore(concurrency)

    async def sem_task(f):
        async with semaphore:
            return await analyze_file(f["path"], parser, renderer, ocr, discrepancy, llm, risk_engine, threshold)

    tasks = [sem_task(f) for f in files]
    results = await asyncio.gather(*tasks)

    # Combine predictions with ground truth
    y_true: List[int] = []
    y_pred: List[int] = []
    rows = []
    for i, res in enumerate(results):
        label = files[i]["label"]
        pred = res.get("predicted", 0) if res.get("error") is None else 0
        y_true.append(label)
        y_pred.append(pred)
        risk_score = res.get("risk", {}).get("risk_score") if res.get("risk") else None
        severity = res.get("risk", {}).get("severity") if res.get("risk") else None
        llm_conf = res.get("llm", {}).get("confidence") if isinstance(res.get("llm"), dict) else None
        discrepancies = res.get("discrepancies", {})
        rows.append({
            "file": res.get("file") or files[i]["path"],
            "true_label": label,
            "predicted_label": pred,
            "risk_score": risk_score,
            "severity": severity,
            "llm_confidence": llm_conf,
            "discrepancy_score": discrepancies.get("discrepancy_score") if discrepancies else None,
            "hidden_text_detected": discrepancies.get("suspicious_segments") if discrepancies else None,
            "error": res.get("error"),
        })

    # compute metrics
    precision, recall, f1, _ = precision_recall_fscore_support(y_true, y_pred, average="binary", zero_division=0)
    cm = confusion_matrix(y_true, y_pred)

    # write CSV with per-file rows then summary
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        header = ["file", "true_label", "predicted_label", "risk_score", "severity", "llm_confidence", "discrepancy_score", "hidden_text_detected", "error"]
        writer.writerow(header)
        for r in rows:
            writer.writerow([r.get(h) for h in header])

        # blank line and summary
        writer.writerow([])
        writer.writerow(["metric", "value"])
        writer.writerow(["precision", precision])
        writer.writerow(["recall", recall])
        writer.writerow(["f1", f1])
        writer.writerow(["confusion_matrix", str(cm.tolist())])

    print("Evaluation complete")
    print(f"precision={precision:.3f} recall={recall:.3f} f1={f1:.3f}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--clean_dir", default=None)
    ap.add_argument("--injected_dir", default=None)
    ap.add_argument("--out", required=True)
    ap.add_argument("--concurrency", type=int, default=4)
    ap.add_argument("--threshold", type=float, default=50.0, help="Risk score threshold for suspicious classification (0-100)")
    args = ap.parse_args()

    asyncio.run(run_evaluation(args.clean_dir, args.injected_dir, args.out, args.concurrency, args.threshold))


if __name__ == "__main__":
    main()
