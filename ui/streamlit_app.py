import os
import io
import csv
import json
import time
import requests
import streamlit as st
from datetime import datetime

API_URL = os.environ.get("API_URL", "http://api:8000")

st.set_page_config(page_title="Resume Injection Detector", layout="centered")

st.title("Resume Prompt-Injection Detector")
# Visible version banner to confirm updated code is running
st.markdown(f"**UI version:** updated {datetime.utcnow().isoformat()} UTC")

st.markdown("Upload PDF(s) to analyze or run a batch evaluation with a CSV of true labels.")

mode = st.radio("Mode", ["Single file analysis", "Batch evaluation"])

col1, col2 = st.columns([3, 1])
with col1:
    st.markdown("Upload PDF(s) or run a batch evaluation below.")
with col2:
    threshold = st.slider("Risk threshold", 0, 100, 50)
    st.caption("Files with risk_score >= threshold are classified as suspicious.")

def analyze_bytes(name, data, timeout=120):
    files = {"file": (name, io.BytesIO(data), "application/pdf")}
    with st.spinner(f"Analyzing {name}..."):
        resp = requests.post(f"{API_URL}/analyze", files=files, timeout=timeout)
    if resp.status_code != 200:
        raise RuntimeError(f"API error {resp.status_code}: {resp.text}")
    return resp.json()

if mode == "Single file analysis":
    uploaded = st.file_uploader("Choose a PDF file", type=["pdf"])
    if 'uploaded' in locals() and uploaded is not None:
        if hasattr(uploaded, "read"):
            data = uploaded.read()
            name = getattr(uploaded, "name", "uploaded.pdf")
        else:
            data = uploaded.read()
            name = os.path.basename(uploaded.name)

        st.subheader(f"File: {name}")
        # Optional ground-truth label for single-file evaluation
        true_label_choice = st.selectbox("True label (optional)", ["Unknown", "Clean (0)", "Injected (1)"], index=0)
        true_label = None
        if true_label_choice == "Clean (0)":
            true_label = 0
        elif true_label_choice == "Injected (1)":
            true_label = 1
        try:
            result = analyze_bytes(name, data)
            st.success("Analysis complete")
            risk = result.get("risk", {})
            llm = result.get("llm_verification", {})
            disc = result.get("discrepancies", {})

            # Prominent risk display
            st.markdown("### Risk Score")
            st.markdown(f"## **{risk.get('risk_score', 'N/A')}**")
            st.write("**Severity:**", risk.get("severity"))
            st.write("**LLM Suspicious:**", llm.get("suspicious"))
            st.write("**LLM confidence:**", llm.get("confidence"))

            st.subheader("Discrepancy diff")
            text_diff = disc.get("text_diff") if disc else None
            if text_diff:
                st.code(text_diff, language="diff")
            else:
                st.write("No text diff available.")

            st.subheader("Suspicious segments / details")
            ss = disc.get("suspicious_segments")
            st.write(ss if ss else "None")

            with st.expander("Full JSON response"):
                st.json(result)

            # Maintain evaluation history in session state
            if 'eval_history' not in st.session_state:
                st.session_state.eval_history = []

            if true_label is not None:
                # append current result to history
                st.session_state.eval_history.append({
                    'file': name,
                    'risk': risk.get('risk_score', 0),
                    'pred': 1 if risk.get('risk_score', 0) >= threshold else 0,
                    'true': true_label
                })

            # If we have any history, compute aggregated metrics
            if st.session_state.get('eval_history'):
                hist = st.session_state.eval_history
                tp = fp = tn = fn = 0
                for r in hist:
                    t = r.get('true')
                    p = r.get('pred')
                    if t == 1 and p == 1:
                        tp += 1
                    elif t == 0 and p == 1:
                        fp += 1
                    elif t == 1 and p == 0:
                        fn += 1
                    elif t == 0 and p == 0:
                        tn += 1

                def safe_div(a, b):
                    return a / b if b else 0.0

                precision = safe_div(tp, tp + fp)
                recall = safe_div(tp, tp + fn)
                f1 = safe_div(2 * precision * recall, precision + recall) if (precision + recall) else 0.0

                st.markdown("---")
                st.subheader("Session evaluation (aggregated)")
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("True Positives", tp)
                c2.metric("False Positives", fp)
                c3.metric("True Negatives", tn)
                c4.metric("False Negatives", fn)

                p1, p2, p3 = st.columns(3)
                p1.metric("Precision", f"{round(precision,4)}")
                p2.metric("Recall", f"{round(recall,4)}")
                p3.metric("F1 Score", f"{round(f1,4)}")

                st.subheader("Session per-file history")
                st.table(hist)

                if st.button("Clear session history"):
                    st.session_state.eval_history = []
        except Exception as e:
            st.error(f"Request failed: {e}")
    else:
        st.info("Upload a PDF to begin analysis.")

else:  # Batch evaluation
    st.markdown("Upload multiple PDFs (select all) and a CSV mapping filenames to labels. CSV format: filename,label (0=clean,1=injected)")
    uploaded_files = st.file_uploader("Choose PDF files", type=["pdf"], accept_multiple_files=True)
    labels_file = st.file_uploader("Upload labels CSV", type=["csv"])

    if st.button("Run evaluation"):
        if not uploaded_files:
            st.error("No PDF files uploaded for evaluation.")
        elif not labels_file:
            st.error("No labels CSV uploaded. Provide a CSV with columns: filename,label")
        else:
            # parse labels
            try:
                labels_text = labels_file.getvalue().decode("utf-8")
                reader = csv.reader(io.StringIO(labels_text))
                labels_map = {}
                for row in reader:
                    if not row:
                        continue
                    if len(row) < 2:
                        continue
                    fname = row[0].strip()
                    lbl = int(row[1])
                    labels_map[fname] = lbl
            except Exception as e:
                st.error(f"Failed to parse labels CSV: {e}")
                labels_map = {}

            results = []
            tp = fp = tn = fn = 0
            progress = st.progress(0)
            total = len(uploaded_files)
            for idx, f in enumerate(uploaded_files):
                name = getattr(f, "name", f"file_{idx}.pdf")
                data = f.read()
                try:
                    res = analyze_bytes(name, data, timeout=300)
                    risk = res.get("risk", {}).get("risk_score", 0)
                    pred = 1 if risk >= threshold else 0
                    true = labels_map.get(name)
                    if true is None:
                        # try basename without path
                        true = labels_map.get(os.path.basename(name))
                    if true is None:
                        results.append({"file": name, "error": "label_missing", "risk": risk, "pred": pred})
                    else:
                        results.append({"file": name, "risk": risk, "pred": pred, "true": true})
                        if true == 1 and pred == 1:
                            tp += 1
                        elif true == 0 and pred == 1:
                            fp += 1
                        elif true == 1 and pred == 0:
                            fn += 1
                        elif true == 0 and pred == 0:
                            tn += 1
                except Exception as e:
                    results.append({"file": name, "error": str(e)})
                progress.progress(int((idx + 1) / total * 100))
                time.sleep(0.1)

            # compute metrics
            def safe_div(a, b):
                return a / b if b else 0.0

            precision = safe_div(tp, tp + fp)
            recall = safe_div(tp, tp + fn)
            f1 = safe_div(2 * precision * recall, precision + recall) if (precision + recall) else 0.0

            st.subheader("Evaluation results")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("True Positives", tp)
            c2.metric("False Positives", fp)
            c3.metric("True Negatives", tn)
            c4.metric("False Negatives", fn)

            p1, p2, p3 = st.columns(3)
            p1.metric("Precision", f"{round(precision,4)}")
            p2.metric("Recall", f"{round(recall,4)}")
            p3.metric("F1 Score", f"{round(f1,4)}")

            st.markdown("---")
            st.subheader("Per-file results (table)")
            st.table(results)

            # allow download of results as CSV
            try:
                import pandas as pd
                df = pd.DataFrame(results)
                csv_bytes = df.to_csv(index=False).encode('utf-8')
                st.download_button("Download results CSV", data=csv_bytes, file_name="evaluation_results.csv", mime="text/csv")
            except Exception:
                csv_out = io.StringIO()
                writer = csv.writer(csv_out)
                keys = set()
                for r in results:
                    keys.update(r.keys())
                keys = sorted(keys)
                writer.writerow(keys)
                for r in results:
                    writer.writerow([r.get(k, "") for k in keys])
                st.download_button("Download results CSV", data=csv_out.getvalue().encode('utf-8'), file_name='evaluation_results.csv', mime='text/csv')
