import os
from flask import Flask
from flask_caching import Cache

cache = Cache()

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def create_app():
    app = Flask(
        __name__,
        template_folder=os.path.join(ROOT, 'templates'),
        static_folder=os.path.join(ROOT, 'static'),
    )
    app.config['CACHE_TYPE'] = 'SimpleCache'
    app.config['CACHE_DEFAULT_TIMEOUT'] = 3600

    cache.init_app(app)

    with app.app_context():
        from .views import views
        app.register_blueprint(views)

    return app