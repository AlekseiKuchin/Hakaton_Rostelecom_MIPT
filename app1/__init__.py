from flask import Flask
from flasgger import Swagger
from .routes import api_blueprint

def create_app():
    app = Flask(__name__)
    Swagger(app)  # Инициализация Swagger
    app.register_blueprint(api_blueprint, url_prefix="/api")
    return app
