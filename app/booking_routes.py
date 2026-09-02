from datetime import datetime
from flask import render_template, request, redirect, url_for, session, flash

from . import db
from .models import User, Artisan, Booking, BookingProposal


def _parse_datetime(value):
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M")
    except (TypeError, ValueError):
        return None


def _parse_price(value):
    try:
        price = float(value)
        return price if price > 0 else None
    except (TypeError, ValueError):
        return None


def _reject_pending_proposals(booking):
    for proposal in booking.proposals:
        if proposal.status == "pending":
            proposal.status = "rejected"


def register_booking_routes(app):
    @app.route("/artisan/bookings/<int:booking_id>/negotiate", methods=["GET", "POST"])
    def negotiate_booking(booking_id):
        if session.get("user_role") != "artisan":
            flash("Only the assigned artisan can negotiate this booking.", "danger")
            return redirect(url_for("home"))

        artisan = User.query.get(session.get("user_id")).artisan_profile
        booking = Booking.query.get_or_404(booking_id)
        if not artisan or booking.artisan_id != artisan.id:
            flash("You can only negotiate your own booking requests.", "danger")
            return redirect(url_for("artisan_bookings"))
        if booking.status not in {"pending", "negotiating"}:
            flash("This booking is no longer open for negotiation.", "warning")
            return redirect(url_for("artisan_bookings"))

        if request.method == "POST":
            proposed_price = _parse_price(request.form.get("proposed_price"))
            proposed_date = _parse_datetime(request.form.get("proposed_date"))
            message = request.form.get("message", "").strip()

            if proposed_price is None:
                flash("Please enter a valid proposed price.", "danger")
                return redirect(url_for("negotiate_booking", booking_id=booking.id))
            if proposed_date is None or proposed_date < datetime.now():
                flash("Please choose a valid future date and time.", "danger")
                return redirect(url_for("negotiate_booking", booking_id=booking.id))

            _reject_pending_proposals(booking)
            db.session.add(BookingProposal(
                booking_id=booking.id,
                proposed_by="artisan",
                proposed_price=proposed_price,
                proposed_date=proposed_date,
                message=message or None,
                status="pending"
            ))
            booking.status = "negotiating"
            db.session.commit()
            flash("Your proposal has been sent to the customer.", "success")
            return redirect(url_for("artisan_bookings"))

        return render_template("booking_negotiation.html", booking=booking, role="artisan")

    @app.route("/bookings/<int:booking_id>/proposal", methods=["POST"])
    def customer_counter_proposal(booking_id):
        if session.get("user_role") != "customer":
            flash("Only the customer can make a counter-proposal.", "danger")
            return redirect(url_for("home"))

        booking = Booking.query.get_or_404(booking_id)
        if booking.customer_id != session.get("user_id"):
            flash("You can only negotiate your own bookings.", "danger")
            return redirect(url_for("my_bookings"))
        if booking.status not in {"pending", "negotiating"}:
            flash("This booking is no longer open for negotiation.", "warning")
            return redirect(url_for("my_bookings"))

        proposed_price = _parse_price(request.form.get("proposed_price"))
        proposed_date = _parse_datetime(request.form.get("proposed_date"))
        message = request.form.get("message", "").strip()
        if proposed_price is None or proposed_date is None or proposed_date < datetime.now():
            flash("Please provide a valid future date and a positive price.", "danger")
            return redirect(url_for("my_bookings"))

        _reject_pending_proposals(booking)
        db.session.add(BookingProposal(
            booking_id=booking.id,
            proposed_by="customer",
            proposed_price=proposed_price,
            proposed_date=proposed_date,
            message=message or None,
            status="pending"
        ))
        booking.status = "negotiating"
        db.session.commit()
        flash("Your counter-proposal has been sent to the artisan.", "success")
        return redirect(url_for("my_bookings"))

    @app.route("/bookings/<int:booking_id>/proposal/<int:proposal_id>/respond", methods=["POST"])
    def respond_customer_proposal(booking_id, proposal_id):
        if session.get("user_role") != "customer":
            flash("Only the customer can respond to this proposal.", "danger")
            return redirect(url_for("home"))

        booking = Booking.query.get_or_404(booking_id)
        proposal = BookingProposal.query.get_or_404(proposal_id)
        if booking.customer_id != session.get("user_id") or proposal.booking_id != booking.id:
            flash("You can only respond to proposals on your own bookings.", "danger")
            return redirect(url_for("my_bookings"))
        if proposal.status != "pending" or proposal.proposed_by != "artisan":
            flash("This proposal is no longer available.", "warning")
            return redirect(url_for("my_bookings"))

        action = request.form.get("action")
        if action == "accept":
            _reject_pending_proposals(booking)
            proposal.status = "accepted"
            booking.booking_date = proposal.proposed_date
            booking.status = "accepted"
            db.session.commit()
            flash("Proposal accepted. The booking is now confirmed.", "success")
        elif action == "reject":
            proposal.status = "rejected"
            booking.status = "pending"
            db.session.commit()
            flash("Proposal declined. The original booking request remains open.", "info")
        else:
            flash("Invalid proposal response.", "danger")
        return redirect(url_for("my_bookings"))

    @app.route("/artisan/bookings/<int:booking_id>/proposal/<int:proposal_id>/respond", methods=["POST"])
    def respond_artisan_proposal(booking_id, proposal_id):
        if session.get("user_role") != "artisan":
            flash("Only the artisan can respond to this proposal.", "danger")
            return redirect(url_for("home"))

        artisan = User.query.get(session.get("user_id")).artisan_profile
        booking = Booking.query.get_or_404(booking_id)
        proposal = BookingProposal.query.get_or_404(proposal_id)
        if not artisan or booking.artisan_id != artisan.id or proposal.booking_id != booking.id:
            flash("You can only respond to proposals on your own bookings.", "danger")
            return redirect(url_for("artisan_bookings"))
        if proposal.status != "pending" or proposal.proposed_by != "customer":
            flash("This proposal is no longer available.", "warning")
            return redirect(url_for("artisan_bookings"))

        action = request.form.get("action")
        if action == "accept":
            _reject_pending_proposals(booking)
            proposal.status = "accepted"
            booking.booking_date = proposal.proposed_date
            booking.status = "accepted"
            db.session.commit()
            flash("Customer proposal accepted. The booking is now confirmed.", "success")
        elif action == "reject":
            proposal.status = "rejected"
            booking.status = "pending"
            db.session.commit()
            flash("Customer proposal declined. The original request remains open.", "info")
        else:
            flash("Invalid proposal response.", "danger")
        return redirect(url_for("artisan_bookings"))
