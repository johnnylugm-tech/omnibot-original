import subprocess
import json
import os
import re
from datetime import datetime

def run_tests():
    print("🚀 Running TDD Verification Suite...")
    result = subprocess.run(
        ["pytest", "--json-report", "--json-report-file=report.json", "--tb=short"],
        capture_output=True,
        text=True
    )
    return result

def get_git_revision():
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"]).decode("ascii").strip()[:7]
    except:
        return "unknown"

def update_report(report_data):
    report_path = "SPEC/omnibot-tdd-verification-report.md"
    summary = report_data.get("summary", {})
    
    total = summary.get("total", 0)
    passed = summary.get("passed", 0)
    failed = summary.get("failed", 0)
    skipped = summary.get("skipped", 0)
    duration = round(report_data.get("duration", 0), 2)
    commit = get_git_revision()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with open(report_path, "r") as f:
        content = f.read()

    # Update metadata
    content = re.sub(r"\*\*Repo:\*\*.*", f"**Repo:** `johnnylugm-tech/omnibot-original` (master branch, commit `{commit}`)", content)
    content = re.sub(r"\*\*報告產生時間:\*\*.*", f"**報告產生時間:** {now}", content)

    # Update test results block
    new_results = f"""
```
{total} tests collected
{passed} passed | {failed} failed | {skipped} skipped
執行時間: {duration} 秒
```"""
    content = re.sub(r"## 測試收集結果\n\n```[\s\S]*?```", f"## 測試收集結果\n\n{new_results}", content)

    with open(report_path, "w") as f:
        f.write(content)
    
    print(f"✅ Report updated: {passed}/{total} passed (Commit {commit})")

if __name__ == "__main__":
    if not os.path.exists("SPEC"):
        os.makedirs("SPEC")
    
    run_tests()
    if os.path.exists("report.json"):
        with open("report.json", "r") as f:
            data = json.load(f)
            update_report(data)
        os.remove("report.json")
    else:
        print("❌ Error: report.json not generated.")
