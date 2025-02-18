from flask import Flask
from .user import user_bp
from .general_routes import general_bp
from flask_cors import CORS
from .admin import admin_bp

def create_app():
    app = Flask(__name__, template_folder='../templates')
    CORS(app)
    app.register_blueprint(general_bp)
    app.register_blueprint(user_bp, url_prefix='/user')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    return app