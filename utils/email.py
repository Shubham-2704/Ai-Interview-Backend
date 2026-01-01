import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import os

def send_otp_email(
    to_email: str,
    user_name: str,
    otp: str,
    expiry_minutes: int = 10
):
    with open("templates/otp_email.html", "r", encoding="utf-8") as file:
        html_template = file.read()

    html_content = (
        html_template
        .replace("{{user_name}}", user_name)
        .replace("{{otp_code}}", otp)
        .replace("{{otp_expiry_minutes}}", str(expiry_minutes))
        .replace("{{current_year}}", str(datetime.now().year))
    )

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "TaskFlow - OTP Verification"
    msg["From"] = os.getenv("EMAIL_FROM")
    msg["To"] = to_email

    msg.attach(MIMEText(html_content, "html"))

    server = smtplib.SMTP(os.getenv("SMTP_HOST"), int(os.getenv("SMTP_PORT")))
    server.starttls()
    server.login(
        os.getenv("SMTP_USER"),
        os.getenv("SMTP_PASSWORD")
    )
    server.sendmail(msg["From"], to_email, msg.as_string())
    server.quit()