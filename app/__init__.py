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
    from .admin_routes import register_admin_routes
    from .security import init_security
    from .security_routes import register_security_routes

    register_routes(app)
    register_profile_routes(app)
    register_booking_routes(app)
    register_dashboard_routes(app)
    register_admin_routes(app)
    register_security_routes(app)
    init_security(app)
    register_notification_hooks()

    @app.errorhandler(404)
    def page_not_found(error):
        return "Page not found.", 404

    @app.errorhandler(413)
    def request_too_large(error):
        return "The uploaded file is too large. Maximum size is 5 MB.", 413

    @app.errorhandler(500)
    def internal_server_error(error):
        db.session.rollback()
        return "Something went wrong. Please try again.", 500

    with app.app_context():
        db.create_all()

    return app
