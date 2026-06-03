from flask import Flask

def create_app():
    app = Flask(__name__)

    with app.app_context():
        from .views import views
        app.register_blueprint(views)

    return app