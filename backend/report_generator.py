import pathlib
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_reports_dir() -> pathlib.Path:
    return pathlib.Path(__file__).resolve().parent.parent / "outputs" / "inspection_reports"

def generate_report(job_id: str, input_source: str, inference_result: dict,
                    proxy_metrics: dict, model_version: str,
                    annotated_image_path: str = None) -> str:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    report_dir = get_reports_dir()
    report_dir.mkdir(parents=True, exist_ok=True)
    
    if not annotated_image_path:
        annotated_image_path = "*No annotated frame available.*"
    
    raw_findings = inference_result.get("findings", [])
    if raw_findings:
        rows = []
        for f in raw_findings:
            if isinstance(f, dict):
                label = f.get("label", "")
                conf = f.get("confidence", "")
                sev = f.get("severity", "")
                desc = f.get("description", "")
            else:
                label, conf, sev, desc = (list(f) + ["", "", "", ""])[:4]
            rows.append(f"| {label} | {conf} | {sev} | {desc} |")
        header = "| Finding | Confidence | Severity | Description |\n|---------|-----------|----------|-------------|"
        findings_table = header + "\n" + "\n".join(rows)
    else:
        findings_table = "*No findings.*"
    
    proxy_metrics_str = "\n".join([f"{key}: {value}" for key, value in proxy_metrics.items()])
    
    recommended_actions = inference_result.get("recommended_actions", ["No action required"])
    recommended_actions_str = "\n- ".join(recommended_actions)
    
    report_content = f"""
# Vision_Inspect Report — {timestamp}
**Job ID**: {job_id}, **Input Source**: {input_source}, **Model Version**: {model_version}, **Model Used**: {inference_result.get("model", inference_result.get("model_used", "Unknown"))}
## Findings
{findings_table}
## Pass/Fail Verdict
{inference_result.get("pass_fail", inference_result.get("verdict", "UNKNOWN")).upper()}
## Proxy Metrics
{proxy_metrics_str}
## Annotated Frame
{annotated_image_path}
## Recommended Human Actions
- {recommended_actions_str}
---
*This report is for human review only. Vision_Inspect makes no automated decisions.*
"""
    
    report_file = report_dir / f"{job_id}.md"
    with open(report_file, "w") as f:
        f.write(report_content)
    
    logger.info(f"Report saved to {report_file}")
    
    return report_content
