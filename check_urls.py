# check_urls.py
import requests

urls = {
    "reducehf_ae": "https://www.opencodelists.org/codelist/reducehf/heart-failure-ae/5ad354c5/download.csv",
    "qcovid_af":   "https://www.opencodelists.org/codelist/qcovid/has_atrial_fibrillation/2a4910da/download.csv",
}

for name, url in urls.items():
    r = requests.get(url, timeout=10)
    lines = r.text.splitlines()
    header = lines[0] if lines else "EMPTY"
    sample = lines[1] if len(lines) > 1 else "EMPTY"
    print(f"{r.status_code} {name}: {len(lines)} rows | cols: {header[:60]}")
    print(f"  sample: {sample[:60]}")