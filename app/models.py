from . import db


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), default="customer")
    profile_picture = db.Column(db.String(255), nullable=True)

    artisan_profile = db.relationship("Artisan", back_populates="user", uselist=False, cascade="all, delete-orphan")

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
    services = db.relationship("Service", backref="artisan", cascade="all, delete-orphan", lazy=True)
    portfolio_items = db.relationship("PortfolioItem", back_populates="artisan", cascade="all, delete-orphan", order_by="PortfolioItem.id.desc()", lazy=True)
    availability = db.relationship("ArtisanAvailability", back_populates="artisan", cascade="all, delete-orphan", order_by="ArtisanAvailability.day_order", lazy=True)

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
    proposals = db.relationship("BookingProposal", back_populates="booking", cascade="all, delete-orphan", order_by="BookingProposal.id.desc()", lazy=True)


class BookingProposal(db.Model):
    __tablename__ = "booking_proposals"

    id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.Integer, db.ForeignKey("bookings.id", ondelete="CASCADE"), nullable=False)
    proposed_by = db.Column(db.String(20), nullable=False)
    proposed_price = db.Column(db.Numeric(10, 2), nullable=False)
    proposed_date = db.Column(db.DateTime, nullable=False)
    message = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), default="pending", nullable=False)
    created_at = db.Column(db.DateTime, default=db.func.now(), nullable=False)

    booking = db.relationship("Booking", back_populates="proposals")


class Notification(db.Model):
    __tablename__ = "notifications"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title = db.Column(db.String(150), nullable=False)
    message = db.Column(db.Text, nullable=False)
    notification_type = db.Column(db.String(30), default="info", nullable=False)
    is_read = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=db.func.now(), nullable=False)

    user = db.relationship("User", backref=db.backref("notifications", cascade="all, delete-orphan", lazy=True))


class Review(db.Model):
    __tablename__ = "reviews"

    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    artisan_id = db.Column(db.Integer, db.ForeignKey("artisans.id"), nullable=False)
    rating = db.Column(db.Integer, nullable=False)
    comment = db.Column(db.Text, nullable=True)


class PortfolioItem(db.Model):
    __tablename__ = "portfolio_items"

    id = db.Column(db.Integer, primary_key=True)
    artisan_id = db.Column(db.Integer, db.ForeignKey("artisans.id"), nullable=False)
    title = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, nullable=True)
    image = db.Column(db.String(255), nullable=True)

    artisan = db.relationship("Artisan", back_populates="portfolio_items")


class ArtisanAvailability(db.Model):
    __tablename__ = "artisan_availability"

    id = db.Column(db.Integer, primary_key=True)
    artisan_id = db.Column(db.Integer, db.ForeignKey("artisans.id"), nullable=False)
    day = db.Column(db.String(15), nullable=False)
    day_order = db.Column(db.Integer, nullable=False)
    start_time = db.Column(db.String(5), nullable=True)
    end_time = db.Column(db.String(5), nullable=True)
    is_available = db.Column(db.Boolean, default=True, nullable=False)

    artisan = db.relationship("Artisan", back_populates="availability")
