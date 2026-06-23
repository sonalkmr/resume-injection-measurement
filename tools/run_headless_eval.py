import requests
from pathlib import Path
import json

API = "http://127.0.0.1:8000/analyze"
files = ["examples/pdfs/data_skills_keywords_case.pdf", "examples/pdfs/instruction_override_case.pdf"]
labels = {"data_skills_keywords_case.pdf": 1, "instruction_override_case.pdf": 1}
threshold = 50

tp = fp = tn = fn = 0
results = []
for p in files:
    name = Path(p).name
    print(f"Posting {name} ...")
    with open(p, "rb") as f:
        resp = requests.post(API, files={"file": (name, f, "application/pdf")}, timeout=300)
    if resp.status_code != 200:
        print("API error:", resp.status_code, resp.text)
        results.append({"file": name, "error": resp.text})
        continue
    data = resp.json()
    risk = data.get("risk", {}).get("risk_score", 0)
    pred = 1 if risk >= threshold else 0
    true = labels.get(name)
    results.append({"file": name, "risk": risk, "pred": pred, "true": true})
    if true == 1 and pred == 1:
        tp += 1
    elif true == 0 and pred == 1:
        fp += 1
    elif true == 1 and pred == 0:
        fn += 1
    elif true == 0 and pred == 0:
        tn += 1

precision = tp / (tp + fp) if (tp + fp) else 0.0
recall = tp / (tp + fn) if (tp + fn) else 0.0
f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0

print()
print("TP=", tp, "FP=", fp, "TN=", tn, "FN=", fn)
print(f"precision={precision:.4f} recall={recall:.4f} f1={f1:.4f}")
print('\nPer-file results:')
print(json.dumps(results, indent=2))
