from .db import db

def init_db(app):
    db.init_app(app)
    from .Models.user import User
    with app.app_context():
        db.create_all()