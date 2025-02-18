from ..db import db
from werkzeug.security import generate_password_hash, check_password_hash
from cryptography.fernet import Fernet
import hashlib
import os

class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    fullname = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    id_number_hash = db.Column(db.String(64))  
    is_verified = db.Column(db.Boolean, default=False)
    eth_address = db.Column(db.String(42), unique=True)  
    encrypted_eth_private_key = db.Column(db.Text)

    ENCRYPTION_KEY = os.getenv('ENCRYPTION_KEY', Fernet.generate_key())
    cipher_suite = Fernet(ENCRYPTION_KEY)
    
    def set_password(self, password):
        self.password = generate_password_hash(password)
        
    def check_password(self, password):
        return check_password_hash(self.password, password)
        
    def set_id_number(self, id_number):
        self.id_number_hash = hashlib.sha256(id_number.encode()).hexdigest()
        
    def set_eth_private_key(self, private_key):
        """Encrypt and store the Ethereum private key"""
        if not private_key:
            raise ValueError("Private key cannot be empty")
            
        try:
            private_key_str = str(private_key)
            encrypted_key = self.cipher_suite.encrypt(private_key_str.encode())
            self.encrypted_eth_private_key = encrypted_key.decode()
        except Exception as e:
            raise Exception(f"Failed to encrypt private key: {str(e)}")
    
    def get_eth_private_key(self):
        """Decrypt and return the Ethereum private key"""
        if not self.encrypted_eth_private_key:
            return None
        try:
            decrypted_key = self.cipher_suite.decrypt(self.encrypted_eth_private_key.encode())
            return decrypted_key.decode()
        except Exception as e:
            raise Exception(f"Failed to decrypt private key: {str(e)}")
        