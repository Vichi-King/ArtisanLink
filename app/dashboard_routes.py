from functools import wraps
from flask import render_template, request, redirect, url_for, session, flash

from . import db
from .models import User, Notification, Booking


def _login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to continue.", "warning")
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


def register_dashboard_routes(app):
    @app.context_processor
    def dashboard_context():
        if "user_id" not in session:
            return {"unread_notifications": 0, "recent_notifications": [], "dashboard_booking_stats": {}}
        user_id = session["user_id"]
        unread = Notification.query.filter_by(user_id=user_id, is_read=False).count()
        recent = Notification.query.filter_by(user_id=user_id).order_by(Notification.id.desc()).limit(5).all()
        stats = {}
        if session.get("user_role") == "artisan":
            user = User.query.get(user_id)
            artisan = user.artisan_profile if user else None
            if artisan:
                stats = {
                    "total": Booking.query.filter_by(artisan_id=artisan.id).count(),
                    "pending": Booking.query.filter_by(artisan_id=artisan.id, status="pending").count(),
                    "active": Booking.query.filter(Booking.artisan_id == artisan.id, Booking.status.in_(["accepted", "negotiating", "awaiting_customer_confirmation"])).count(),
                    "completed": Booking.query.filter_by(artisan_id=artisan.id, status="completed").count(),
                }
        return {"unread_notifications": unread, "recent_notifications": recent, "dashboard_booking_stats": stats}

    @app.route("/notifications")
    @_login_required
    def notifications():
        items = Notification.query.filter_by(user_id=session["user_id"]).order_by(Notification.id.desc()).all()
        return render_template("notifications.html", notifications=items)

    @app.route("/notifications/<int:notification_id>/read", methods=["POST"])
    @_login_required
    def mark_notification_read(notification_id):
        notification = Notification.query.get_or_404(notification_id)
        if notification.user_id != session["user_id"]:
            flash("You can only update your own notifications.", "danger")
            return redirect(url_for("notifications"))
        notification.is_read = True
        db.session.commit()
        return redirect(request.form.get("next") or url_for("notifications"))

    @app.route("/notifications/read-all", methods=["POST"])
    @_login_required
    def mark_all_notifications_read():
        Notification.query.filter_by(user_id=session["user_id"], is_read=False).update({"is_read": True}, synchronize_session=False)
        db.session.commit()
        flash("All notifications marked as read.", "success")
        return redirect(url_for("notifications"))

    @app.route("/account/profile", methods=["GET", "POST"])
    @_login_required
    def edit_account():
        user = User.query.get_or_404(session["user_id"])
        if request.method == "POST":
            full_name = request.form.get("full_name", "").strip()
            email = request.form.get("email", "").strip().lower()
            if not full_name or not email:
                flash("Name and email are required.", "danger")
                return redirect(url_for("edit_account"))
            if User.query.filter(User.email == email, User.id != user.id).first():
                flash("Another account already uses this email address.", "danger")
                return redirect(url_for("edit_account"))
            user.full_name = full_name
            user.email = email
            session["user_name"] = full_name
            db.session.commit()
            flash("Your account details have been updated.", "success")
            return redirect(url_for("customer_dashboard" if user.role == "customer" else "artisan_dashboard"))
        return render_template("account_profile.html", user=user)
