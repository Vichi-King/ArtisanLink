from flask import app, render_template, request, redirect, url_for, session, flash
from flask_bcrypt import Bcrypt
from werkzeug.utils import secure_filename
import os
import uuid

from . import db
from .models import User, Artisan


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


def register_routes(app):

    @app.route("/")
    def home():
        return render_template("home.html")


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

            hashed_password = generate_password_hash(
                password
            )


            new_user = User(

                full_name=full_name,

                email=email,

                password_hash=hashed_password,

                role=role,

                profile_picture=profile_picture

            )


            db.session.add(new_user)

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
        return render_template("artisans.html")

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