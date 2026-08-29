from flask import app, render_template, request, redirect, url_for, session, flash
from flask_bcrypt import Bcrypt
from werkzeug.utils import secure_filename
from sqlalchemy import func, case
import csv
import io
import hmac
import os
import uuid

from . import db
from .models import User, Artisan, Booking, Review


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


def has_bulk_access():
    return bool(session.get("bulk_admin"))


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
                return redirect(url_for("home"))

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

            if not bio or not phone or not location:
                flash("All fields are required.", "danger")
                return redirect(url_for("become_artisan"))

            artisan = Artisan(
                user_id=user.id,
                bio=bio,
                phone=phone,
                location=location
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

    @app.route("/bulk-admin", methods=["GET", "POST"])
    def bulk_admin_login():
        access_key = os.getenv("ADMIN_ACCESS_KEY")
        if not access_key:
            flash("Bulk management is disabled. Set ADMIN_ACCESS_KEY first.", "warning")
            return redirect(url_for("home"))

        if request.method == "POST":
            submitted_key = request.form.get("access_key", "")
            if hmac.compare_digest(submitted_key, access_key):
                session["bulk_admin"] = True
                return redirect(url_for("bulk_artisans"))
            flash("The management access key is incorrect.", "danger")

        return render_template("bulk_admin_login.html")

    @app.route("/bulk-admin/artisans", methods=["GET", "POST"])
    def bulk_artisans():
        if not has_bulk_access():
            return redirect(url_for("bulk_admin_login"))

        if request.method == "POST":
            rows = list(csv.DictReader(io.StringIO(request.form.get("artisan_csv", "").strip())))
            created = 0
            errors = []
            for row_number, row in enumerate(rows, start=2):
                full_name = row.get("full_name", "").strip()
                email = row.get("email", "").strip().lower()
                password = row.get("password", "")
                phone = row.get("phone", "").strip()
                location = row.get("location", "").strip()
                category = row.get("category", "").strip()
                bio = row.get("bio", "").strip()
                try:
                    experience = int(row.get("experience", "0"))
                    rating = float(row.get("rating", "0") or 0)
                except ValueError:
                    errors.append(f"Row {row_number}: experience and rating must be numbers.")
                    continue

                if not all([full_name, email, password, phone, location, category, bio]) or experience < 0 or not 0 <= rating <= 5:
                    errors.append(f"Row {row_number}: complete every required field and use a rating from 0 to 5.")
                    continue
                if User.query.filter_by(email=email).first():
                    errors.append(f"Row {row_number}: {email} is already registered.")
                    continue

                verified = row.get("verified", "").strip().lower() in {"yes", "true", "1"}
                user = User(
                    full_name=full_name,
                    email=email,
                    password_hash=bcrypt.generate_password_hash(password).decode("utf-8"),
                    role="artisan"
                )
                artisan = Artisan(
                    user=user,
                    phone=phone,
                    location=location,
                    category=category,
                    bio=bio,
                    experience=experience,
                    is_verified=verified,
                    manual_rating=rating or None
                )
                db.session.add_all([user, artisan])
                created += 1

            db.session.commit()
            flash(f"Created {created} artisan account(s)." + (f" {len(errors)} row(s) were skipped." if errors else ""), "success")
            return render_template("bulk_artisans.html", errors=errors)

        return render_template("bulk_artisans.html", errors=[])

    @app.route("/bulk-admin/artisans/update", methods=["GET", "POST"])
    def bulk_update_artisans():
        if not has_bulk_access():
            return redirect(url_for("bulk_admin_login"))

        if request.method == "POST":
            rows = list(csv.DictReader(io.StringIO(request.form.get("update_csv", "").strip())))
            updated = 0
            errors = []
            for row_number, row in enumerate(rows, start=2):
                email = row.get("email", "").strip().lower()
                artisan = Artisan.query.join(User).filter(User.email == email).first()
                if not artisan:
                    errors.append(f"Row {row_number}: no artisan account exists for {email or 'that email'}.")
                    continue
                try:
                    rating_value = row.get("rating", "").strip()
                    if rating_value:
                        rating = float(rating_value)
                        if not 0 <= rating <= 5:
                            raise ValueError
                        artisan.manual_rating = rating
                    experience_value = row.get("experience", "").strip()
                    if experience_value:
                        artisan.experience = max(int(experience_value), 0)
                except ValueError:
                    errors.append(f"Row {row_number}: rating must be 0–5 and experience must be a whole number.")
                    continue

                if row.get("verified", "").strip():
                    artisan.is_verified = row["verified"].strip().lower() in {"yes", "true", "1"}
                for field in ("phone", "location", "category", "bio"):
                    if row.get(field, "").strip():
                        setattr(artisan, field, row[field].strip())
                updated += 1

            db.session.commit()
            flash(f"Updated {updated} artisan profile(s)." + (f" {len(errors)} row(s) were skipped." if errors else ""), "success")
            return render_template("bulk_update_artisans.html", errors=errors)

        return render_template("bulk_update_artisans.html", errors=[])

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
