import smtplib
import json
import logging
import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from backend.config_loader import load_notification_config

SEVERITY_LEVELS = {"critical": 4, "high": 3, "medium": 2, "low": 1, "none": 0}
TEAMS_COLORS = {"critical": "FF0000", "high": "FF6600", "medium": "FFCC00", "low": "00CC00"}

class Notifier:
    def __init__(self, config: dict = None):
        self._cfg = config or load_notification_config()

    def should_notify(self, severity: str, channel: str) -> bool:
        return SEVERITY_LEVELS[severity] >= SEVERITY_LEVELS[self._cfg['channels'][channel]['threshold']]

    def send_teams(self, subject: str, body: str, severity: str) -> bool:
        if not self._cfg['teams']['enabled']:
            return False
        webhook_url = self._cfg['teams']['webhook_url']
        headers = {'Content-Type': 'application/json'}
        data = {
            "@type": "MessageCard",
            "@context": "http://schema.org/extensions",
            "themeColor": TEAMS_COLORS[severity],
            "summary": subject,
            "title": subject,
            "text": body
        }
        try:
            response = requests.post(webhook_url, headers=headers, data=json.dumps(data))
            return response.status_code == 200
        except Exception as e:
            logging.error(f"Failed to send Teams notification: {e}")
            return False

    def send_email(self, subject: str, body: str, recipients: list) -> bool:
        if not self._cfg['email']['enabled']:
            return False
        smtp_server = self._cfg['email']['smtp_server']
        smtp_port = self._cfg['email']['smtp_port']
        smtp_user = self._cfg['email']['smtp_user']
        smtp_password = self._cfg['email']['smtp_password']
        from_email = self._cfg['email']['from_email']
        msg = MIMEMultipart()
        msg['From'] = from_email
        msg['To'] = ', '.join(recipients)
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))
        try:
            server = smtplib.SMTP(smtp_server, smtp_port)
            server.starttls()
            server.login(smtp_user, smtp_password)
            text = msg.as_string()
            server.sendmail(from_email, recipients, text)
            server.quit()
            return True
        except Exception as e:
            logging.error(f"Failed to send email notification: {e}")
            return False

    def notify(self, finding: dict, report_path: str) -> None:
        subject = self._cfg['message_template'].format(severity=finding['severity'], source=finding['source'])
        body = f"Finding details can be found in the report at {report_path}"
        if self.should_notify(finding['severity'], 'teams'):
            self.send_teams(subject, body, finding['severity'])
        if self.should_notify(finding['severity'], 'email'):
            self.send_email(subject, body, self._cfg['email']['recipients'])
