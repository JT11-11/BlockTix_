from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from ..db import db 
from Utlis.web3_config import contract_service
import uuid

class Event(db.Model):
    __tablename__ = 'events'
    
    id = db.Column(db.Integer, primary_key=True)
    event_name = db.Column(db.String(255), nullable=False)
    available_tickets = db.Column(db.Integer, nullable=False)
    ticket_price = db.Column(db.Numeric(10,2), nullable=False)
    venue = db.Column(db.String(255), nullable=False)
    event_date = db.Column(db.Date, nullable=False)
    event_time = db.Column(db.Time, nullable=False)
    image_url = db.Column(db.String(500), default=None) 
    description = db.Column(db.Text, nullable=False)
    verification_pin = db.Column(db.String(4), nullable=True) 
    eco_paper_straws = db.Column(db.Boolean, default=False)
    eco_public_transport = db.Column(db.Boolean, default=False)
    eco_recycling = db.Column(db.Boolean, default=False)
    eco_composting = db.Column(db.Boolean, default=False)
    eco_renewable_energy = db.Column(db.Boolean, default=False)
    
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    
    blockchain_event_id = db.Column(db.Integer, nullable=True)
    
    def create_on_blockchain(self):
        """Create event on blockchain"""
        try:
            if not self.blockchain_event_id:
                blockchain_event_id = contract_service.create_event(self)
                self.blockchain_event_id = blockchain_event_id
                db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            raise e