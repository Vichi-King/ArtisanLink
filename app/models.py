from . import db


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    full_name = db.Column(
        db.String(100),
        nullable=False
    )

    email = db.Column(
        db.String(120),
        unique=True,
        nullable=False
    )

    password_hash = db.Column(
        db.String(255),
        nullable=False
    )

    role = db.Column(
        db.String(20),
        default="customer"
    )

    profile_picture = db.Column(
        db.String(255),
        nullable=True
    )

    # Relationship with artisan profile
    artisan_profile = db.relationship(
        "Artisan",
        backref="user",
        uselist=False,
        cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<User {self.email}>"


class Artisan(db.Model):
    __tablename__ = "artisans"

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        unique=True,
        nullable=False
    )

    bio = db.Column(db.Text, nullable=True)

    phone = db.Column(db.String(20), nullable=True)

    location = db.Column(db.String(100), nullable=True)

    # Relationship with services
    services = db.relationship(
        "Service",
        backref="artisan",
        cascade="all, delete-orphan",
        lazy=True
    )

    def __repr__(self):
        return f"<Artisan {self.id}>"


class Service(db.Model):
    __tablename__ = "services"

    id = db.Column(db.Integer, primary_key=True)

    artisan_id = db.Column(
        db.Integer,
        db.ForeignKey("artisans.id"),
        nullable=False
    )

    name = db.Column(db.String(100), nullable=False)

    description = db.Column(db.Text, nullable=True)

    category = db.Column(db.String(100), nullable=False)

    price = db.Column(db.Numeric(10, 2), nullable=False)

    def __repr__(self):
        return f"<Service {self.name}>"