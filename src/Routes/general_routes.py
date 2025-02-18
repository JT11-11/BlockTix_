from flask import Blueprint, render_template
import os  

general_bp = Blueprint('general', __name__)

@general_bp.route('/')
def home():
    return render_template('home.html')  
