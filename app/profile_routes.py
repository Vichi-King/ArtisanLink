import os
import uuid

from flask import render_template, request, redirect, url_for, session, flash

from . import db
from .models import User, PortfolioItem, ArtisanAvailability


PORTFOLIO_UPLOAD_FOLDER = os.path.join("app", "static", "uploads", "portfolio")
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}
DAYS = [
    ("Monday", 1), ("Tuesday", 2), ("Wednesday", 3), ("Thursday", 4),
    ("Friday", 5), ("Saturday", 6), ("Sunday", 7)
]


def allowed_image(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def register_profile_routes(app):
    def artisan_owner():
        user = User.query.get(session.get("user_id"))
        return user, user.artisan_profile if user else None

    @app.route("/artisan/portfolio/add", methods=["GET", "POST"])
    def add_portfolio_item():
        if session.get("user_role") != "artisan":
            flash("Only artisans can manage a portfolio.", "danger")
            return redirect(url_for("login"))
        user, artisan = artisan_owner()
        if not artisan:
            flash("Your artisan profile could not be found.", "danger")
            return redirect(url_for("artisan_dashboard"))
        if request.method == "POST":
            title = request.form.get("title", "").strip()
            description = request.form.get("description", "").strip()
            image = request.files.get("image")
            if not title:
                flash("A portfolio title is required.", "danger")
                return redirect(url_for("add_portfolio_item"))
            filename = None
            if image and image.filename:
                if not allowed_image(image.filename):
                    flash("Please upload a JPG, JPEG, PNG, or WEBP image.", "danger")
                    return redirect(url_for("add_portfolio_item"))
                os.makedirs(PORTFOLIO_UPLOAD_FOLDER, exist_ok=True)
                extension = image.filename.rsplit(".", 1)[1].lower()
                filename = f"{uuid.uuid4().hex}.{extension}"
                image.save(os.path.join(PORTFOLIO_UPLOAD_FOLDER, filename))
            db.session.add(PortfolioItem(artisan_id=artisan.id, title=title, description=description or None, image=filename))
            db.session.commit()
            flash("Portfolio item added successfully.", "success")
            return redirect(url_for("artisan_dashboard"))
        return render_template("portfolio_form.html")

    @app.route("/artisan/portfolio/<int:item_id>/delete", methods=["POST"])
    def delete_portfolio_item(item_id):
        if session.get("user_role") != "artisan":
            return redirect(url_for("login"))
        _, artisan = artisan_owner()
        item = PortfolioItem.query.get_or_404(item_id)
        if not artisan or item.artisan_id != artisan.id:
            flash("You can only manage your own portfolio.", "danger")
            return redirect(url_for("artisan_dashboard"))
        filename = item.image
        db.session.delete(item)
        db.session.commit()
        if filename:
            path = os.path.join(PORTFOLIO_UPLOAD_FOLDER, filename)
            if os.path.exists(path):
                os.remove(path)
        flash("Portfolio item removed.", "info")
        return redirect(url_for("artisan_dashboard"))

    @app.route("/artisan/availability", methods=["GET", "POST"])
    def manage_availability():
        if session.get("user_role") != "artisan":
            flash("Only artisans can manage availability.", "danger")
            return redirect(url_for("login"))
        _, artisan = artisan_owner()
        if not artisan:
            flash("Your artisan profile could not be found.", "danger")
            return redirect(url_for("artisan_dashboard"))

        existing = {slot.day: slot for slot in artisan.availability}
        if request.method == "POST":
            for day, day_order in DAYS:
                available = request.form.get(f"available_{day}") == "on"
                start = request.form.get(f"start_{day}", "").strip() or None
                end = request.form.get(f"end_{day}", "").strip() or None
                if available and (not start or not end or start >= end):
                    flash(f"Please provide a valid start and end time for {day}.", "danger")
                    return redirect(url_for("manage_availability"))
                slot = existing.get(day)
                if not slot:
                    slot = ArtisanAvailability(artisan_id=artisan.id, day=day, day_order=day_order)
                    db.session.add(slot)
                slot.is_available = available
                slot.start_time = start if available else None
                slot.end_time = end if available else None
            db.session.commit()
            flash("Your availability has been updated.", "success")
            return redirect(url_for("artisan_dashboard"))

        availability = []
        for day, day_order in DAYS:
            slot = existing.get(day)
            availability.append(slot or ArtisanAvailability(day=day, day_order=day_order, is_available=False))
        return render_template("availability.html", availability=availability)
