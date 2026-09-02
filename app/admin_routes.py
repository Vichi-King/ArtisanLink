from functools import wraps

from flask import render_template, request, redirect, url_for, session, flash
from sqlalchemy import func

from . import db
from .models import User, Artisan, Booking, Review


class PlatformCategory(db.Model):
    __tablename__ = "platform_categories"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)


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
    @app.route("/admin/manage")
    @admin_required
    def admin_manage():
        stats = {
            "users": User.query.count(),
            "customers": User.query.filter_by(role="customer").count(),
            "artisans": Artisan.query.count(),
            "verified_artisans": Artisan.query.filter_by(is_verified=True).count(),
            "bookings": Booking.query.count(),
            "completed": Booking.query.filter_by(status="completed").count(),
            "reviews": Review.query.count(),
            "categories": PlatformCategory.query.count(),
        }
        users = User.query.order_by(User.id.desc()).limit(30).all()
        reviews = (
            db.session.query(Review, User, Artisan)
            .join(User, Review.customer_id == User.id)
            .join(Artisan, Review.artisan_id == Artisan.id)
            .order_by(Review.id.desc())
            .limit(30)
            .all()
        )
        categories = PlatformCategory.query.order_by(PlatformCategory.name.asc()).all()
        usage = dict(
            db.session.query(Artisan.category, func.count(Artisan.id))
            .filter(Artisan.category.isnot(None), Artisan.category != "")
            .group_by(Artisan.category)
            .all()
        )
        return render_template("admin_management.html", stats=stats, users=users, reviews=reviews, categories=categories, usage=usage)

    @app.post("/admin/manage/users/<int:user_id>/role")
    @admin_required
    def admin_manage_role(user_id):
        user = User.query.get_or_404(user_id)
        if user.id == session.get("user_id"):
            flash("You cannot change your own administrator role.", "warning")
            return redirect(url_for("admin_manage") + "#users")
        role = request.form.get("role", "").strip()
        if role not in {"customer", "artisan", "admin"}:
            flash("Invalid user role.", "danger")
        elif role == "artisan" and not user.artisan_profile:
            flash("This user needs an artisan profile before receiving the artisan role.", "warning")
        else:
            user.role = role
            db.session.commit()
            flash(f"{user.full_name}'s role has been updated.", "success")
        return redirect(url_for("admin_manage") + "#users")

    @app.post("/admin/manage/reviews/<int:review_id>/delete")
    @admin_required
    def admin_manage_delete_review(review_id):
        review = Review.query.get_or_404(review_id)
        db.session.delete(review)
        db.session.commit()
        flash("Review removed by administrator.", "success")
        return redirect(url_for("admin_manage") + "#reviews")

    @app.post("/admin/manage/categories/add")
    @admin_required
    def admin_manage_add_category():
        name = request.form.get("name", "").strip()
        if not name:
            flash("Category name is required.", "warning")
        elif PlatformCategory.query.filter(func.lower(PlatformCategory.name) == name.lower()).first():
            flash("That category already exists.", "warning")
        else:
            db.session.add(PlatformCategory(name=name))
            db.session.commit()
            flash("Category added successfully.", "success")
        return redirect(url_for("admin_manage") + "#categories")

    @app.post("/admin/manage/categories/<int:category_id>/delete")
    @admin_required
    def admin_manage_delete_category(category_id):
        category = PlatformCategory.query.get_or_404(category_id)
        db.session.delete(category)
        db.session.commit()
        flash("Category removed from the platform catalogue.", "success")
        return redirect(url_for("admin_manage") + "#categories")
