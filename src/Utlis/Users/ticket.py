from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from dotenv import load_dotenv
import secrets
import smtplib
import os

load_dotenv()

def generate_ticket_id():
    """Generate a unique ticket identifier"""
    return f"TIX{secrets.token_hex(6).upper()}"

def send_ticket_confirmation(user_email, ticket_details):
    """Send ticket confirmation email"""
    try:
        sender_email = os.environ.get('EMAIL_USER')
        sender_password = os.environ.get('EMAIL_PASSWORD')
        
        message = MIMEMultipart()
        message["From"] = sender_email
        message["To"] = user_email
        message["Subject"] = "Your BlockTix Ticket Confirmation"
        
        body = f"""
        Hello,
        
        Thank you for your purchase! Here are your ticket details:
        
        Event: {ticket_details['event_name']}
        Date: {ticket_details['event_date']}
        Time: {ticket_details['event_time']}
        Venue: {ticket_details['venue']}
        Ticket ID: {ticket_details['ticket_id']}
        
        You can view your ticket in your dashboard.
        
        Best regards,
        BlockTix Team
        """
        
        message.attach(MIMEText(body, "plain"))
        
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(sender_email, sender_password)
            text = message.as_string()
            server.sendmail(sender_email, user_email, text)
            return True
            
    except Exception as e:
        print(f"Error sending ticket confirmation: {str(e)}")
        return False
