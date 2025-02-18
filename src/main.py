from datetime import timedelta
import click
import os
from flask import Flask, render_template
from Routes import create_app
from Database.db import db
from dotenv import load_dotenv

load_dotenv()

def create_database_url():
    DB_USER = os.environ.get('DB_USER')
    DB_PASSWORD = os.environ.get('DB_PASSWORD')
    DB_HOST = os.environ.get('DB_HOST')
    DB_NAME = os.environ.get('DB_NAME')
    
    return f'postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:5432/{DB_NAME}'

app = create_app()

app.config['SQLALCHEMY_DATABASE_URI'] = create_database_url()
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=1) 
app.secret_key = 'your-secret-key-here'

db.init_app(app)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, host='0.0.0.0', port=4309)


