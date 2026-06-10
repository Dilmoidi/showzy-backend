import logging
import socket
import threading

from celery import shared_task
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.utils.html import strip_tags

from .models import Booking
from .pdf_utils import generate_booking_pdf

logger = logging.getLogger(__name__)


def generate_ticket_html(booking, show, user, seats_str):
    """Render the booking confirmation email HTML."""
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8">
      <title>Your Showzy Broadcast Pass</title>
    </head>
    <body style="margin:0; padding:40px 0; background-color:#06070d; font-family:'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color:#f1f3f9;">
      <table align="center" border="0" cellpadding="0" cellspacing="0" width="600" style="background-color:#0d0f1e; border: 2px solid #00f2fe; border-radius: 16px; overflow: hidden; box-shadow: 0 0 30px rgba(0, 242, 254, 0.25);">
        <tr>
          <td style="padding: 30px 40px; background: linear-gradient(135deg, #7b2cbf 0%, #0d0f1e 100%); border-bottom: 1px solid rgba(255, 255, 255, 0.08);">
            <h1 style="margin: 0; font-family: 'Orbitron', monospace; font-size: 26px; font-weight: 900; color: #00f2fe; letter-spacing: 1px; text-shadow: 0 0 10px rgba(0, 242, 254, 0.5);">
              Showzy
            </h1>
            <p style="margin: 5px 0 0 0; font-size: 13px; color: #8e9bb3; letter-spacing: 0.5px;">
              SECURE SEATING PROTOCOL VERIFIED
            </p>
          </td>
        </tr>
        <tr>
          <td style="padding: 40px;">
            <p style="margin: 0 0 20px 0; font-size: 16px; line-height: 1.5; color: #f1f3f9;">
              Greetings <strong>{user.username}</strong>,
            </p>
            <p style="margin: 0 0 30px 0; font-size: 14px; line-height: 1.6; color: #8e9bb3;">
              Your transaction has been cleared and seating matrix is locked. Below is your official broadcast pass. Present this copy at the screen entry points.
            </p>
            <table border="0" cellpadding="0" cellspacing="0" width="100%" style="background-color:#14172e; border: 1px solid rgba(255, 255, 255, 0.05); border-radius: 10px; margin-bottom: 30px;">
              <tr>
                <td style="padding: 24px;">
                  <table border="0" cellpadding="0" cellspacing="0" width="100%">
                    <tr>
                      <td colspan="2" style="padding-bottom: 20px; border-bottom: 1px dashed rgba(0, 242, 254, 0.2);">
                        <div style="font-size: 11px; color: #ff007f; font-weight: bold; letter-spacing: 1.5px; text-transform: uppercase;">
                          {show.movie.language} Broadcast
                        </div>
                        <h2 style="margin: 4px 0 0 0; font-size: 22px; color: #ffffff; font-weight: 800; line-height: 1.2;">
                          {show.movie.title}
                        </h2>
                        <div style="margin-top: 6px; font-size: 13px; color: #8e9bb3;">
                          {show.cinema.name} &bull; {show.cinema.address}
                        </div>
                      </td>
                    </tr>
                    <tr>
                      <td style="padding-top: 20px; width: 50%;">
                        <div style="font-size: 11px; color: #8e9bb3; margin-bottom: 4px;">DATE</div>
                        <strong style="font-size: 14px; color: #ffffff;">{show.date.strftime('%a, %d %b %Y')}</strong>
                      </td>
                      <td style="padding-top: 20px; width: 50%;">
                        <div style="font-size: 11px; color: #8e9bb3; margin-bottom: 4px;">SHOWTIME</div>
                        <strong style="font-size: 14px; color: #ffffff;">{show.start_time.strftime('%I:%M %p')}</strong>
                      </td>
                    </tr>
                    <tr>
                      <td style="padding-top: 15px; width: 50%;">
                        <div style="font-size: 11px; color: #8e9bb3; margin-bottom: 4px;">SCREEN (AUDI)</div>
                        <strong style="font-size: 14px; color: #ffffff;">{show.screen.name}</strong>
                      </td>
                      <td style="padding-top: 15px; width: 50%;">
                        <div style="font-size: 11px; color: #8e9bb3; margin-bottom: 4px;">SEAT LOCKS</div>
                        <strong style="font-size: 15px; color: #00f2fe; text-shadow: 0 0 5px rgba(0, 242, 254, 0.3);">{seats_str}</strong>
                      </td>
                    </tr>
                    <tr>
                      <td style="padding-top: 15px; width: 50%; border-top: 1px solid rgba(255,255,255,0.05); margin-top: 15px;">
                        <div style="font-size: 11px; color: #8e9bb3; margin-bottom: 4px;">TICKET ID</div>
                        <strong style="font-size: 14px; color: #ffffff;">#SZ-{booking.id}</strong>
                      </td>
                      <td style="padding-top: 15px; width: 50%; border-top: 1px solid rgba(255,255,255,0.05); margin-top: 15px;">
                        <div style="font-size: 11px; color: #8e9bb3; margin-bottom: 4px;">CHARGES</div>
                        <strong style="font-size: 14px; color: #ffffff;">INR {booking.total_amount} (Paid)</strong>
                      </td>
                    </tr>
                  </table>
                </td>
              </tr>
            </table>
            <table align="center" border="0" cellpadding="0" cellspacing="0" style="margin-bottom: 20px;">
              <tr>
                <td align="center" style="background-color: #06070d; border: 1px solid rgba(255,255,255,0.08); border-radius: 8px; padding: 15px;">
                  <img src="https://api.qrserver.com/v1/create-qr-code/?size=120x120&color=00f2fe&bgcolor=06070d&data=SZ-CONF-{booking.id}" width="120" height="120" alt="Broadcast QR Code" style="display:block; border-radius:4px;" />
                  <div style="font-size: 9px; color:#8e9bb3; letter-spacing:1px; margin-top:8px; text-transform:uppercase;">
                    SCAN AT AUDI ENTRY
                  </div>
                </td>
              </tr>
            </table>
            <p style="margin: 30px 0 0 0; font-size: 12px; color:#6b758a; text-align:center; line-height: 1.5;">
              This is an automated system dispatch. Do not reply to this transmission.<br>
              &copy; {booking.created_at.year} Showzy Networks. All Rights Reserved.
            </p>
          </td>
        </tr>
      </table>
    </body>
    </html>
    """


def _get_recipient_list(user):
    recipients = []
    if user.email:
        recipients.append(user.email)

    audit_email = getattr(settings, "CONFIRMATION_AUDIT_EMAIL", "")
    if audit_email and audit_email not in recipients:
        recipients.append(audit_email)

    return recipients or ["customer@example.com"]


def send_booking_email_sync(booking_id):
    """Build and send the booking confirmation email with a PDF ticket."""
    try:
        booking = (
            Booking.objects.select_related(
                "user",
                "show__movie",
                "show__cinema",
                "show__screen",
            )
            .prefetch_related("show_seats__seat")
            .get(pk=booking_id)
        )
    except Booking.DoesNotExist:
        logger.error("Booking %s not found to send email.", booking_id)
        return False

    if booking.booking_status != "CONFIRMED":
        logger.warning(
            "Booking %s status is %s, not sending email.",
            booking_id,
            booking.booking_status,
        )
        return False

    try:
        show = booking.show
        user = booking.user
        seats_str = ", ".join(
            f"{show_seat.seat.row}{show_seat.seat.number}"
            for show_seat in booking.show_seats.all()
        )

        subject = (
            f"Ticket Confirmed! Broadcast Pass for {show.movie.title} - #SZ-{booking.id}"
        )
        html_content = generate_ticket_html(booking, show, user, seats_str)
        text_content = strip_tags(html_content)
        recipients = _get_recipient_list(user)
        from_email = getattr(settings, "DEFAULT_FROM_EMAIL", None)

        message = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=from_email,
            to=recipients,
        )
        message.attach_alternative(html_content, "text/html")

        pdf_bytes = generate_booking_pdf(booking)
        message.attach(
            filename=f"showzy_ticket_{booking.id}.pdf",
            content=pdf_bytes,
            mimetype="application/pdf",
        )

        message.send(fail_silently=False)
        logger.info(
            "Successfully sent confirmation email for booking %s to %s",
            booking_id,
            user.email,
        )
        return True
    except Exception:
        logger.exception("Error sending booking email for booking %s", booking_id)
        return False


@shared_task(name="api.tasks.send_booking_email_task")
def send_booking_email_task(booking_id):
    """Celery wrapper around the synchronous email sender."""
    return send_booking_email_sync(booking_id)


def is_redis_available():
    """Fast Redis availability probe for local Celery dispatch."""
    try:
        with socket.create_connection(("localhost", 6379), timeout=0.1):
            return True
    except OSError:
        return False


def dispatch_booking_email(booking_id):
    """
    Dispatch booking email via Celery when Redis is available.
    Fall back to a background thread when the queue is unavailable.
    """
    if is_redis_available():
        try:
            send_booking_email_task.delay(booking_id)
            logger.info("Dispatched email task %s via Celery queue.", booking_id)
            return
        except Exception as exc:
            logger.warning(
                "Celery queue dispatch failed for booking %s: %s. Falling back to background thread.",
                booking_id,
                exc,
            )

    logger.info(
        "Redis is offline. Falling back to background thread email dispatcher for booking %s.",
        booking_id,
    )
    thread = threading.Thread(target=send_booking_email_sync, args=(booking_id,))
    thread.daemon = True
    thread.start()
