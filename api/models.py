import uuid
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta

class City(models.Model):
    name = models.CharField(max_length=100, unique=True)

    class Meta:
        verbose_name_plural = "Cities"

    def __str__(self):
        return self.name

class Movie(models.Model):
    title = models.CharField(max_length=255)
    description = models.TextField()
    duration_minutes = models.IntegerField()
    language = models.CharField(max_length=100)  # e.g., Hindi, English, Tamil, Telugu, Malayalam, Kannada
    genre = models.CharField(max_length=150)
    poster_url = models.URLField(max_length=500, blank=True, null=True)
    release_date = models.DateField()
    is_active = models.BooleanField(default=True)
    is_approved = models.BooleanField(default=False)
    is_featured = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.title} ({self.language})"

class Cinema(models.Model):
    STATUS_CHOICES = (
        ('PENDING', 'Pending Approval'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
        ('SUSPENDED', 'Suspended'),
    )
    name = models.CharField(max_length=255)
    address = models.TextField()
    city = models.ForeignKey(City, on_delete=models.CASCADE, related_name='cinemas')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    owner = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='owned_cinemas')
    commission_rate = models.DecimalField(max_digits=5, decimal_places=2, default=10.00)

    def __str__(self):
        return f"{self.name} - {self.city.name}"

class Screen(models.Model):
    name = models.CharField(max_length=100)  # e.g., Screen 1, Screen 2, IMAX
    cinema = models.ForeignKey(Cinema, on_delete=models.CASCADE, related_name='screens')

    def __str__(self):
        return f"{self.cinema.name} - {self.name}"

class Seat(models.Model):
    SEAT_TYPES = (
        ('CLASSIC', 'Classic'),
        ('PREMIUM', 'Premium'),
        ('RECLINER', 'Recliner'),
    )
    screen = models.ForeignKey(Screen, on_delete=models.CASCADE, related_name='seats')
    row = models.CharField(max_length=2)  # e.g., A, B, C
    number = models.IntegerField()       # e.g., 1, 2, 3
    seat_type = models.CharField(max_length=20, choices=SEAT_TYPES, default='CLASSIC')

    class Meta:
        unique_together = ('screen', 'row', 'number')
        ordering = ['row', 'number']

    def __str__(self):
        return f"{self.screen.cinema.name} - {self.screen.name} - {self.row}{self.number} ({self.seat_type})"

class Show(models.Model):
    movie = models.ForeignKey(Movie, on_delete=models.CASCADE, related_name='shows')
    screen = models.ForeignKey(Screen, on_delete=models.CASCADE, related_name='shows')
    cinema = models.ForeignKey(Cinema, on_delete=models.CASCADE, related_name='shows')  # Denormalized for convenience
    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    
    # Prices by seat type
    classic_price = models.DecimalField(max_digits=8, decimal_places=2, default=150.00)
    premium_price = models.DecimalField(max_digits=8, decimal_places=2, default=250.00)
    recliner_price = models.DecimalField(max_digits=8, decimal_places=2, default=450.00)

    class Meta:
        ordering = ['date', 'start_time']

    def __str__(self):
        return f"{self.movie.title} @ {self.cinema.name} - {self.date} {self.start_time}"

class Booking(models.Model):
    STATUS_CHOICES = (
        ('PENDING', 'Pending'),
        ('CONFIRMED', 'Confirmed'),
        ('FAILED', 'Failed'),
        ('EXPIRED', 'Expired'),
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='bookings')
    show = models.ForeignKey(Show, on_delete=models.CASCADE, related_name='bookings')
    booking_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Razorpay details
    razorpay_order_id = models.CharField(max_length=255, blank=True, null=True, unique=True)
    razorpay_payment_id = models.CharField(max_length=255, blank=True, null=True)
    razorpay_signature = models.CharField(max_length=255, blank=True, null=True)
    
    booking_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    qr_token = models.CharField(max_length=255, blank=True, null=True)
    qr_image = models.TextField(blank=True, null=True) # Storing base64 encoded PNG
    is_checked_in = models.BooleanField(default=False)
    checked_in_at = models.DateTimeField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_scanned = models.BooleanField(default=False)
    group_session = models.ForeignKey('GroupBookingSession', on_delete=models.SET_NULL, null=True, blank=True, related_name='bookings')

    def is_expired(self):
        # Bookings expire after 5 minutes if still pending
        return self.booking_status == 'PENDING' and timezone.now() - self.created_at > timedelta(minutes=5)

    def __str__(self):
        return f"Booking #{self.id} - {self.user.username} - {self.booking_status}"

class ShowSeat(models.Model):
    STATUS_CHOICES = (
        ('AVAILABLE', 'Available'),
        ('LOCKED', 'Locked'),
        ('BOOKED', 'Booked'),
    )
    show = models.ForeignKey(Show, on_delete=models.CASCADE, related_name='show_seats')
    seat = models.ForeignKey(Seat, on_delete=models.CASCADE, related_name='show_seats')
    booking = models.ForeignKey(Booking, on_delete=models.SET_NULL, blank=True, null=True, related_name='show_seats')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='AVAILABLE')
    locked_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        unique_together = ('show', 'seat')

    def is_lock_expired(self):
        if self.status == 'LOCKED' and self.locked_at:
            # 5 minute lock
            return timezone.now() - self.locked_at > timedelta(minutes=5)
        return False

    def refresh_lock_status(self):
        """Checks if the lock has expired, and if so, resets status to AVAILABLE."""
        if self.is_lock_expired():
            self.status = 'AVAILABLE'
            self.locked_at = None
            self.booking = None
            self.save()
            return True
        return False

    def __str__(self):
        return f"{self.show.movie.title} - Seat {self.seat.row}{self.seat.number} ({self.status})"

class UserProfile(models.Model):
    ROLE_CHOICES = (
        ('SUPERADMIN', 'Super Admin'),
        ('THEATRE_ADMIN', 'Theatre Admin'),
        ('USER', 'Regular User'),
    )
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='USER')
    reward_points = models.IntegerField(default=0)
    badges = models.JSONField(default=list, blank=True)

    def __str__(self):
        return f"{self.user.username}'s Profile"

class FoodItem(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=6, decimal_places=2)
    image_url = models.URLField(max_length=500, blank=True, null=True)

    def __str__(self):
        return self.name

class BookingFood(models.Model):
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name='booking_foods')
    food_item = models.ForeignKey(FoodItem, on_delete=models.CASCADE)
    quantity = models.IntegerField(default=1)

    def __str__(self):
        return f"{self.booking} - {self.food_item.name} x{self.quantity}"

class GroupBooking(models.Model):
    booking = models.OneToOneField(Booking, on_delete=models.CASCADE, related_name='group_booking')
    amount_per_person = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"Group Split for Booking #{self.booking.id}"

class GroupMemberSplit(models.Model):
    SPLIT_STATUS = (
        ('PENDING', 'Pending'),
        ('PAID', 'Paid'),
    )
    group_booking = models.ForeignKey(GroupBooking, on_delete=models.CASCADE, related_name='splits')
    email = models.EmailField()
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=SPLIT_STATUS, default='PENDING')

    def __str__(self):
        return f"{self.email} - Split: {self.status}"

class GroupBookingSession(models.Model):
    session_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    show = models.ForeignKey(Show, on_delete=models.CASCADE, related_name='group_sessions')
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_group_sessions')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Group Session {self.session_token} for Show {self.show.id}"

from django.db.models.signals import post_save
from django.dispatch import receiver

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    if hasattr(instance, 'profile'):
        instance.profile.save()


class Coupon(models.Model):
    code = models.CharField(max_length=50, unique=True)
    discount_amount = models.DecimalField(max_digits=8, decimal_places=2)
    is_active = models.BooleanField(default=True)
    expiry_date = models.DateField()

    def __str__(self):
        return self.code


class Offer(models.Model):
    cinema = models.ForeignKey(Cinema, on_delete=models.CASCADE, related_name='offers')
    code = models.CharField(max_length=50, unique=True)
    discount_percentage = models.DecimalField(max_digits=5, decimal_places=2)
    valid_from = models.DateTimeField()
    valid_to = models.DateTimeField()
    description = models.TextField()

    def __str__(self):
        return self.code


class Notification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=150)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.title}"


class ScanLog(models.Model):
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name='scan_logs', null=True, blank=True)
    scanned_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='scans')
    scan_time = models.DateTimeField(default=timezone.now)
    device = models.CharField(max_length=255, blank=True, null=True)
    ip_address = models.CharField(max_length=45, blank=True, null=True)
    status = models.CharField(max_length=50)  # SUCCESS, ALREADY_USED, INVALID, EXPIRED
    remarks = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"Scan Log #{self.id} - Booking UUID {self.booking.booking_id} - Status {self.status}"

