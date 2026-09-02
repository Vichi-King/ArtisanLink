from sqlalchemy import event

from .models import Booking, BookingProposal, Notification

_REGISTERED = False


def register_notification_hooks():
    global _REGISTERED
    if _REGISTERED:
        return
    _REGISTERED = True

    @event.listens_for(Booking, "after_insert")
    def booking_created(mapper, connection, target):
        connection.execute(
            Notification.__table__.insert().values(
                user_id=target.artisan.user_id,
                title="New booking request",
                message=f"A customer has requested your {target.service.name} service.",
                notification_type="booking",
                is_read=False,
            )
        )

    @event.listens_for(Booking, "before_update")
    def booking_status_changed(mapper, connection, target):
        state = getattr(target, "_sa_instance_state", None)
        if not state:
            return
        status_history = state.attrs.status.history
        if not status_history.has_changes() or not status_history.deleted:
            return

        old_status = status_history.deleted[0]
        new_status = target.status
        if old_status == new_status:
            return

        customer_messages = {
            "accepted": ("Booking confirmed", "Your booking request has been accepted by the artisan.", "success"),
            "declined": ("Booking declined", "The artisan has declined your booking request.", "warning"),
            "negotiating": ("Booking negotiation", "A new proposal is waiting for your response.", "booking"),
            "awaiting_customer_confirmation": ("Confirm completed work", "The artisan marked your booking as completed. Please confirm the outcome.", "booking"),
            "completed": ("Booking completed", "Your booking is now marked as completed. You can leave a review.", "success"),
            "not_completed": ("Booking update", "You reported that the booking was not completed.", "warning"),
            "pending": ("Proposal declined", "The negotiation proposal was declined and the booking is open again.", "info"),
        }
        if new_status in customer_messages:
            title, message, kind = customer_messages[new_status]
            connection.execute(Notification.__table__.insert().values(user_id=target.customer_id, title=title, message=message, notification_type=kind, is_read=False))

        artisan_messages = {
            "accepted": ("Booking accepted", "A customer booking has been accepted and confirmed.", "success"),
            "declined": ("Booking declined", "A customer booking request was declined.", "warning"),
            "completed": ("Completion confirmed", "The customer confirmed that your booking work was completed.", "success"),
            "not_completed": ("Completion disputed", "The customer reported that the booking work was not completed.", "warning"),
        }
        if new_status in artisan_messages:
            title, message, kind = artisan_messages[new_status]
            connection.execute(Notification.__table__.insert().values(user_id=target.artisan.user_id, title=title, message=message, notification_type=kind, is_read=False))

    @event.listens_for(BookingProposal, "after_insert")
    def proposal_created(mapper, connection, target):
        booking = target.booking
        if not booking:
            return
        recipient_id = booking.customer_id if target.proposed_by == "artisan" else booking.artisan.user_id
        connection.execute(Notification.__table__.insert().values(user_id=recipient_id, title="New booking proposal", message="A new price and schedule proposal is waiting for your response.", notification_type="booking", is_read=False))
