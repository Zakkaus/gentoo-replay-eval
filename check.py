#!/usr/bin/env python3
import json, glob, os, py_compile, sys
errs = []
if os.path.exists("cases/index.json"):
    for c in json.load(open("cases/index.json")):
        cid = c["id"]
        if not os.path.exists(f"cases/{cid}/meta.json"): errs.append(f"missing cases/{cid}/meta.json")
        else:
            try: json.load(open(f"cases/{cid}/meta.json"))
            except Exception as e: errs.append(f"cases/{cid}/meta.json: {e}")
        if not glob.glob(f"cases/{cid}/before/*"): errs.append(f"{cid}: no before file")
        if not glob.glob(f"cases/{cid}/truth/*"): errs.append(f"{cid}: no truth file")
for s in ["select_cases.py", "score.py", "lesson_map.py", "provenance.py", "check.py"]:
    try: py_compile.compile(s, doraise=True)
    except Exception as e: errs.append(f"{s}: {e}")
print("\n".join(errs) or f"check ok: {len(glob.glob('cases/*/meta.json'))} cases valid, scripts compile")
sys.exit(1 if errs else 0)
