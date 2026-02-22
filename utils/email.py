# import smtplib
# from email.mime.text import MIMEText
# from email.mime.multipart import MIMEMultipart
# from datetime import datetime
# import os

# FRONTEND_URL = os.getenv("FRONTEND_URL")

# def send_otp_email(
#     to_email: str,
#     user_name: str,
#     otp: str,
#     expiry_minutes: int = 10
# ):
#     with open("templates/otp_email.html", "r", encoding="utf-8") as file:
#         html_template = file.read()

#     html_content = (
#         html_template
#         .replace("{{user_name}}", user_name)
#         .replace("{{otp_code}}", otp)
#         .replace("{{otp_expiry_minutes}}", str(expiry_minutes))
#         .replace("{{current_year}}", str(datetime.now().year))
#     )

#     msg = MIMEMultipart("alternative")
#     msg["Subject"] = "Intervia - OTP Verification"
#     msg["From"] = os.getenv("EMAIL_FROM")
#     msg["To"] = to_email

#     msg.attach(MIMEText(html_content, "html"))

#     server = smtplib.SMTP(os.getenv("SMTP_HOST"), int(os.getenv("SMTP_PORT")))
#     server.starttls()
#     server.login(
#         os.getenv("SMTP_USER"),
#         os.getenv("SMTP_PASSWORD")
#     )
#     server.sendmail(msg["From"], to_email, msg.as_string())
#     server.quit()

# def send_welcome_email(
#     to_email: str,
#     user_name: str,
#     login_url: str 
# ):
#     try:
#         with open("templates/welcome_email.html", "r", encoding="utf-8") as file:
#             html_template = file.read()
        
#         # Replace placeholders
#         html_content = (
#             html_template
#             .replace("{{user_name}}", user_name)
#             .replace("{{login_url}}", login_url)
#             .replace("{{help_center_url}}", "https://yourdomain.com/help")
#             .replace("{{current_year}}", str(datetime.now().year))
#         )

#         msg = MIMEMultipart("alternative")
#         msg["Subject"] = f"Welcome to Intervia, {user_name}! 🎉"
#         msg["From"] = os.getenv("EMAIL_FROM")
#         msg["To"] = to_email

#         msg.attach(MIMEText(html_content, "html"))

#         server = smtplib.SMTP(os.getenv("SMTP_HOST"), int(os.getenv("SMTP_PORT")))
#         server.starttls()
#         server.login(
#             os.getenv("SMTP_USER"),
#             os.getenv("SMTP_PASSWORD")
#         )
#         server.sendmail(msg["From"], to_email, msg.as_string())
#         server.quit()
        
#         print(f"Welcome email sent to {to_email}")
#         return True
        
#     except Exception as e:
#         print(f"Error sending welcome email: {e}")
#         return False
    
# # Helper function to send welcome email asynchronously
# async def send_welcome_email_async(to_email: str, user_name: str):
#     """Send welcome email asynchronously"""
#     try:
#         # Use your domain URL (update this with your actual domain)
#         login_url = FRONTEND_URL + "/dashboard"
#         send_welcome_email(to_email, user_name, login_url)
#     except Exception as e:
#         print(f"Error in async welcome email: {e}")


#Production Code for mailing services.

from datetime import datetime
import requests
import os

FRONTEND_URL = os.getenv("FRONTEND_URL")
RESEND_API_KEY = os.getenv("RESEND_API_KEY")
EMAIL_FROM = os.getenv("EMAIL_FROM")


# 🔹 Core Email Sender (Resend API)
def send_email(to_email: str, subject: str, html_content: str):
    response = requests.post(
        "https://api.resend.com/emails",
        headers={
            "Authorization": f"Bearer {RESEND_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "from": EMAIL_FROM,
            "to": [to_email],
            "subject": subject,
            "html": html_content,
        },
    )

    print("STATUS:", response.status_code)
    print("RESPONSE:", response.text)

    if response.status_code >= 400:
        print("Email failed:", response.text)
        return False

    return True


# 🔹 Welcome Email (Sync)
def send_welcome_email(
    to_email: str,
    user_name: str,
    login_url: str
):
    try:
        with open("templates/welcome_email.html", "r", encoding="utf-8") as file:
            html_template = file.read()

        html_content = (
            html_template
            .replace("{{user_name}}", user_name)
            .replace("{{login_url}}", login_url)
            .replace("{{current_year}}", str(datetime.now().year))
        )

        return send_email(
            to_email,
            f"Welcome to Intervia, {user_name}! 🎉",
            html_content
        )

    except Exception as e:
        print(f"Error sending welcome email: {e}")
        return False


# 🔹 Async Wrapper (So your controller stays SAME)
async def send_welcome_email_async(to_email: str, user_name: str):
    try:
        login_url = FRONTEND_URL + "/dashboard"
        send_welcome_email(to_email, user_name, login_url)
    except Exception as e:
        print(f"Error in async welcome email: {e}")


# 🔹 OTP Email
def send_otp_email(
    to_email: str,
    user_name: str,
    otp: str,
    expiry_minutes: int = 10
):
    try:
        with open("templates/otp_email.html", "r", encoding="utf-8") as file:
            html_template = file.read()

        html_content = (
            html_template
            .replace("{{user_name}}", user_name)
            .replace("{{otp_code}}", otp)
            .replace("{{otp_expiry_minutes}}", str(expiry_minutes))
            .replace("{{current_year}}", str(datetime.now().year))
        )

        return send_email(
            to_email,
            "Intervia - OTP Verification",
            html_content
        )

    except Exception as e:
        print(f"Error sending OTP email: {e}")
        return False