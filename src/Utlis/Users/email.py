from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import os
import smtplib
from dotenv import load_dotenv
import random
import string

load_dotenv()

def generate_verification_code():
    """Generate a random 6-digit code"""
    return ''.join(random.choices(string.digits, k=6))

def send_verification_email(to_email, code):
    """Send verification code via Gmail SMTP"""
    try:
        sender_email = os.environ.get('EMAIL_USER')  
        sender_password = os.environ.get('EMAIL_PASSWORD')  
        
        message = MIMEMultipart()
        message["From"] = sender_email
        message["To"] = to_email
        message["Subject"] = "Your BlockTix Verification Code"
        
        body = f"""
        Hello,
        
        Your verification code is: {code}
        
        This code will expire in 10 minutes.
        
        Best regards,
        BlockTix Team
        """
        
        message.attach(MIMEText(body, "plain"))
        
        # Create SMTP session
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(sender_email, sender_password)
            text = message.as_string()
            server.sendmail(sender_email, to_email, text)
            return True
            
    except Exception as e:
        print(f"Error sending email: {str(e)}")
        return False