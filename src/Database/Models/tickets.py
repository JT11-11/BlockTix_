import json
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from ..db import db
import uuid
import qrcode
from io import BytesIO
import base64
from .event_data import Event
from Utlis.web3_config import contract_service

class Ticket(db.Model):
    __tablename__ = 'tickets'
    
    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.String(16), unique=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    event_id = db.Column(db.Integer, db.ForeignKey('events.id'), nullable=False)
    amount_paid = db.Column(db.Numeric(10, 2), nullable=False)
    purchase_date = db.Column(db.DateTime, default=datetime.now, nullable=False)
    status = db.Column(db.String(20), nullable=False, default='active')
    qr_code = db.Column(db.Text)  
    qr_generated_at = db.Column(db.DateTime)  
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    used_at = db.Column(db.DateTime)
    blockchain_ticket_id = db.Column(db.String(100), nullable=True)  
    user = db.relationship('User', backref=db.backref('tickets', lazy=True))
    event = db.relationship('Event', backref=db.backref('tickets', lazy=True))
    
    def __init__(self, user_id, event_id, amount_paid, ticket_id=None, status='active'):
        self.user_id = user_id
        self.event_id = event_id
        self.amount_paid = amount_paid
        self.ticket_id = ticket_id or f"TIX-{uuid.uuid4().hex[:6].upper()}"
        self.status = status
        
    def mark_as_used(self):
        """Mark ticket as used"""
        self.status = 'used'
        self.used_at = datetime.now()
        
    def generate_qr_code(self, entered_pin):
        """Generate QR code for ticket"""
        try:
            event = Event.query.get(self.event_id)
            
            if not event:
                return False, "Event not found"
                
            print(f"Comparing pins - Entered: {entered_pin}, Event: {event.verification_pin}")
            
            if str(entered_pin) != str(event.verification_pin):
                return False, "Invalid verification pin"
                
            if self.status != 'active':
                return False, "Ticket is no longer active"

            qr_data = {
                'ticket_id': self.ticket_id,
                'event_id': self.event_id,
                'event_name': event.event_name,
                'event_date': event.event_date.strftime('%Y-%m-%d'),
                'event_time': event.event_time.strftime('%H:%M'),
                'venue': event.venue,
                'timestamp': datetime.now().isoformat()
            }            
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(json.dumps(qr_data))
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            buffered = BytesIO()
            img.save(buffered, format="PNG")
            img_str = base64.b64encode(buffered.getvalue()).decode()
            self.qr_code = img_str
            self.qr_generated_at = datetime.now()
            db.session.commit()
            
            return True, "QR code generated successfully"
        
        except Exception as e:
            print(f"Error generating QR code: {str(e)}")
            return False, f"Error generating QR code: {str(e)}"
        
    def to_dict(self):
        """Convert ticket to dictionary"""
        return {
            'ticket_id': self.ticket_id,
            'event_name': self.event.event_name,
            'event_date': self.event.event_date.strftime('%Y-%m-%d'),
            'event_time': self.event.event_time.strftime('%H:%M'),
            'venue': self.event.venue,
            'amount_paid': float(self.amount_paid),
            'purchase_date': self.purchase_date.strftime('%Y-%m-%d %H:%M:%S'),
            'status': self.status,
            'qr_code': self.qr_code if self.qr_code else None,
            'qr_generated_at': self.qr_generated_at.strftime('%Y-%m-%d %H:%M:%S') if self.qr_generated_at else None
        }
    blockchain_ticket_id = db.Column(db.String(100), nullable=True)
    
    def purchase_on_blockchain(self):
        """Purchase ticket on blockchain"""
        try:
            if not self.blockchain_ticket_id:
                blockchain_ticket_id = contract_service.purchase_ticket(
                    self.event.blockchain_event_id,
                    float(self.amount_paid)
                )
                self.blockchain_ticket_id = blockchain_ticket_id
                db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            raise e
    
    def use_on_blockchain(self, verification_pin):
        """Use ticket on blockchain"""
        try:
            if self.blockchain_ticket_id:
                success = contract_service.use_ticket(
                    self.blockchain_ticket_id,
                    verification_pin
                )
                if success:
                    self.status = 'used'
                    self.used_at = datetime.now()
                    db.session.commit()
                return success
            return False
        except Exception as e:
            db.session.rollback()
            raise e
