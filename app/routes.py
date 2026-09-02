from datetime import datetime
from functools import wraps

from flask import app, render_template, request, redirect, url_for, session, flash
from flask_bcrypt import Bcrypt
from werkzeug.utils import secure_filename
from sqlalchemy import func, case
import os
import uuid

from . import db
from .models import User, Artisan, Service, Booking, Review


UPLOAD_FOLDER = os.path.join(
    "app",
    "static",
    "uploads",
    "artisans"
)

ALLOWED_EXTENSIONS = {
    "png",
    "jpg",
    "jpeg"
}

def allowed_file(filename):

    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower()
        in ALLOWED_EXTENSIONS
    )

bcrypt = Bcrypt()


def ranked_artisans(limit=None, offset=None):
    """Return artisans ordered by completed work, trust and profile quality."""
    completed_jobs = (
        db.session.query(
            Booking.artisan_id.label("artisan_id"),
            func.count(Booking.id).label("completed_jobs")
        )
        .filter(Booking.status == "completed")
        .group_by(Booking.artisan_id)
        .subquery()
    )
    review_stats = (
        db.session.query(
            Review.artisan_id.label("artisan_id"),
            func.avg(Review.rating).label("average_rating"),
            func.count(Review.id).label("review_count")
        )
        .group_by(Review.artisan_id)
        .subquery()
    )

    jobs = func.coalesce(completed_jobs.c.completed_jobs, 0)
    rating = func.coalesce(review_stats.c.average_rating, Artisan.manual_rating, 0)
    reviews = func.coalesce(review_stats.c.review_count, 0)
    profile_photo = case((User.profile_picture.isnot(None), 10), else_=0)
    verification = case((Artisan.is_verified.is_(True), 15), else_=0)
    score = (jobs * 4 + rating * 20 + verification + profile_photo).label("featured_score")

    query = (
        db.session.query(
            Artisan,
            rating.label("rating"),
            reviews.label("review_count"),
            jobs.label("completed_jobs"),
            score
        )
        .join(User, Artisan.user_id == User.id)
        .outerjoin(completed_jobs, completed_jobs.c.artisan_id == Artisan.id)
        .outerjoin(review_stats, review_stats.c.artisan_id == Artisan.id)
        .order_by(score.desc(), jobs.desc(), rating.desc(), Artisan.id.desc())
    )

    if offset:
        query = query.offset(offset)
    if limit:
        query = query.limit(limit)
    return query.all()


def login_required(view):
    """Require any logged-in user."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to continue.", "warning")
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


def role_required(*roles):
    """Require a logged-in user whose role is one of `roles`."""
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if "user_id" not in session:
                flash("Please log in to continue.", "warning")
                return redirect(url_for("login"))
            if session.get("user_role") not in roles:
                flash("You do not have access to that page.", "danger")
                return redirect(url_for("home"))
            return view(*args, **kwargs)
        return wrapped
    return decorator


def dashboard_endpoint_for(role):
    """Where a given role's dashboard lives - used for post-action redirects."""
    if role == "admin":
        return "admin_dashboard"
    if role == "artisan":
        return "artisan_dashboard"
    return "customer_dashboard"


def register_routes(app):

    @app.route("/")
    def home():
        return render_template(
            "home.html",
            featured_artisans=ranked_artisans(limit=4)
        )


    @app.route("/register", methods=["GET", "POST"])
    def register():

        role = request.args.get("role", "customer")

        if role not in ["customer", "artisan"]:
            role = "customer"


        if request.method == "POST":

            full_name = request.form.get(
                "full_name",
                ""
            ).strip()

            email = request.form.get(
                "email",
                ""
            ).strip().lower()

            password = request.form.get(
                "password",
                ""
            )

            confirm_password = request.form.get(
                "confirm_password",
                ""
            )

            phone = ""
            category = ""
            experience = None
            location = ""
            description = ""

            if role == "artisan":
                phone = request.form.get("phone", "").strip()
                category = request.form.get("category", "").strip()
                location = request.form.get("location", "").strip()
                description = request.form.get("description", "").strip()
                experience_value = request.form.get("experience", "").strip()

                if not all([
                    full_name,
                    email,
                    phone,
                    category,
                    experience_value,
                    location,
                    description
                ]):
                    flash("Please complete all artisan profile fields.", "danger")
                    return redirect(url_for("register", role="artisan"))

                try:
                    experience = int(experience_value)
                    if experience < 0:
                        raise ValueError
                except ValueError:
                    flash("Years of experience must be a non-negative whole number.", "danger")
                    return redirect(url_for("register", role="artisan"))


            # ---------------------------------------------
            # PASSWORD CHECK
            # ---------------------------------------------

            if password != confirm_password:

                flash(
                    "Passwords do not match.",
                    "danger"
                )

                return redirect(
                    url_for(
                        "register",
                        role=role
                    )
                )


            # ---------------------------------------------
            # CHECK EXISTING EMAIL
            # ---------------------------------------------

            existing_user = User.query.filter_by(
                email=email
            ).first()

            if existing_user:

                flash(
                    "An account with this email already exists.",
                    "danger"
                )

                return redirect(
                    url_for(
                        "register",
                        role=role
                    )
                )


            # ---------------------------------------------
            # PROFILE PICTURE
            # ---------------------------------------------

            profile_picture = None


            if role == "artisan":

                image = request.files.get(
                    "profile_picture"
                )

                if image and image.filename:

                    if not allowed_file(
                        image.filename
                    ):

                        flash(
                            "Please upload a JPG, JPEG, or PNG image.",
                            "danger"
                        )

                        return redirect(
                            url_for(
                                "register",
                                role="artisan"
                            )
                        )


                    os.makedirs(
                        UPLOAD_FOLDER,
                        exist_ok=True
                    )


                    extension = image.filename.rsplit(
                        ".",
                        1
                    )[1].lower()


                    filename = (
                        f"{uuid.uuid4().hex}.{extension}"
                    )


                    image.save(
                        os.path.join(
                            UPLOAD_FOLDER,
                            filename
                        )
                    )


                    profile_picture = filename


            # ---------------------------------------------
            # CREATE USER
            # ---------------------------------------------

            hashed_password = bcrypt.generate_password_hash(password).decode("utf-8")


            new_user = User(

                full_name=full_name,

                email=email,

                password_hash=hashed_password,

                role=role,

                profile_picture=profile_picture

            )


            db.session.add(new_user)

            if role == "artisan":
                artisan_profile = Artisan(
                    user=new_user,
                    bio=description,
                    phone=phone,
                    location=location,
                    category=category,
                    experience=experience
                )
                db.session.add(artisan_profile)

            db.session.commit()


            flash(
                "Account created successfully!",
                "success"
            )


            return redirect(
                url_for("login")
            )


        return render_template(
            "register.html",
            role=role
        )

    @app.route("/login", methods=["GET", "POST"])
    def login():

        if request.method == "POST":

            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")

            user = User.query.filter_by(email=email).first()

            if user and bcrypt.check_password_hash(
                user.password_hash,
                password
            ):
                session["user_id"] = user.id
                session["user_name"] = user.full_name
                session["user_role"] = user.role

                flash("Login successful.", "success")

                if user.role == "admin":
                    return redirect(url_for("admin_dashboard"))
                if user.role == "artisan":
                    return redirect(url_for("artisan_dashboard"))
                return redirect(url_for("customer_dashboard"))

            flash("Invalid email or password.", "danger")
            return redirect(url_for("login"))

        return render_template("login.html")

    @app.route("/become-artisan", methods=["GET", "POST"])
    def become_artisan():

        # Make sure the user is logged in
        if "user_id" not in session:
            flash("Please log in to become an artisan.", "warning")
            return redirect(url_for("login"))

        # Get the currently logged-in user
        user = User.query.get(session["user_id"])

        # If the user is already an artisan
        if user.role == "artisan":
            flash("You are already registered as an artisan.", "info")
            return redirect(url_for("artisan_dashboard"))

        if request.method == "POST":

            bio = request.form.get("bio", "").strip()
            phone = request.form.get("phone", "").strip()
            location = request.form.get("location", "").strip()
            category = request.form.get("category", "").strip()
            experience_value = request.form.get("experience", "").strip()

            if not all([bio, phone, location, category, experience_value]):
                flash("All fields are required.", "danger")
                return redirect(url_for("become_artisan"))

            try:
                experience = int(experience_value)
                if experience < 0:
                    raise ValueError
            except ValueError:
                flash("Years of experience must be a non-negative whole number.", "danger")
                return redirect(url_for("become_artisan"))

            artisan = Artisan(
                user_id=user.id,
                bio=bio,
                phone=phone,
                location=location,
                category=category,
                experience=experience
            )

            user.role = "artisan"

            db.session.add(artisan)
            db.session.commit()

            # Update the current session
            session["user_role"] = "artisan"

            flash(
                "Congratulations! You are now registered as an artisan.",
                "success"
            )

            return redirect(url_for("artisan_dashboard"))

        return render_template("become_artisan.html")


    @app.route("/artisan/dashboard")
    def artisan_dashboard():

        if "user_id" not in session:
            flash("Please log in to access your dashboard.", "warning")
            return redirect(url_for("login"))

        user = User.query.get(session["user_id"])

        if user.role != "artisan":
            flash("You do not have access to the artisan dashboard.", "danger")
            return redirect(url_for("home"))

        artisan = Artisan.query.filter_by(user_id=user.id).first()

        return render_template(
            "artisan_dashboard.html",
            user=user,
            artisan=artisan
        )

    @app.route("/artisan/profile/edit", methods=["GET", "POST"])
    def edit_artisan_profile():

        if "user_id" not in session:
            flash("Please log in to edit your profile.", "warning")
            return redirect(url_for("login"))

        user = User.query.get(session["user_id"])

        if not user or user.role != "artisan":
            flash("Only artisan accounts can edit an artisan profile.", "danger")
            return redirect(url_for("home"))

        artisan = user.artisan_profile

        if not artisan:
            flash("Your artisan profile could not be found.", "danger")
            return redirect(url_for("home"))

        if request.method == "POST":
            full_name = request.form.get("full_name", "").strip()
            email = request.form.get("email", "").strip().lower()
            phone = request.form.get("phone", "").strip()
            category = request.form.get("category", "").strip()
            location = request.form.get("location", "").strip()
            bio = request.form.get("bio", "").strip()
            experience_value = request.form.get("experience", "").strip()

            if not all([full_name, email, phone, category, location, bio, experience_value]):
                flash("Please complete all profile fields.", "danger")
                return redirect(url_for("edit_artisan_profile"))

            try:
                experience = int(experience_value)
                if experience < 0:
                    raise ValueError
            except ValueError:
                flash("Years of experience must be a non-negative whole number.", "danger")
                return redirect(url_for("edit_artisan_profile"))

            existing_user = User.query.filter(
                User.email == email,
                User.id != user.id
            ).first()

            if existing_user:
                flash("Another account already uses this email address.", "danger")
                return redirect(url_for("edit_artisan_profile"))

            image = request.files.get("profile_picture")
            new_filename = None

            if image and image.filename:
                if not allowed_file(image.filename):
                    flash("Please upload a JPG, JPEG, or PNG image.", "danger")
                    return redirect(url_for("edit_artisan_profile"))

                os.makedirs(UPLOAD_FOLDER, exist_ok=True)
                extension = image.filename.rsplit(".", 1)[1].lower()
                new_filename = f"{uuid.uuid4().hex}.{extension}"
                image.save(os.path.join(UPLOAD_FOLDER, new_filename))

            old_filename = user.profile_picture
            user.full_name = full_name
            user.email = email
            artisan.phone = phone
            artisan.category = category
            artisan.location = location
            artisan.bio = bio
            artisan.experience = experience

            if new_filename:
                user.profile_picture = new_filename

            db.session.commit()

            if new_filename and old_filename:
                old_image_path = os.path.join(UPLOAD_FOLDER, old_filename)
                if os.path.exists(old_image_path):
                    os.remove(old_image_path)

            session["user_name"] = user.full_name
            flash("Your artisan profile has been updated.", "success")
            return redirect(url_for("artisan_dashboard"))

        return render_template(
            "edit_artisan_profile.html",
            user=user,
            artisan=artisan
        )

    
    @app.route("/logout")
    def logout():

        session.clear()

        flash("You have been logged out.", "info")
        return redirect(url_for("home"))


    @app.route("/services")
    def services():
        return render_template("services.html")

    
    @app.route("/artisans")
    def artisans():
        page_size = 6
        directory_artisans = ranked_artisans(limit=page_size)
        total_artisans = Artisan.query.count()
        return render_template(
            "artisans.html",
            artisans=directory_artisans,
            total_artisans=total_artisans,
            has_more=total_artisans > page_size
        )

    @app.route("/artisans/load")
    def load_artisans():
        page = max(request.args.get("page", 1, type=int), 1)
        page_size = 6
        total_artisans = Artisan.query.count()
        artisans = ranked_artisans(
            limit=page_size,
            offset=(page - 1) * page_size
        )
        return {
            "html": render_template("_artisan_cards.html", artisans=artisans),
            "has_more": page * page_size < total_artisans
        }

    @app.route("/artisans/<int:artisan_id>")
    def artisan_profile(artisan_id):
        if "user_id" not in session:
            flash("Create an account or log in to view artisan profiles.", "info")
            return redirect(url_for("register", next=request.path))

        profile = next(
            (row for row in ranked_artisans() if row[0].id == artisan_id),
            None
        )
        if not profile:
            flash("That artisan profile is not available.", "danger")
            return redirect(url_for("artisans"))

        artisan, rating, review_count, completed_jobs, _ = profile
        reviews = Review.query.filter_by(artisan_id=artisan.id).order_by(
            Review.id.desc()
        ).limit(5).all()
        return render_template(
            "artisan_public_profile.html",
            artisan=artisan,
            rating=float(rating or 0),
            review_count=review_count,
            completed_jobs=completed_jobs,
            reviews=reviews
        )

    # ---------------------------------------------
    # ARTISAN SERVICE MANAGEMENT
    # ---------------------------------------------

    @app.route("/artisan/services/add", methods=["GET", "POST"])
    @role_required("artisan")
    def add_service():
        user = User.query.get(session["user_id"])
        artisan = user.artisan_profile

        if not artisan:
            flash("Your artisan profile could not be found.", "danger")
            return redirect(url_for("artisan_dashboard"))

        if request.method == "POST":
            name = request.form.get("name", "").strip()
            category = request.form.get("category", "").strip()
            description = request.form.get("description", "").strip()
            price_raw = request.form.get("price", "").strip()

            if not all([name, category, price_raw]):
                flash("Please complete the service name, category and price.", "danger")
                return redirect(url_for("add_service"))

            try:
                price = float(price_raw)
                if price <= 0:
                    raise ValueError
            except ValueError:
                flash("Price must be a positive number.", "danger")
                return redirect(url_for("add_service"))

            service = Service(
                artisan_id=artisan.id,
                name=name,
                category=category,
                description=description or None,
                price=price
            )

            db.session.add(service)
            db.session.commit()

            flash("Your service has been added.", "success")
            return redirect(url_for("artisan_dashboard"))

        return render_template("service_form.html", service=None)

    @app.route("/artisan/services/<int:service_id>/edit", methods=["GET", "POST"])
    @role_required("artisan")
    def edit_service(service_id):
        user = User.query.get(session["user_id"])
        artisan = user.artisan_profile
        service = Service.query.get_or_404(service_id)

        if not artisan or service.artisan_id != artisan.id:
            flash("You can only manage your own services.", "danger")
            return redirect(url_for("artisan_dashboard"))

        if request.method == "POST":
            name = request.form.get("name", "").strip()
            category = request.form.get("category", "").strip()
            description = request.form.get("description", "").strip()
            price_raw = request.form.get("price", "").strip()

            if not all([name, category, price_raw]):
                flash("Please complete the service name, category and price.", "danger")
                return redirect(url_for("edit_service", service_id=service_id))

            try:
                price = float(price_raw)
                if price <= 0:
                    raise ValueError
            except ValueError:
                flash("Price must be a positive number.", "danger")
                return redirect(url_for("edit_service", service_id=service_id))

            service.name = name
            service.category = category
            service.description = description or None
            service.price = price
            db.session.commit()

            flash("Your service has been updated.", "success")
            return redirect(url_for("artisan_dashboard"))

        return render_template("service_form.html", service=service)

    @app.route("/artisan/services/<int:service_id>/delete", methods=["POST"])
    @role_required("artisan")
    def delete_service(service_id):
        user = User.query.get(session["user_id"])
        artisan = user.artisan_profile
        service = Service.query.get_or_404(service_id)

        if not artisan or service.artisan_id != artisan.id:
            flash("You can only manage your own services.", "danger")
            return redirect(url_for("artisan_dashboard"))

        has_bookings = Booking.query.filter_by(service_id=service.id).first() is not None
        if has_bookings:
            flash("This service has booking history and cannot be deleted. You can edit it instead.", "warning")
            return redirect(url_for("artisan_dashboard"))

        db.session.delete(service)
        db.session.commit()

        flash("Service removed.", "info")
        return redirect(url_for("artisan_dashboard"))

    # ---------------------------------------------
    # CUSTOMER DASHBOARD
    # ---------------------------------------------

    @app.route("/dashboard")
    @role_required("customer")
    def customer_dashboard():
        user = User.query.get(session["user_id"])

        recent_bookings = (
            Booking.query.filter_by(customer_id=user.id)
            .order_by(Booking.id.desc())
            .limit(5)
            .all()
        )

        booking_total = Booking.query.filter_by(customer_id=user.id).count()
        pending_total = Booking.query.filter_by(customer_id=user.id, status="pending").count()
        completed_total = Booking.query.filter_by(customer_id=user.id, status="completed").count()

        suggested_artisans = ranked_artisans(limit=4)

        return render_template(
            "customer_dashboard.html",
            user=user,
            recent_bookings=recent_bookings,
            booking_total=booking_total,
            pending_total=pending_total,
            completed_total=completed_total,
            suggested_artisans=suggested_artisans
        )

    # ---------------------------------------------
    # PASSWORD UPDATE (shared by every role)
    # ---------------------------------------------

    @app.route("/account/change-password", methods=["POST"])
    @login_required
    def change_password():
        user = User.query.get(session["user_id"])
        redirect_endpoint = dashboard_endpoint_for(user.role)

        current_password = request.form.get("current_password", "")
        new_password = request.form.get("new_password", "")
        confirm_new_password = request.form.get("confirm_new_password", "")

        if not bcrypt.check_password_hash(user.password_hash, current_password):
            flash("Your current password is incorrect.", "danger")
            return redirect(url_for(redirect_endpoint))

        if len(new_password) < 8:
            flash("Your new password must be at least 8 characters long.", "danger")
            return redirect(url_for(redirect_endpoint))

        if new_password != confirm_new_password:
            flash("New passwords do not match.", "danger")
            return redirect(url_for(redirect_endpoint))

        if bcrypt.check_password_hash(user.password_hash, new_password):
            flash("Your new password must be different from your current password.", "danger")
            return redirect(url_for(redirect_endpoint))

        user.password_hash = bcrypt.generate_password_hash(new_password).decode("utf-8")
        db.session.commit()

        flash("Your password has been updated.", "success")
        return redirect(url_for(redirect_endpoint))

    # ---------------------------------------------
    # BOOKING - CUSTOMER SIDE
    # ---------------------------------------------

    @app.route("/book/<int:artisan_id>/<int:service_id>", methods=["GET", "POST"])
    @role_required("customer")
    def book_service(artisan_id, service_id):
        artisan = Artisan.query.get_or_404(artisan_id)
        service = Service.query.filter_by(id=service_id, artisan_id=artisan_id).first_or_404()

        if request.method == "POST":
            booking_date_raw = request.form.get("booking_date", "").strip()

            if not booking_date_raw:
                flash("Please choose a date and time for your booking.", "danger")
                return redirect(url_for("book_service", artisan_id=artisan_id, service_id=service_id))

            try:
                booking_date = datetime.strptime(booking_date_raw, "%Y-%m-%dT%H:%M")
            except ValueError:
                flash("Please provide a valid date and time.", "danger")
                return redirect(url_for("book_service", artisan_id=artisan_id, service_id=service_id))

            if booking_date < datetime.now():
                flash("Booking date and time must be in the future.", "danger")
                return redirect(url_for("book_service", artisan_id=artisan_id, service_id=service_id))

            booking = Booking(
                customer_id=session["user_id"],
                artisan_id=artisan_id,
                service_id=service_id,
                booking_date=booking_date,
                status="pending"
            )

            db.session.add(booking)
            db.session.commit()

            flash("Your booking request has been sent to the artisan.", "success")
            return redirect(url_for("my_bookings"))

        return render_template("book_service.html", artisan=artisan, service=service)

    @app.route("/bookings")
    @role_required("customer")
    def my_bookings():
        bookings = (
            Booking.query.filter_by(customer_id=session["user_id"])
            .order_by(Booking.booking_date.desc())
            .all()
        )
        return render_template("my_bookings.html", bookings=bookings)

    @app.route("/bookings/<int:booking_id>/cancel", methods=["POST"])
    @role_required("customer")
    def cancel_booking(booking_id):
        booking = Booking.query.get_or_404(booking_id)

        if booking.customer_id != session["user_id"]:
            flash("You can only cancel your own bookings.", "danger")
            return redirect(url_for("my_bookings"))

        if booking.status != "pending":
            flash("Only pending bookings can be cancelled.", "warning")
            return redirect(url_for("my_bookings"))

        booking.status = "cancelled"
        db.session.commit()

        flash("Your booking request has been cancelled.", "info")
        return redirect(url_for("my_bookings"))

    # ---------------------------------------------
    # BOOKING - ARTISAN SIDE
    # ---------------------------------------------

    @app.route("/artisan/bookings")
    @role_required("artisan")
    def artisan_bookings():
        user = User.query.get(session["user_id"])
        artisan = user.artisan_profile

        bookings = (
            Booking.query.filter_by(artisan_id=artisan.id)
            .order_by(Booking.booking_date.desc())
            .all()
            if artisan else []
        )

        return render_template("artisan_bookings.html", bookings=bookings, artisan=artisan)

    @app.route("/artisan/bookings/<int:booking_id>/respond", methods=["POST"])
    @role_required("artisan")
    def respond_booking(booking_id):
        booking = Booking.query.get_or_404(booking_id)
        user = User.query.get(session["user_id"])
        artisan = user.artisan_profile

        if not artisan or booking.artisan_id != artisan.id:
            flash("You can only manage your own booking requests.", "danger")
            return redirect(url_for("artisan_bookings"))

        action = request.form.get("action")

        # action -> (status required beforehand, status after)
        valid_transitions = {
            "accept": ("pending", "accepted"),
            "decline": ("pending", "declined"),
            "complete": ("accepted", "completed"),
        }

        if action not in valid_transitions:
            flash("Unrecognised booking action.", "danger")
            return redirect(url_for("artisan_bookings"))

        required_status, new_status = valid_transitions[action]

        if booking.status != required_status:
            flash("This booking has already moved on and can no longer be updated that way.", "warning")
            return redirect(url_for("artisan_bookings"))

        booking.status = new_status
        db.session.commit()

        flash(f"Booking marked as {new_status}.", "success")
        return redirect(url_for("artisan_bookings"))

    # ---------------------------------------------
    # ADMIN
    # ---------------------------------------------

    @app.route("/admin/dashboard")
    @role_required("admin")
    def admin_dashboard():
        total_customers = User.query.filter_by(role="customer").count()
        total_artisans = Artisan.query.count()
        verified_artisans = Artisan.query.filter_by(is_verified=True).count()

        booking_counts = dict(
            db.session.query(Booking.status, func.count(Booking.id))
            .group_by(Booking.status)
            .all()
        )

        completed_revenue = (
            db.session.query(func.coalesce(func.sum(Service.price), 0))
            .join(Booking, Booking.service_id == Service.id)
            .filter(Booking.status == "completed")
            .scalar()
        )

        average_rating = db.session.query(func.coalesce(func.avg(Review.rating), 0)).scalar()

        all_artisans = (
            Artisan.query.join(User)
            .order_by(Artisan.is_verified.asc(), Artisan.id.desc())
            .all()
        )

        recent_bookings = Booking.query.order_by(Booking.id.desc()).limit(8).all()

        return render_template(
            "admin_dashboard.html",
            total_customers=total_customers,
            total_artisans=total_artisans,
            verified_artisans=verified_artisans,
            unverified_count=total_artisans - verified_artisans,
            booking_counts=booking_counts,
            completed_revenue=completed_revenue,
            average_rating=float(average_rating or 0),
            all_artisans=all_artisans,
            recent_bookings=recent_bookings
        )

    @app.route("/admin/artisans/<int:artisan_id>/verify", methods=["POST"])
    @role_required("admin")
    def verify_artisan(artisan_id):
        artisan = Artisan.query.get_or_404(artisan_id)
        artisan.is_verified = not artisan.is_verified
        db.session.commit()

        status_text = "verified" if artisan.is_verified else "unverified"
        flash(f"{artisan.user.full_name} is now {status_text}.", "success")
        return redirect(url_for("admin_dashboard"))

    @app.route("/admin/artisans/<int:artisan_id>/remove", methods=["POST"])
    @role_required("admin")
    def remove_artisan(artisan_id):
        artisan = Artisan.query.get_or_404(artisan_id)
        user = artisan.user
        name = user.full_name

        # Remove records that reference this artisan first so the delete
        # does not fail on a foreign-key constraint.
        Review.query.filter_by(artisan_id=artisan.id).delete()
        Booking.query.filter_by(artisan_id=artisan.id).delete()

        db.session.delete(user)  # cascades to the Artisan profile
        db.session.commit()

        flash(f"{name}'s account has been removed from ArtisanLink.", "success")
        return redirect(url_for("admin_dashboard"))

    @app.route("/about")
    def about():
        return render_template("about.html")

    @app.route("/contact", methods=["GET", "POST"])
    def contact():

        if request.method == "POST":

            name = request.form.get("name")
            email = request.form.get("email")
            subject = request.form.get("subject")
            message = request.form.get("message")

            # Temporary handling
            print("CONTACT MESSAGE")
            print("Name:", name)
            print("Email:", email)
            print("Subject:", subject)
            print("Message:", message)

            return redirect(url_for("contact"))

        return render_template("contact.html")
