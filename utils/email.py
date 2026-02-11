import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import os

FRONTEND_URL = os.getenv("FRONTEND_URL")

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
    msg["Subject"] = "Intervia - OTP Verification"
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

def send_welcome_email(
    to_email: str,
    user_name: str,
    login_url: str 
):
    try:
        with open("templates/welcome_email.html", "r", encoding="utf-8") as file:
            html_template = file.read()
        
        # Replace placeholders
        html_content = (
            html_template
            .replace("{{user_name}}", user_name)
            .replace("{{login_url}}", login_url)
            .replace("{{help_center_url}}", "https://yourdomain.com/help")
            .replace("{{current_year}}", str(datetime.now().year))
        )

        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"Welcome to Intervia, {user_name}! 🎉"
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
        
        print(f"Welcome email sent to {to_email}")
        return True
        
    except Exception as e:
        print(f"Error sending welcome email: {e}")
        return False
    
# Helper function to send welcome email asynchronously
async def send_welcome_email_async(to_email: str, user_name: str):
    """Send welcome email asynchronously"""
    try:
        # Use your domain URL (update this with your actual domain)
        login_url = FRONTEND_URL + "/dashboard"
        send_welcome_email(to_email, user_name, login_url)
    except Exception as e:
        print(f"Error in async welcome email: {e}")
