import sys

from flask_bcrypt import Bcrypt

from app import create_app, db
from app.models import User


app = create_app()
bcrypt = Bcrypt(app)


def create_admin(full_name, email, password):
    with app.app_context():
        existing = User.query.filter_by(email=email).first()
        if existing:
            print(f"❌ A user with the email '{email}' already exists.")
            return

        admin = User(
            full_name=full_name,
            email=email,
            password_hash=bcrypt.generate_password_hash(password).decode("utf-8"),
            role="admin"
        )
        db.session.add(admin)
        db.session.commit()
        print(f"✅ Admin account created for {email}")


if __name__ == "__main__":
    if len(sys.argv) == 4:
        _, name, email, password = sys.argv
    else:
        name = input("Full name: ").strip()
        email = input("Email: ").strip().lower()
        password = input("Password: ").strip()

    create_admin(name, email, password)
