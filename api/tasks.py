import logging
import threading
from django.core.mail import send_mail
from django.utils.html import strip_tags
from celery import shared_task
from .models import Booking

logger = logging.getLogger(__name__)

from django.core.mail import EmailMultiAlternatives
from .pdf_utils import generate_booking_pdf

def generate_ticket_html(booking, show, user, seats_str):
  """Renders a beautiful inline-CSS styled cyberpunk ticket HTML email with embedded base64 QR."""
  qr_src = booking.qr_image if booking.qr_image else f"https://api.qrserver.com/v1/create-qr-code/?size=120x120&color=00f2fe&bgcolor=06070d&data={booking.booking_id}"
  return f"""
  <!DOCTYPE html>
  <html>
  <head>
    <meta charset="utf-8">
    <title>Your Showzy Broadcast Pass</title>
  </head>
  <body style="margin:0; padding:40px 0; background-color:#06070d; font-family:'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color:#f1f3f9;">
    <table align="center" border="0" cellpadding="0" cellspacing="0" width="600" style="background-color:#0d0f1e; border: 2px solid #00f2fe; border-radius: 16px; overflow: hidden; box-shadow: 0 0 30px rgba(0, 242, 254, 0.25);">
      <!-- Header Banner -->
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
      
      <!-- Content Body -->
      <tr>
        <td style="padding: 40px;">
          <p style="margin: 0 0 20px 0; font-size: 16px; line-height: 1.5; color: #f1f3f9;">
            Greetings <strong>{user.username}</strong>,
          </p>
          <p style="margin: 0 0 30px 0; font-size: 14px; line-height: 1.6; color: #8e9bb3;">
            Your transaction has been cleared and seating matrix is locked. Below is your official broadcast pass. Present this copy at the screen entry points.
          </p>
          
          <!-- Ticket Details Card -->
          <table border="0" cellpadding="0" cellspacing="0" width="100%" style="background-color:#14172e; border: 1px solid rgba(255, 255, 255, 0.05); border-radius: 10px; margin-bottom: 30px;">
            <tr>
              <td style="padding: 24px;">
                <table border="0" cellpadding="0" cellspacing="0" width="100%">
                  <!-- Film & Theatre -->
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
                  
                  <!-- Show details grid -->
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
          
          <!-- Secure QR scan block -->
          <table align="center" border="0" cellpadding="0" cellspacing="0" style="margin-bottom: 20px;">
            <tr>
              <td align="center" style="background-color: #06070d; border: 1px solid rgba(255,255,255,0.08); border-radius: 8px; padding: 15px;">
                <img src="{qr_src}" width="120" height="120" alt="Broadcast QR Code" style="display:block; border-radius:4px;" />
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

def send_booking_email_sync(booking_id):
  """Synchronous logic that does the database query, generates the PDF, and sends the email with PDF attachment."""
  try:
    booking = Booking.objects.get(pk=booking_id)
    if booking.booking_status != 'CONFIRMED':
      logger.warning(f"Booking {booking_id} status is {booking.booking_status}, not sending email.")
      return False
      
    show = booking.show
    user = booking.user
    show_seats = booking.show_seats.all()
    seats_str = ", ".join([f"{ss.seat.row}{ss.seat.number}" for ss in show_seats])
    
    subject = f"Ticket Confirmed! Broadcast Pass for {show.movie.title} - #SZ-{booking.id}"
    html_content = generate_ticket_html(booking, show, user, seats_str)
    text_content = strip_tags(html_content)
    
    recipients = []
    if user.email:
      recipients.append(user.email)
    
    import sys
    is_testing = 'test' in sys.argv
    
    from django.conf import settings
    audit_email = getattr(settings, 'CONFIRMATION_AUDIT_EMAIL', '')
    if audit_email and audit_email not in recipients and not is_testing:
      recipients.append(audit_email)
      
    if not recipients:
      recipients = ["customer@example.com"]
    
      pdf_bytes = generate_booking_pdf(booking)
      email.attach(f"showzy_ticket_{booking.booking_id}.pdf", pdf_bytes, "application/pdf")
    except Exception as pdf_err:
      logger.error(f"Failed to generate/attach PDF for booking {booking_id}: {str(pdf_err)}")
      
    email.send(fail_silently=False)
    logger.info(f"Successfully sent confirmation email with PDF for booking {booking_id} to {recipients}")
    return True
  except Booking.DoesNotExist:
    logger.error(f"Booking {booking_id} not found to send email.")
    return False
  except Exception as e:
    logger.exception(f"Error sending booking email for booking {booking_id}: {str(e)}")
    return False

@shared_task(name="api.tasks  
    from django.conf import settings

email = EmailMultiAlternatives(
    subject=subject,
    body=text_content,
    from_email=settings.DEFAULT_FROM_EMAIL,
    to=recipients,
)
    email.attach_alternative(html_content, "text/html")
    email.attach_alternative(html_content, "text/html")

# Generate PDF bytes and attach
try:
    pdf_bytes = generate_booking_pdf(booking)
    email.attach(
        f"showzy_ticket_{booking.booking_id}.pdf",
        pdf_bytes,
        "application/pdf",
    )
except Exception as pdf_err:
    logger.error(
        f"Failed to generate/attach PDF for booking {booking_id}: {str(pdf_err)}"
    )

email.send(fail_silently=False)
    # Generate PDF bytes and attach
    try:.send_booking_email_task")
def send_booking_email_task(booking_id):
  """Celery shared task wrapper."""
  return send_booking_email_sync(booking_id)

def is_redis_available():
  import socket
  try:
    s = socket.socket()
    s.settimeout(0.1)  # 100ms fail-fast
    s.connect(('localhost', 6379))
    s.close()
    return True
  except Exception:
    return False

def dispatch_booking_email(booking_id):
    """
    Hybrid async dispatcher:
    Tries dispatching via Celery worker if Redis is running.
    Otherwise, sends the email synchronously.
    """
    if is_redis_available():
        try:
            # Trigger via Celery
            send_booking_email_task.delay(booking_id)
            logger.info(
                f"Dispatched email task {booking_id} via Celery queue."
            )
            return
        except Exception as e:
            logger.warning(
                f"Celery queue dispatch failed: {str(e)}. Falling back to synchronous email."
            )

    # Fallback: send synchronously
    logger.info(
        f"Redis is offline. Sending email synchronously for booking {booking_id}."
    )
    send_booking_email_sync(booking_id)