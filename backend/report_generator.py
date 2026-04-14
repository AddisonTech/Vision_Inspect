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
    
    findings_table = "\n".join([f"| {label} | {confidence} | {severity} | {description}" for label, confidence, severity, description in inference_result.get("findings", [])])
    if not findings_table:
        findings_table = "*No findings.*"
    
    proxy_metrics_str = "\n".join([f"{key}: {value}" for key, value in proxy_metrics.items()])
    
    recommended_actions = inference_result.get("recommended_actions", ["No action required"])
    recommended_actions_str = "\n- ".join(recommended_actions)
    
    report_content = f"""
# Vision_Inspect Report — {timestamp}
**Job ID**: {job_id}, **Input Source**: {input_source}, **Model Version**: {model_version}, **Model Used**: {inference_result.get("model_used", "Unknown")}
## Findings
{findings_table}
## Pass/Fail Verdict
{inference_result.get("verdict", "UNKNOWN").upper()}
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
