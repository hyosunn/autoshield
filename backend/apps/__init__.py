from flask import Flask
from flask_caching import Cache
from flask_cors import CORS

cache = Cache()

def create_app():
    app = Flask(__name__)
    app.config['CACHE_TYPE'] = 'SimpleCache'
    app.config['CACHE_DEFAULT_TIMEOUT'] = 3600

    cache.init_app(app)
    CORS(app, resources={r'/api/*': {'origins': '*'}})

    with app.app_context():
        from .views import views
        app.register_blueprint(views)

    return app
