import time
from datetime import datetime
from email.parser import BytesParser
from email.message import Message
import config

# Converts a Unix timestamp to a formatted string like this: Jan 01 at 00:00:00
def format_time(timestamp: float) -> str:
    dt_object = datetime.utcfromtimestamp(timestamp)
    return dt_object.strftime("%b %d at %H:%M:%S")

# Extracts the email address from a field that could contain a name and email like: Example Name <example@example.com>
def extract_email_address(field: str) -> str:
    if '<' in field and '>' in field:
        start = field.find('<') + 1
        end = field.find('>')
        return field[start:end]
    return field.strip()

# Parses raw email bytes into a JSON dictionary for easy processing
def email_bytes_to_json(data: bytes) -> dict:
    # Double-check size (the SMTP layer also enforces this, but defence in depth)
    if len(data) > config.settings.MAX_EMAIL_SIZE:
        raise ValueError(f"Email size {len(data)} exceeds limit {config.settings.MAX_EMAIL_SIZE}")

    msg = BytesParser().parsebytes(data)
    
    to_field = extract_email_address(msg.get("To", "")).lower()
    from_field = extract_email_address(msg.get("From", "")).lower()
    
    current_timestamp = int(time.time())

    email_dict = {
        "From": from_field,
        "To": to_field,
        "Subject": msg.get("Subject", "No Subject"),
        "Timestamp": current_timestamp,
        "Sent": format_time(current_timestamp),
        "Body": "",
        "ContentType": "Text"
    }

    # Loop through parts of the message to find the body
    for part in msg.walk():
        content_type = part.get_content_type()
        if content_type == "text/plain" or content_type == "text/html":
            payload = part.get_payload(decode=True)
            if payload is None:
                continue
            charset = part.get_content_charset() or "utf-8"
            try:
                email_dict["Body"] = payload.decode(charset)
            except (LookupError, UnicodeDecodeError):
                # Fallback for unknown or broken charsets
                email_dict["Body"] = payload.decode("utf-8", errors="replace")
            if content_type == "text/plain":
                email_dict["ContentType"] = "Text"
            if content_type == "text/html":
                email_dict["ContentType"] = "HTML"


    return email_dict
