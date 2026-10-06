import os
import secrets

from flask import Flask
from flask_login import LoginManager
from flask import render_template
from auth.auth import auth_bp
from model.balance import Balance
from model.db import db
from model.user import User
from dashboard.dashboard import dashboard_bp

app = Flask(__name__, template_folder="template")
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY") or secrets.token_hex(32)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///app.db"
db.init_app(app)

login_manager = LoginManager(app)
login_manager.login_view = "auth.login"


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


app.register_blueprint(auth_bp)
app.register_blueprint(dashboard_bp)

with app.app_context():
    db.create_all()

@app.route('/')
def index():
    return render_template('index.html')



if __name__ == '__main__':
    app.run(debug=True)