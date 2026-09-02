from flask import Flask
from flask_sqlalchemy import SQLAlchemy


db = SQLAlchemy()


def create_app():
    app = Flask(__name__)

    app.config.from_object("config.Config")

    db.init_app(app)

    from .routes import register_routes
    from .profile_routes import register_profile_routes
    from .booking_routes import register_booking_routes
    from .dashboard_routes import register_dashboard_routes
    from .notification_hooks import register_notification_hooks

    register_routes(app)
    register_profile_routes(app)
    register_booking_routes(app)
    register_dashboard_routes(app)
    register_notification_hooks()

    with app.app_context():
        db.create_all()

    return app
