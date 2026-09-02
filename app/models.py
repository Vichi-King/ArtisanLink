from . import db


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), default="customer")
    profile_picture = db.Column(db.String(255), nullable=True)

    artisan_profile = db.relationship(
        "Artisan", back_populates="user", uselist=False,
        cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<User {self.email}>"


class Artisan(db.Model):
    __tablename__ = "artisans"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), unique=True, nullable=False)
    bio = db.Column(db.Text, nullable=True)
    phone = db.Column(db.String(20), nullable=True)
    location = db.Column(db.String(100), nullable=True)
    category = db.Column(db.String(100), nullable=True)
    experience = db.Column(db.Integer, nullable=True)
    is_verified = db.Column(db.Boolean, default=False, nullable=False)
    manual_rating = db.Column(db.Numeric(2, 1), nullable=True)

    user = db.relationship("User", back_populates="artisan_profile")
    services = db.relationship(
        "Service", backref="artisan", cascade="all, delete-orphan", lazy=True
    )

    def __repr__(self):
        return f"<Artisan {self.id}>"


class Service(db.Model):
    __tablename__ = "services"

    id = db.Column(db.Integer, primary_key=True)
    artisan_id = db.Column(db.Integer, db.ForeignKey("artisans.id"), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    category = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Numeric(10, 2), nullable=False)

    def __repr__(self):
        return f"<Service {self.name}>"


class Booking(db.Model):
    __tablename__ = "bookings"

    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    artisan_id = db.Column(db.Integer, db.ForeignKey("artisans.id"), nullable=False)
    service_id = db.Column(db.Integer, db.ForeignKey("services.id"), nullable=False)
    booking_date = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(40), default="pending")

    customer = db.relationship("User")
    artisan = db.relationship("Artisan")
    service = db.relationship("Service")


class Review(db.Model):
    __tablename__ = "reviews"

    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    artisan_id = db.Column(db.Integer, db.ForeignKey("artisans.id"), nullable=False)
    rating = db.Column(db.Integer, nullable=False)
    comment = db.Column(db.Text, nullable=True)
