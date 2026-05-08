import os
import smtplib
import traceback

from dotenv import load_dotenv
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


# Load .env variables
load_dotenv()


def send_email(
    to_email: str,
    subject: str,
    html_body: str,
    plain_body: str | None = None,
) -> bool:

    # =========================
    # SMTP CONFIG
    # =========================
    host = (os.getenv("SMTP_HOST") or "").strip()
    port = int((os.getenv("SMTP_PORT") or "587").strip())

    username = (os.getenv("SMTP_USERNAME") or "").strip()
    password = (os.getenv("SMTP_PASSWORD") or "").strip()

    from_email = (
        os.getenv("SMTP_FROM_EMAIL")
        or username
        or ""
    ).strip()

    use_tls = (
        (os.getenv("SMTP_USE_TLS") or "true")
        .strip()
        .lower()
        in ("1", "true", "yes")
    )

    # =========================
    # DEBUG CONFIG
    # =========================
    print("\n========== SMTP DEBUG ==========")
    print("HOST:", host)
    print("PORT:", port)
    print("USERNAME:", username)
    print("FROM EMAIL:", from_email)
    print("TLS ENABLED:", use_tls)
    print("================================\n")

    # =========================
    # VALIDATION
    # =========================
    if not host:
        print("ERROR: SMTP_HOST missing")
        return False

    if not from_email:
        print("ERROR: SMTP_FROM_EMAIL missing")
        return False

    try:
        # =========================
        # CREATE MESSAGE
        # =========================
        msg = MIMEMultipart("alternative")

        msg["Subject"] = subject
        msg["From"] = from_email
        msg["To"] = to_email

        # Plain text part
        if plain_body:
            msg.attach(
                MIMEText(
                    plain_body,
                    "plain",
                    "utf-8"
                )
            )

        # HTML part
        msg.attach(
            MIMEText(
                html_body,
                "html",
                "utf-8"
            )
        )

        print("Connecting to SMTP server...")

        # =========================
        # SMTP CONNECTION
        # =========================
        with smtplib.SMTP(host, port, timeout=30) as smtp:

            smtp.set_debuglevel(1)

            print("Running EHLO...")
            smtp.ehlo()

            # TLS
            if use_tls:
                print("Starting TLS...")
                smtp.starttls()
                smtp.ehlo()

            # Login
            if username and password:
                print("Logging into SMTP...")
                smtp.login(username, password)

            print("Sending email...")

            smtp.sendmail(
                from_email,
                [to_email],
                msg.as_string()
            )

        print(f"\nSUCCESS: Email sent to {to_email}\n")

        return True

    except Exception as e:

        print("\n========== EMAIL ERROR ==========")
        print("Error Type:", type(e).__name__)
        print("Error Message:", str(e))
        print("Full Traceback:")
        traceback.print_exc()
        print("=================================\n")

        return False