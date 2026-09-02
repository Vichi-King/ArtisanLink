from email.message import EmailMessage
import smtplib

from flask import current_app, flash, redirect, render_template, request, url_for
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from flask_bcrypt import Bcrypt

from .models import User


def _serializer():
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt="artisanlink-password-reset")


def _send_reset_email(user, reset_url):
    host = current_app.config.get("MAIL_SERVER")
    username = current_app.config.get("MAIL_USERNAME")
    password = current_app.config.get("MAIL_PASSWORD")
    sender = current_app.config.get("MAIL_DEFAULT_SENDER")
    if not all([host, username, password, sender]):
        return False

    message = EmailMessage()
    message["Subject"] = "Reset your ArtisanLink password"
    message["From"] = sender
    message["To"] = user.email
    message.set_content(
        "We received a request to reset your ArtisanLink password.\n\n"
        f"Reset your password here: {reset_url}\n\n"
        "This link expires in 30 minutes. If you did not request this, you can ignore this email."
    )
    try:
        with smtplib.SMTP(host, current_app.config.get("MAIL_PORT", 587), timeout=10) as smtp:
            smtp.starttls()
            smtp.login(username, password)
            smtp.send_message(message)
        return True
    except (OSError, smtplib.SMTPException):
        current_app.logger.exception("Password reset email could not be sent")
        return False


def register_security_routes(app):
    bcrypt = Bcrypt()

    @app.route("/forgot-password", methods=["GET", "POST"])
    def forgot_password():
        if request.method == "POST":
            email = request.form.get("email", "").strip().lower()
            user = User.query.filter_by(email=email).first()
            if user:
                token = _serializer().dumps(user.id)
                reset_url = url_for("reset_password", token=token, _external=True)
                if _send_reset_email(user, reset_url):
                    flash("If an account exists for that email, a password reset link has been sent.", "info")
                else:
                    flash("Password recovery email is not configured yet. Please contact support.", "warning")
            else:
                flash("If an account exists for that email, a password reset link has been sent.", "info")
            return redirect(url_for("forgot_password"))
        return render_template("forgot_password.html")

    @app.route("/reset-password/<token>", methods=["GET", "POST"])
    def reset_password(token):
        try:
            user_id = _serializer().loads(token, max_age=1800)
        except SignatureExpired:
            flash("That password reset link has expired. Please request a new one.", "warning")
            return redirect(url_for("forgot_password"))
        except BadSignature:
            flash("That password reset link is invalid.", "danger")
            return redirect(url_for("forgot_password"))

        user = User.query.get_or_404(user_id)
        if request.method == "POST":
            password = request.form.get("password", "")
            confirm_password = request.form.get("confirm_password", "")
            if len(password) < 8:
                flash("Password must be at least 8 characters long.", "danger")
                return redirect(url_for("reset_password", token=token))
            if password != confirm_password:
                flash("Passwords do not match.", "danger")
                return redirect(url_for("reset_password", token=token))
            user.password_hash = bcrypt.generate_password_hash(password).decode("utf-8")
            from . import db
            db.session.commit()
            flash("Your password has been reset successfully. Please log in.", "success")
            return redirect(url_for("login"))

        return render_template("reset_password.html")
