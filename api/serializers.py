from rest_framework import serializers
from django.contrib.auth.models import User
from .models import (
    City, Movie, Cinema, Screen, Seat, Show, ShowSeat, Booking,
    UserProfile, FoodItem, BookingFood, GroupBooking, GroupMemberSplit,
    Coupon, Offer, Notification
)

class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    role = serializers.CharField(source='profile.role', read_only=True)

    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'password', 'role')

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data.get('email', ''),
            password=validated_data['password']
        )
        return user

class CitySerializer(serializers.ModelSerializer):
    class Meta:
        model = City
        fields = '__all__'

class MovieSerializer(serializers.ModelSerializer):
    class Meta:
        model = Movie
        fields = '__all__'

class CinemaSerializer(serializers.ModelSerializer):
    city_name = serializers.CharField(source='city.name', read_only=True)
    owner_name = serializers.CharField(source='owner.username', read_only=True)
    
    class Meta:
        model = Cinema
        fields = '__all__'

class ScreenSerializer(serializers.ModelSerializer):
    cinema_name = serializers.CharField(source='cinema.name', read_only=True)
    rows_list = serializers.SerializerMethodField()
    cols_count = serializers.SerializerMethodField()

    class Meta:
        model = Screen
        fields = '__all__'

    def get_rows_list(self, obj):
        return sorted(list(set(obj.seats.values_list('row', flat=True))))

    def get_cols_count(self, obj):
        from django.db.models import Max
        max_num = obj.seats.aggregate(Max('number'))['number__max']
        return max_num or 8


class SeatSerializer(serializers.ModelSerializer):
    class Meta:
        model = Seat
        fields = '__all__'

class ShowSerializer(serializers.ModelSerializer):
    movie_title = serializers.CharField(source='movie.title', read_only=True)
    movie_poster = serializers.URLField(source='movie.poster_url', read_only=True)
    cinema_name = serializers.CharField(source='cinema.name', read_only=True)
    screen_name = serializers.CharField(source='screen.name', read_only=True)

    class Meta:
        model = Show
        fields = '__all__'

class ShowSeatSerializer(serializers.ModelSerializer):
    row = serializers.CharField(source='seat.row', read_only=True)
    number = serializers.IntegerField(source='seat.number', read_only=True)
    seat_type = serializers.CharField(source='seat.seat_type', read_only=True)
    seat_id = serializers.IntegerField(source='seat.id', read_only=True)

    class Meta:
        model = ShowSeat
        fields = ('id', 'seat_id', 'row', 'number', 'seat_type', 'status', 'locked_at')

class UserProfileSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    email = serializers.CharField(source='user.email', read_only=True)

    class Meta:
        model = UserProfile
        fields = ('id', 'username', 'email', 'reward_points', 'badges', 'role')

class FoodItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = FoodItem
        fields = '__all__'

class BookingFoodSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source='food_item.name', read_only=True)
    price = serializers.DecimalField(source='food_item.price', max_digits=6, decimal_places=2, read_only=True)

    class Meta:
        model = BookingFood
        fields = ('id', 'food_item', 'name', 'price', 'quantity')

class GroupMemberSplitSerializer(serializers.ModelSerializer):
    class Meta:
        model = GroupMemberSplit
        fields = '__all__'

class GroupBookingSerializer(serializers.ModelSerializer):
    splits = GroupMemberSplitSerializer(many=True, read_only=True)

    class Meta:
        model = GroupBooking
        fields = ('id', 'booking', 'amount_per_person', 'splits')

class BookingSerializer(serializers.ModelSerializer):
    show_details = ShowSerializer(source='show', read_only=True)
    user_name = serializers.CharField(source='user.username', read_only=True)
    seats = serializers.SerializerMethodField()
    booking_foods = BookingFoodSerializer(many=True, read_only=True)
    group_booking = GroupBookingSerializer(read_only=True)
    razorpay_key_id = serializers.SerializerMethodField()
    stripe_public_key = serializers.SerializerMethodField()
    stripe_client_secret = serializers.SerializerMethodField()

    class Meta:
        model = Booking
        fields = '__all__'

    def get_seats(self, obj):
        show_seats = obj.show_seats.all()
        return [f"{ss.seat.row}{ss.seat.number}" for ss in show_seats]

    def get_razorpay_key_id(self, obj):
        from django.conf import settings
        return getattr(settings, 'RAZORPAY_KEY_ID', 'DEMO')

    def get_stripe_public_key(self, obj):
        from django.conf import settings
        return getattr(settings, 'STRIPE_PUBLIC_KEY', 'DEMO')

    def get_stripe_client_secret(self, obj):
        from django.conf import settings
        stripe_secret_key = getattr(settings, 'STRIPE_SECRET_KEY', 'DEMO')
        if stripe_secret_key != 'DEMO' and obj.razorpay_order_id and obj.razorpay_order_id.startswith('pi_'):
            try:
                import stripe
                stripe.api_key = stripe_secret_key
                intent = stripe.PaymentIntent.retrieve(obj.razorpay_order_id)
                return intent.client_secret
            except Exception:
                pass
        return ""


class CouponSerializer(serializers.ModelSerializer):
    class Meta:
        model = Coupon
        fields = '__all__'


class OfferSerializer(serializers.ModelSerializer):
    cinema_name = serializers.CharField(source='cinema.name', read_only=True)

    class Meta:
        model = Offer
        fields = '__all__'


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = '__all__'

