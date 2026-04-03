import smtplib
import ssl
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import config

logger = logging.getLogger("maildrop")

# send an email
def send_email(from_address, to_address, subject, body):
    if config.ENABLE_SENDING == False:
        return False, "Sending is disabled"

    message = MIMEMultipart()
    message["From"] = from_address
    message["To"] = to_address
    message["Subject"] = subject
    message.attach(MIMEText(body, "plain"))

    server = None

    try:
        if config.RELAY_PORT == 465:
            context = ssl.create_default_context()
            server = smtplib.SMTP_SSL(config.RELAY_HOST, config.RELAY_PORT, context=context)
        else:
            server = smtplib.SMTP(config.RELAY_HOST, config.RELAY_PORT)
            server.starttls()

        if config.RELAY_USER and config.RELAY_PASS:
            server.login(config.RELAY_USER, config.RELAY_PASS)
        
        server.send_message(message)
        server.quit()

        logger.info(f"Sent email from {message['From']} to {message['To']}")

        return True, "Sent successfully"
    
    except Exception as e:
        logger.error(f"Failed to send email: {e}")

        if server:
            try:
                server.quit()
            except:
                pass
            
        return False, str(e)