from functools import wraps

from flask import render_template, request, redirect, url_for, session, flash
from sqlalchemy import func

from . import db
from .models import User, Artisan, Service, Booking, Review, PlatformCategory


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to continue.", "warning")
            return redirect(url_for("login"))
        if session.get("user_role") != "admin":
            flash("Administrator access is required.", "danger")
            return redirect(url_for("home"))
        return view(*args, **kwargs)
    return wrapped


def register_admin_routes(app):
    @app.route("/admin")
    @admin_required
    def admin_dashboard():
        stats = {
            "users": User.query.count(),
            "customers": User.query.filter_by(role="customer").count(),
            "artisans": Artisan.query.count(),
            "verified_artisans": Artisan.query.filter_by(is_verified=True).count(),
            "bookings": Booking.query.count(),
            "completed_bookings": Booking.query.filter_by(status="completed").count(),
            "reviews": Review.query.count(),
            "categories": PlatformCategory.query.count(),
        }
        artisans = (
            db.session.query(Artisan, User)
            .join(User, Artisan.user_id == User.id)
            .order_by(Artisan.is_verified.asc(), Artisan.id.desc())
            .limit(20)
            .all()
        )
        users = User.query.order_by(User.id.desc()).limit(20).all()
        reviews = (
            db.session.query(Review, User, Artisan)
            .join(User, Review.customer_id == User.id)
            .join(Artisan, Review.artisan_id == Artisan.id)
            .order_by(Review.id.desc())
            .limit(20)
            .all()
        )
        categories = PlatformCategory.query.order_by(PlatformCategory.name.asc()).all()
        category_usage = dict(
            db.session.query(Artisan.category, func.count(Artisan.id))
            .filter(Artisan.category.isnot(None), Artisan.category != "")
            .group_by(Artisan.category)
            .all()
        )
        return render_template(
            "admin_dashboard.html",
            stats=stats,
            artisans=artisans,
            users=users,
            reviews=reviews,
            categories=categories,
            category_usage=category_usage,
        )

    @app.post("/admin/artisans/<int:artisan_id>/verify")
    @admin_required
    def admin_toggle_verification(artisan_id):
        artisan = Artisan.query.get_or_404(artisan_id)
        artisan.is_verified = not artisan.is_verified
        db.session.commit()
        state = "verified" if artisan.is_verified else "unverified"
        flash(f"Artisan has been marked as {state}.", "success")
        return redirect(url_for("admin_dashboard") + "#artisans")

    @app.post("/admin/users/<int:user_id>/role")
    @admin_required
    def admin_change_role(user_id):
        user = User.query.get_or_404(user_id)
        if user.id == session.get("user_id"):
            flash("You cannot change your own administrator role.", "warning")
            return redirect(url_for("admin_dashboard") + "#users")
        new_role = request.form.get("role", "").strip()
        if new_role not in {"customer", "artisan", "admin"}:
            flash("Invalid user role.", "danger")
            return redirect(url_for("admin_dashboard") + "#users")
        if new_role == "artisan" and not user.artisan_profile:
            flash("A user must have an artisan profile before receiving the artisan role.", "warning")
            return redirect(url_for("admin_dashboard") + "#users")
        user.role = new_role
        db.session.commit()
        flash(f"{user.full_name}'s role has been updated.", "success")
        return redirect(url_for("admin_dashboard") + "#users")

    @app.post("/admin/reviews/<int:review_id>/delete")
    @admin_required
    def admin_delete_review(review_id):
        review = Review.query.get_or_404(review_id)
        db.session.delete(review)
        db.session.commit()
        flash("Review removed by administrator.", "success")
        return redirect(url_for("admin_dashboard") + "#reviews")

    @app.post("/admin/categories/add")
    @admin_required
    def admin_add_category():
        name = request.form.get("name", "").strip()
        if not name:
            flash("Category name is required.", "warning")
            return redirect(url_for("admin_dashboard") + "#categories")
        existing = PlatformCategory.query.filter(func.lower(PlatformCategory.name) == name.lower()).first()
        if existing:
            flash("That category already exists.", "warning")
            return redirect(url_for("admin_dashboard") + "#categories")
        db.session.add(PlatformCategory(name=name))
        db.session.commit()
        flash("Category added successfully.", "success")
        return redirect(url_for("admin_dashboard") + "#categories")

    @app.post("/admin/categories/<int:category_id>/delete")
    @admin_required
    def admin_delete_category(category_id):
        category = PlatformCategory.query.get_or_404(category_id)
        db.session.delete(category)
        db.session.commit()
        flash("Category removed from the platform catalogue.", "success")
        return redirect(url_for("admin_dashboard") + "#categories")
