from datetime import datetime
from ..db import db

class Promotion(db.Model):
    __tablename__ = 'promotions'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    valid_until = db.Column(db.DateTime)
    status = db.Column(db.String(20), default='active') 
    image_url = db.Column(db.String(500))  
    
    @property
    def is_active(self):
        return self.status == 'active' and self.valid_until > datetime.now()