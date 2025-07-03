# src/web/__init__.py

from flask import Flask

from .routes import bp as web_bp


def create_app():
    app = Flask(__name__, static_folder="static", template_folder="templates")
    app.register_blueprint(web_bp)

    # Make Python's getattr() available in Jinja templates
    app.jinja_env.globals["getattr"] = getattr

    return app
