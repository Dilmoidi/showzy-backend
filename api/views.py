import uuid
import stripe
import decimal
from django.conf import settings
from django.db import transaction
from django.db.models import Q, Count
from django.http import HttpResponse
from django.utils import timezone
from django.contrib.auth.models import User
from django.contrib.auth import authenticate

from rest_framework import status, views, permissions, authentication
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.authtoken.models import Token
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.authentication import JWTAuthentication

from .models import (
    City, Movie, Cinema, Screen, Seat, Show, ShowSeat, Booking,
    UserProfile, FoodItem, BookingFood, GroupBooking, GroupMemberSplit,
    Coupon, Offer, Notification, ScanLog
)
from .serializers import (
    UserSerializer, CitySerializer, MovieSerializer, CinemaSerializer, ScreenSerializer,
    ShowSerializer, ShowSeatSerializer, BookingSerializer,
    UserProfileSerializer, FoodItemSerializer, GroupBookingSerializer,
    CouponSerializer, OfferSerializer, NotificationSerializer
)
from .permissions import IsTheatreAdmin, IsSuperAdmin
from .tasks import dispatch_booking_email
from .theatre_admin_views import *

# ----------------- AUTHENTICATION VIEWS -----------------

@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def register_user(request):
    serializer = UserSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.save()
        token, _ = Token.objects.get_or_create(user=user)
        return Response({
            'token': token.key,
            'user': UserSerializer(user).data
        }, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def login_user(request):
    username = request.data.get('username')
    password = request.data.get('password')
    
    if not username or not password:
        return Response({'error': 'Please provide username and password'}, status=status.HTTP_400_BAD_REQUEST)
        
    user = authenticate(username=username, password=password)
    if user:
        token, _ = Token.objects.get_or_create(user=user)
        return Response({
            'token': token.key,
            'user': UserSerializer(user).data
        })
    return Response({'error': 'Invalid credentials'}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
@authentication_classes([authentication.TokenAuthentication])
def get_user_profile(request):
    return Response(UserSerializer(request.user).data)

# --------- JWT AUTHENTICATION VIEWS ---------

@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def jwt_login(request):
    """JWT-based login for all users."""
    username = request.data.get('username')
    password = request.data.get('password')
    
    if not username or not password:
        return Response(
            {'error': 'Please provide username and password'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    user = authenticate(username=username, password=password)
    if not user:
        return Response(
            {'error': 'Invalid credentials'},
            status=status.HTTP_401_UNAUTHORIZED
        )
    
    # Get or create user profile with default role
    profile, _ = UserProfile.objects.get_or_create(user=user)
    
    # Generate JWT tokens
    refresh = RefreshToken.for_user(user)
    
    return Response({
        'access_token': str(refresh.access_token),
        'refresh_token': str(refresh),
        'user': {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'role': profile.role,
        }
    }, status=status.HTTP_200_OK)

@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def theatre_admin_login(request):
    """Theatre Admin specific login endpoint with role validation."""
    username = request.data.get('username')
    password = request.data.get('password')
    
    if not username or not password:
        return Response(
            {'error': 'Please provide username and password'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    user = authenticate(username=username, password=password)
    if not user:
        return Response(
            {'error': 'Invalid credentials'},
            status=status.HTTP_401_UNAUTHORIZED
        )
    
    # Check if user has theatre admin role
    try:
        profile = UserProfile.objects.get(user=user)
        if profile.role not in ['THEATRE_ADMIN', 'SUPERADMIN']:
            return Response(
                {'error': 'Access denied. This account does not have Theatre Admin privileges.'},
                status=status.HTTP_403_FORBIDDEN
            )
    except UserProfile.DoesNotExist:
        return Response(
            {'error': 'User profile not found. Please contact administrator.'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    # Generate JWT tokens
    refresh = RefreshToken.for_user(user)
    
    return Response({
        'access_token': str(refresh.access_token),
        'refresh_token': str(refresh),
        'user': {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'role': profile.role,
        }
    }, status=status.HTTP_200_OK)

@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def get_jwt_profile(request):
    """Get authenticated user profile with role information."""
    try:
        profile = UserProfile.objects.get(user=request.user)
        role = profile.role
    except UserProfile.DoesNotExist:
        role = 'USER'
    
    return Response({
        'id': request.user.id,
        'username': request.user.username,
        'email': request.user.email,
        'role': role,
    }, status=status.HTTP_200_OK)



@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def list_cities(request):
    cities = City.objects.all()
    serializer = CitySerializer(cities, many=True)
    return Response(serializer.data)

@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def list_movies(request):
    city_id = request.query_params.get('city')
    language = request.query_params.get('language')
    genre = request.query_params.get('genre')
    search = request.query_params.get('search')
    mood = request.query_params.get('mood')
    
    show_all = request.query_params.get('all') == 'true'
    if show_all and request.user.is_authenticated and (request.user.is_staff or request.user.is_superuser):
        movies = Movie.objects.all()
    else:
        movies = Movie.objects.filter(is_active=True, is_approved=True)
    
    # Filter by city (only show movies that have shows scheduled in that city)
    if city_id:
        movies = movies.filter(shows__cinema__city_id=city_id).distinct()
        
    if language:
        movies = movies.filter(language__iexact=language)
        
    if genre:
        movies = movies.filter(genre__icontains=genre)
        
    if search:
        movies = movies.filter(title__icontains=search)

    # Mood selection mapping to genres
    if mood:
        mood_map = {
            'happy': ['comedy', 'animation', 'adventure'],
            'melancholic': ['drama', 'romance'],
            'thrill': ['action', 'thriller', 'mystery'],
            'romantic': ['romance', 'drama'],
            'bored': ['fantasy', 'adventure', 'sci-fi']
        }
        genres_target = mood_map.get(mood.lower(), [])
        q_filter = Q()
        for g in genres_target:
            q_filter |= Q(genre__icontains=g)
        movies = movies.filter(q_filter)
        
    serializer = MovieSerializer(movies, many=True)
    return Response(serializer.data)

@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def movie_detail(request, pk):
    try:
        movie = Movie.objects.get(pk=pk, is_active=True)
        serializer = MovieSerializer(movie)
        return Response(serializer.data)
    except Movie.DoesNotExist:
        return Response({'error': 'Movie not found'}, status=status.HTTP_404_NOT_FOUND)

@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def list_movie_shows(request, movie_id):
    city_id = request.query_params.get('city')
    date_str = request.query_params.get('date') # Format: YYYY-MM-DD
    
    if not city_id or not date_str:
        return Response({'error': 'Please provide city and date query parameters'}, status=status.HTTP_400_BAD_REQUEST)
        
    shows = Show.objects.filter(movie_id=movie_id, cinema__city_id=city_id, date=date_str)
    
    # Group shows by Cinema for easier rendering on frontend
    cinema_shows = {}
    for show in shows:
        cinema_id = show.cinema.id
        if cinema_id not in cinema_shows:
            cinema_shows[cinema_id] = {
                'cinema_id': cinema_id,
                'cinema_name': show.cinema.name,
                'address': show.cinema.address,
                'shows': []
            }
        cinema_shows[cinema_id]['shows'].append(ShowSerializer(show).data)
        
    return Response(list(cinema_shows.values()))


# ----------------- SEAT & LOCKING VIEWS -----------------

def clean_expired_locks_for_show(show_id):
    """Helper to release seats whose lock has expired (5-minute window)."""
    now = timezone.now()
    expired_seats = ShowSeat.objects.filter(
        show_id=show_id, 
        status='LOCKED', 
        locked_at__lt=now - timezone.timedelta(minutes=5)
    )
    
    if expired_seats.exists():
        # Update associated bookings to EXPIRED if they are still PENDING
        booking_ids = expired_seats.values_list('booking_id', flat=True).distinct()
        Booking.objects.filter(id__in=booking_ids, booking_status='PENDING').update(booking_status='EXPIRED')
        
        # Reset expired seats
        expired_seats.update(status='AVAILABLE', locked_at=None, booking=None)

@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def get_show_seats(request, show_id):
    try:
        show = Show.objects.get(pk=show_id)
    except Show.DoesNotExist:
        return Response({'error': 'Show not found'}, status=status.HTTP_404_NOT_FOUND)
        
    # Clean expired locks first
    clean_expired_locks_for_show(show_id)
    
    show_seats = ShowSeat.objects.filter(show=show).select_related('seat')
    serializer = ShowSeatSerializer(show_seats, many=True)
    
    # Group show seats by row
    seats_by_row = {}
    for seat_data in serializer.data:
        row = seat_data['row']
        if row not in seats_by_row:
            seats_by_row[row] = []
        seats_by_row[row].append(seat_data)
        
    # Sort the seats in each row by seat number
    for row in seats_by_row:
        seats_by_row[row] = sorted(seats_by_row[row], key=lambda x: x['number'])
        
    return Response({
        'show': ShowSerializer(show).data,
        'seating_plan': seats_by_row
    })

@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
@authentication_classes([authentication.TokenAuthentication])
def lock_seats(request, show_id):
    try:
        show = Show.objects.get(pk=show_id)
    except Show.DoesNotExist:
        return Response({'error': 'Show not found'}, status=status.HTTP_444_NOT_FOUND)
        
    seat_ids = request.data.get('seat_ids', [])
    food_items = request.data.get('food_items', []) # e.g. [{"id": 1, "quantity": 2}]
    use_points = request.data.get('use_points', False)
    coupon = request.data.get('coupon', '')
    split_emails = request.data.get('split_emails', []) # list of friend emails

    if not seat_ids:
        return Response({'error': 'No seats selected'}, status=status.HTTP_400_BAD_REQUEST)
        
    # Run cleanup of expired locks first
    clean_expired_locks_for_show(show_id)
    
    try:
        with transaction.atomic():
            # Lock the selected ShowSeat rows using select_for_update to prevent race conditions
            show_seats = ShowSeat.objects.select_for_update().filter(
                show=show,
                seat_id__in=seat_ids
            ).select_related('seat')
            
            if len(show_seats) != len(seat_ids):
                return Response({'error': 'Some selected seats are invalid for this show'}, status=status.HTTP_400_BAD_REQUEST)
                
            # Verify if all selected seats are actually AVAILABLE
            unavailable_seats = [f"{ss.seat.row}{ss.seat.number}" for ss in show_seats if ss.status != 'AVAILABLE']
            if unavailable_seats:
                return Response({
                    'error': f"Seats {', '.join(unavailable_seats)} are already booked or locked by another user."
                }, status=status.HTTP_400_BAD_REQUEST)
                
            # 1. Calculate ticket cost
            ticket_amount = decimal.Decimal(0)
            for ss in show_seats:
                seat_type = ss.seat.seat_type
                if seat_type == 'PREMIUM':
                    ticket_amount += show.premium_price
                elif seat_type == 'RECLINER':
                    ticket_amount += show.recliner_price
                else:
                    ticket_amount += show.classic_price
                    
            total_amount = ticket_amount

            # 2. Create PENDING Booking
            booking = Booking.objects.create(
                user=request.user,
                show=show,
                booking_status='PENDING',
                total_amount=total_amount
            )
            
            # 3. Add Pre-ordered Food
            food_total = decimal.Decimal(0)
            for food_data in food_items:
                try:
                    food_item = FoodItem.objects.get(pk=food_data['id'])
                    qty = int(food_data['quantity'])
                    if qty > 0:
                        BookingFood.objects.create(
                            booking=booking,
                            food_item=food_item,
                            quantity=qty
                        )
                        food_total += food_item.price * qty
                except FoodItem.DoesNotExist:
                    pass
            total_amount += food_total

            # 4. Coupon Discount (CYBER50 = 50% off tickets cost, max INR 200)
            discount = decimal.Decimal(0)
            if coupon.upper() == 'CYBER50':
                discount = ticket_amount * decimal.Decimal(0.50)
                if discount > decimal.Decimal(200.00):
                    discount = decimal.Decimal(200.00)
                total_amount -= discount

            # 5. Points Redemption
            points_redeemed = 0
            profile, _ = UserProfile.objects.get_or_create(user=request.user)
            if use_points and profile.reward_points > 0:
                available_points = profile.reward_points
                # 1 point = 1 INR discount. Points can pay up to the total amount.
                if available_points >= total_amount:
                    points_redeemed = int(total_amount)
                    total_amount = decimal.Decimal(0)
                else:
                    points_redeemed = available_points
                    total_amount -= decimal.Decimal(available_points)
                
                # Deduct points from profile immediately
                profile.reward_points -= points_redeemed
                profile.save()

            booking.total_amount = total_amount
            booking.save()
            
            # 6. Update ShowSeat status to LOCKED
            now = timezone.now()
            for ss in show_seats:
                ss.status = 'LOCKED'
                ss.locked_at = now
                ss.booking = booking
                ss.save()

            # 7. Group Split setup
            amount_per_person = total_amount
            if split_emails:
                total_parties = len(split_emails) + 1
                amount_per_person = total_amount / decimal.Decimal(total_parties)
                
                group_booking = GroupBooking.objects.create(
                    booking=booking,
                    amount_per_person=amount_per_person
                )
                for email in split_emails:
                    GroupMemberSplit.objects.create(
                        group_booking=group_booking,
                        email=email,
                        amount=amount_per_person,
                        status='PENDING'
                    )

            # 8. Stripe PaymentIntent creation
            stripe_pk = getattr(settings, 'STRIPE_PUBLIC_KEY', 'DEMO')
            stripe_sk = getattr(settings, 'STRIPE_SECRET_KEY', 'DEMO')

            stripe_client_secret = None
            stripe_payment_intent_id = None
            is_demo = True

            # Pay either the full amount, or just the user's split portion
            payment_amount = amount_per_person

            if stripe_sk != 'DEMO' and stripe_pk != 'DEMO' and payment_amount > 0:
                try:
                    stripe.api_key = stripe_sk
                    intent = stripe.PaymentIntent.create(
                        amount=int(payment_amount * 100),  # Stripe uses paise (smallest INR unit)
                        currency='inr',
                        metadata={
                            'booking_id': str(booking.id),
                            'user_id': str(request.user.id),
                            'show_id': str(show.id)
                        }
                    )
                    stripe_client_secret = intent.client_secret
                    stripe_payment_intent_id = intent.id
                    booking.razorpay_order_id = stripe_payment_intent_id  # Reuse field to store PI ID
                    is_demo = False
                except stripe.error.StripeError as e:
                    # Fall back to demo mode if Stripe fails
                    booking.razorpay_order_id = f"pi_demo_{uuid.uuid4().hex[:12]}"
            else:
                booking.razorpay_order_id = f"pi_demo_{uuid.uuid4().hex[:12]}"

            booking.save()

            return Response({
                'booking_id': booking.id,
                'stripe_client_secret': stripe_client_secret,
                'stripe_public_key': stripe_pk if stripe_pk != 'DEMO' else None,
                'payment_intent_id': stripe_payment_intent_id or booking.razorpay_order_id,
                'total_amount': float(total_amount),
                'amount_per_person': float(amount_per_person),
                'discount': float(discount),
                'points_redeemed': points_redeemed,
                'is_demo': is_demo,
                'expires_at': (booking.created_at + timezone.timedelta(minutes=5)).isoformat()
            }, status=status.HTTP_201_CREATED)
            
    except Exception as e:
        return Response({'error': f"Failed to lock seats: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ----------------- PAYMENT VERIFICATION VIEW -----------------

@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
@authentication_classes([authentication.TokenAuthentication])
def verify_payment(request):
    booking_id = request.data.get('booking_id')
    payment_intent_id = request.data.get('payment_intent_id')
    is_demo_success = request.data.get('demo_success', False)

    if not booking_id:
        return Response({'error': 'Booking ID is required'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        with transaction.atomic():
            booking = Booking.objects.select_for_update().get(pk=booking_id, user=request.user)

            if booking.booking_status == 'CONFIRMED':
                return Response({'status': 'SUCCESS', 'message': 'Payment already verified'})

            if booking.is_expired():
                # Release seats
                ShowSeat.objects.filter(booking=booking).update(status='AVAILABLE', locked_at=None, booking=None)
                booking.booking_status = 'EXPIRED'
                booking.save()
                return Response({'error': 'Booking lock expired. Please search again.'}, status=status.HTTP_400_BAD_REQUEST)

            # Verify Payment via Stripe
            stripe_sk = getattr(settings, 'STRIPE_SECRET_KEY', 'DEMO')
            payment_valid = False

            if stripe_sk != 'DEMO' and payment_intent_id and not is_demo_success and booking.total_amount > 0:
                try:
                    stripe.api_key = stripe_sk
                    # Retrieve the PaymentIntent and check it succeeded
                    intent = stripe.PaymentIntent.retrieve(payment_intent_id)
                    if intent.status == 'succeeded':
                        payment_valid = True
                    else:
                        payment_valid = False
                except stripe.error.StripeError:
                    payment_valid = False
            else:
                # Demo success path or points covered full cost (0 total)
                payment_valid = is_demo_success or booking.total_amount == 0

            if payment_valid:
                # Update booking status
                booking.booking_status = 'CONFIRMED'
                booking.razorpay_payment_id = payment_intent_id or 'demo_payment'
                
                # --- GENERATE SECURE QR CODE AND TOKEN ---
                import secrets
                import json
                import qrcode
                import io
                import base64
                
                qr_token = secrets.token_urlsafe(32)
                frontend_url = getattr(settings, 'FRONTEND_URL', 'https://showzy-frontend.vercel.app')
                qr_payload = f"{frontend_url}/ticket/{booking.booking_id}?token={qr_token}"
                
                qr = qrcode.QRCode(version=1, box_size=10, border=4)
                qr.add_data(qr_payload)
                qr.make(fit=True)
                img = qr.make_image(fill_color="black", back_color="white")
                
                buffer = io.BytesIO()
                img.save(buffer, format="PNG")
                qr_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
                
                booking.qr_token = qr_token
                booking.qr_image = f"data:image/png;base64,{qr_base64}"
                booking.save()

                # Update seats status to BOOKED
                ShowSeat.objects.filter(booking=booking).update(status='BOOKED', locked_at=None)

                # --- GAMIFICATION ENGAGEMENT SYSTEM ---
                profile, _ = UserProfile.objects.get_or_create(user=request.user)

                # 1. Reward 10% of total split portion as points
                points_earned = int(booking.total_amount * decimal.Decimal(0.10))
                profile.reward_points += points_earned

                # 2. Check and unlock badges
                new_badges = []
                current_badges = list(profile.badges)

                # Badge: Cinema Pioneer (first successful booking)
                if "CINEMA_PIONEER" not in current_badges:
                    confirmed_count = Booking.objects.filter(user=request.user, booking_status='CONFIRMED').count()
                    if confirmed_count >= 1:
                        current_badges.append("CINEMA_PIONEER")
                        new_badges.append("CINEMA_PIONEER")

                # Badge: Snack Commander (pre-ordered food items)
                if "SNACK_COMMANDER" not in current_badges:
                    if booking.booking_foods.exists():
                        current_badges.append("SNACK_COMMANDER")
                        new_badges.append("SNACK_COMMANDER")

                # Badge: Squad Leader (initiated a group split payment booking)
                if "SQUAD_LEADER" not in current_badges:
                    if hasattr(booking, 'group_booking'):
                        current_badges.append("SQUAD_LEADER")
                        new_badges.append("SQUAD_LEADER")

                # Badge: Night Owl (showtime starting after 9:00 PM)
                if "NIGHT_OWL" not in current_badges:
                    show_time = booking.show.start_time
                    if show_time.hour >= 21:
                        current_badges.append("NIGHT_OWL")
                        new_badges.append("NIGHT_OWL")

                profile.badges = current_badges
                profile.save()

                # Dispatch email confirmation after transaction commits
                transaction.on_commit(
                    lambda: dispatch_booking_email(booking.id)
                )

                return Response({
                    'status': 'SUCCESS',
                    'message': 'Ticket booked successfully!',
                    'booking': BookingSerializer(booking).data,
                    'points_earned': points_earned,
                    'new_badges_unlocked': new_badges
                })
            else:
                # Mark booking failed
                booking.booking_status = 'FAILED'
                booking.save()

                # Release locked seats
                ShowSeat.objects.filter(booking=booking).update(status='AVAILABLE', locked_at=None, booking=None)

                return Response({'error': 'Payment verification failed'}, status=status.HTTP_400_BAD_REQUEST)

    except Booking.DoesNotExist:
        return Response({'error': 'Booking not found'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({'error': f"Internal server error: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
@authentication_classes([authentication.TokenAuthentication])
def cancel_booking(request, booking_id):
    """Allows user to cancel a pending booking and release seats immediately."""
    try:
        with transaction.atomic():
            booking = Booking.objects.select_for_update().get(pk=booking_id, user=request.user)
            
            if booking.booking_status != 'PENDING':
                return Response({'error': 'Only pending bookings can be cancelled'}, status=status.HTTP_400_BAD_REQUEST)
                
            booking.booking_status = 'FAILED'
            booking.save()
            
            # Release seats
            ShowSeat.objects.filter(booking=booking).update(status='AVAILABLE', locked_at=None, booking=None)
            
            return Response({'status': 'CANCELLED', 'message': 'Booking cancelled and seats released.'})
            
    except Booking.DoesNotExist:
        return Response({'error': 'Booking not found'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
@authentication_classes([authentication.TokenAuthentication])
def get_user_bookings(request):
    bookings = Booking.objects.filter(user=request.user).order_by('-created_at')
    serializer = BookingSerializer(bookings, many=True)
    return Response(serializer.data)


# ----------------- ADVANCED PROTOCOL VIEWS -----------------

@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
@authentication_classes([authentication.TokenAuthentication])
def get_ai_recommendations(request):
    """
    Analyzes booking history of user to recommend films of matching genres.
    Falls back to latest scheduled movies if booking list is empty.
    """
    user_bookings = Booking.objects.filter(user=request.user, booking_status='CONFIRMED')
    
    if not user_bookings.exists():
        # Fallback recommendations: latest active movies
        movies = Movie.objects.filter(is_active=True).order_by('-release_date')[:3]
        serializer = MovieSerializer(movies, many=True)
        return Response(serializer.data)

    # Genre weight analysis
    genre_weights = {}
    for booking in user_bookings:
        genres = booking.show.movie.genre.split(', ')
        for g in genres:
            genre_weights[g] = genre_weights.get(g, 0) + 1
            
    # Score all other movies
    movies = Movie.objects.filter(is_active=True)
    movies_scored = []
    
    for movie in movies:
        # Avoid recommending movies already booked by user
        already_booked = user_bookings.filter(show__movie=movie).exists()
        if already_booked:
            continue
            
        score = 0
        movie_genres = movie.genre.split(', ')
        for mg in movie_genres:
            score += genre_weights.get(mg, 0)
            
        movies_scored.append((movie, score))
        
    # Sort by score descending
    movies_scored = sorted(movies_scored, key=lambda x: x[1], reverse=True)
    recommended_movies = [m[0] for m in movies_scored[:3]]
    
    # Fallback if recommendations list is empty (e.g. they watched everything in genre)
    if not recommended_movies:
        recommended_movies = list(Movie.objects.filter(is_active=True)[:2])

    serializer = MovieSerializer(recommended_movies, many=True)
    return Response(serializer.data)

@api_view(['GET', 'POST', 'DELETE'])
@permission_classes([permissions.AllowAny])
def list_food_items(request):
    """Returns all canteen food items, allows creation and deletion by admin."""
    if request.method == 'GET':
        foods = FoodItem.objects.all()
        serializer = FoodItemSerializer(foods, many=True)
        return Response(serializer.data)
    elif request.method == 'POST':
        serializer = FoodItemSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    elif request.method == 'DELETE':
        food_id = request.data.get('food_id') or request.query_params.get('food_id')
        if not food_id:
            return Response({'error': 'food_id is required.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            food = FoodItem.objects.get(id=food_id)
            food.delete()
            return Response({'success': True})
        except FoodItem.DoesNotExist:
            return Response({'error': 'FoodItem not found.'}, status=status.HTTP_404_NOT_FOUND)

@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
@authentication_classes([authentication.TokenAuthentication])
def get_profile_details(request):
    """Returns User Profile stats along with user's complete booking history."""
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    bookings = Booking.objects.filter(user=request.user).order_by('-created_at')
    
    return Response({
        'profile': UserProfileSerializer(profile).data,
        'bookings': BookingSerializer(bookings, many=True).data
    })

@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
@authentication_classes([authentication.TokenAuthentication])
def simulate_split_payment(request):
    """
    Mock endpoint to simulate split payment responses from friends.
    Expects split_id and demo_success in request.
    """
    split_id = request.data.get('split_id')
    is_success = request.data.get('demo_success', False)
    
    if not split_id:
        return Response({'error': 'Split ID required'}, status=status.HTTP_400_BAD_REQUEST)
        
    try:
        split = GroupMemberSplit.objects.get(pk=split_id)
        if split.status == 'PAID':
            return Response({'status': 'SUCCESS', 'message': 'Split already paid'})
            
        if is_success:
            split.status = 'PAID'
            split.save()
            
            # Check if all split payments for this group booking are now PAID
            group_booking = split.group_booking
            all_paid = not group_booking.splits.filter(status='PENDING').exists()
            
            return Response({
                'status': 'SUCCESS',
                'message': 'Split payment simulated successfully!',
                'all_splits_paid': all_paid
            })
        else:
            return Response({'error': 'Split payment simulation failed'}, status=status.HTTP_400_BAD_REQUEST)
            
    except GroupMemberSplit.DoesNotExist:
        return Response({'error': 'Split record not found'}, status=status.HTTP_404_NOT_FOUND)


# ----------------- ADMIN DASHBOARD VIEWS -----------------

def check_role(user, allowed_roles):
    if user.is_superuser:
        return True
    try:
        return user.profile.role in allowed_roles
    except Exception:
        return False


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
@authentication_classes([authentication.TokenAuthentication, JWTAuthentication])
def create_movie(request):
    if not check_role(request.user, ['THEATRE_ADMIN', 'SUPERADMIN']):
        return Response({'error': 'Access denied: Theatre Admin or Super Admin role required.'}, status=status.HTTP_403_FORBIDDEN)
    serializer = MovieSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
@authentication_classes([authentication.TokenAuthentication, JWTAuthentication])
def schedule_show(request):
    if not check_role(request.user, ['THEATRE_ADMIN', 'SUPERADMIN']):
        return Response({'error': 'Access denied: Theatre Admin or Super Admin role required.'}, status=status.HTTP_403_FORBIDDEN)
    movie_id = request.data.get('movie_id')
    screen_id = request.data.get('screen_id')
    date = request.data.get('date')
    start_time = request.data.get('start_time')
    end_time = request.data.get('end_time')
    
    classic_price = request.data.get('classic_price', 150.00)
    premium_price = request.data.get('premium_price', 250.00)
    recliner_price = request.data.get('recliner_price', 450.00)
    
    try:
        screen = Screen.objects.get(pk=screen_id)
        movie = Movie.objects.get(pk=movie_id)
        cinema = screen.cinema
        
        with transaction.atomic():
            show = Show.objects.create(
                movie=movie,
                screen=screen,
                cinema=cinema,
                date=date,
                start_time=start_time,
                end_time=end_time,
                classic_price=classic_price,
                premium_price=premium_price,
                recliner_price=recliner_price
            )
            
            # Generate ShowSeat mapping automatically for all screen seats
            seats = Seat.objects.filter(screen=screen)
            show_seats = [
                ShowSeat(show=show, seat=seat, status='AVAILABLE')
                for seat in seats
            ]
            ShowSeat.objects.bulk_create(show_seats)
            
            return Response(ShowSerializer(show).data, status=status.HTTP_201_CREATED)
            
    except Screen.DoesNotExist:
        return Response({'error': 'Screen not found'}, status=status.HTTP_400_BAD_REQUEST)
    except Movie.DoesNotExist:
        return Response({'error': 'Movie not found'}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
@authentication_classes([authentication.TokenAuthentication])
def admin_stats(request):
    if not check_role(request.user, ['SUPERADMIN']):
        return Response({'error': 'Access denied: Super Admin role required.'}, status=status.HTTP_403_FORBIDDEN)
    
    total_bookings = Booking.objects.filter(booking_status='CONFIRMED').count()
    total_movies = Movie.objects.filter(is_active=True).count()
    total_shows = Show.objects.filter(date__gte=timezone.now().date()).count()
    total_users = User.objects.filter(is_superuser=False).count()
    
    # Cinemas breakdown
    total_cinemas = Cinema.objects.all().count()
    pending_cinemas = Cinema.objects.filter(status='PENDING').count()
    approved_cinemas = Cinema.objects.filter(status='APPROVED').count()
    suspended_cinemas = Cinema.objects.filter(status='SUSPENDED').count()
    
    # Revenue calculations
    revenue = sum(b.total_amount for b in Booking.objects.filter(booking_status='CONFIRMED'))
    
    # Most watched movies
    top_movies = Movie.objects.annotate(
        total_tickets=Count('shows__bookings__show_seats', filter=Q(shows__bookings__booking_status='CONFIRMED'))
    ).order_by('-total_tickets')[:5]
    
    most_watched = []
    for m in top_movies:
        most_watched.append({
            'id': m.id,
            'title': m.title,
            'genre': m.genre,
            'language': m.language,
            'tickets_sold': m.total_tickets or 0
        })
        
    # Revenue graph last 7 days
    import datetime
    today = timezone.now().date()
    revenue_graph = []
    for i in range(6, -1, -1):
        day = today - datetime.timedelta(days=i)
        day_start = timezone.make_aware(datetime.datetime.combine(day, datetime.time.min))
        day_end = timezone.make_aware(datetime.datetime.combine(day, datetime.time.max))
        bookings_day = Booking.objects.filter(
            booking_status='CONFIRMED',
            created_at__range=(day_start, day_end)
        )
        day_revenue = sum(b.total_amount for b in bookings_day)
        revenue_graph.append({
            'date': day.strftime('%b %d'),
            'revenue': float(day_revenue)
        })
        
    # Theatre performance
    theatre_perf = []
    for cinema in Cinema.objects.all():
        bookings_cinema = Booking.objects.filter(
            show__cinema=cinema,
            booking_status='CONFIRMED'
        )
        sales = sum(b.total_amount for b in bookings_cinema)
        commission_rate = cinema.commission_rate
        commission_earned = sales * (commission_rate / 100)
        theatre_perf.append({
            'id': cinema.id,
            'name': cinema.name,
            'city': cinema.city.name,
            'status': cinema.status,
            'bookings_count': bookings_cinema.count(),
            'sales': float(sales),
            'commission_rate': float(commission_rate),
            'commission_earned': float(commission_earned)
        })

    return Response({
        'total_bookings': total_bookings,
        'total_movies': total_movies,
        'total_shows': total_shows,
        'total_revenue': float(revenue),
        'total_users': total_users,
        'total_cinemas': total_cinemas,
        'pending_cinemas': pending_cinemas,
        'approved_cinemas': approved_cinemas,
        'suspended_cinemas': suspended_cinemas,
        'most_watched_movies': most_watched,
        'revenue_graph': revenue_graph,
        'theatre_performance': theatre_perf,
        'commission_settings': {
            'default_commission': 10.0,
            'convenience_fee': 30.0,
        }
    })

@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
@authentication_classes([authentication.TokenAuthentication, JWTAuthentication])
def admin_list_cinemas(request):
    if not check_role(request.user, ['THEATRE_ADMIN', 'SUPERADMIN']):
        return Response({'error': 'Access denied: Staff role required.'}, status=status.HTTP_403_FORBIDDEN)
    if request.user.is_superuser or request.user.profile.role == 'SUPERADMIN':
        cinemas = Cinema.objects.all()
    else:
        cinemas = Cinema.objects.filter(owner=request.user)
    serializer = CinemaSerializer(cinemas, many=True)
    return Response(serializer.data)

@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
@authentication_classes([authentication.TokenAuthentication, JWTAuthentication])
def admin_list_screens(request):
    if not check_role(request.user, ['THEATRE_ADMIN', 'SUPERADMIN']):
        return Response({'error': 'Access denied: Staff role required.'}, status=status.HTTP_403_FORBIDDEN)
    cinema_id = request.query_params.get('cinema')
    if not cinema_id:
        return Response({'error': 'Cinema ID required'}, status=status.HTTP_400_BAD_REQUEST)
    try:
        if not (request.user.is_superuser or request.user.profile.role == 'SUPERADMIN'):
            cinema = Cinema.objects.get(id=cinema_id, owner=request.user)
        else:
            cinema = Cinema.objects.get(id=cinema_id)
    except Cinema.DoesNotExist:
        return Response({'error': 'Cinema not found or access denied'}, status=status.HTTP_403_FORBIDDEN)
    screens = Screen.objects.filter(cinema=cinema)
    serializer = ScreenSerializer(screens, many=True)
    return Response(serializer.data)


# --- UPGRADED ADMIN & CINEMA MANAGER VIEWS ---

@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
@authentication_classes([authentication.TokenAuthentication])
def admin_create_cinema(request):
    if not check_role(request.user, ['SUPERADMIN']):
        return Response({'error': 'Access denied: Super Admin role required.'}, status=status.HTTP_403_FORBIDDEN)
    """Allows Super Admin (staff) to create a Cinema directly."""
    name = request.data.get('name')
    address = request.data.get('address')
    city_id = request.data.get('city_id')
    city_name = request.data.get('city_name')

    if not name or not address:
        return Response({'error': 'Name and address are required'}, status=status.HTTP_400_BAD_REQUEST)

    if city_id:
        try:
            city = City.objects.get(id=city_id)
        except City.DoesNotExist:
            return Response({'error': 'City not found'}, status=status.HTTP_404_NOT_FOUND)
    elif city_name:
        city, _ = City.objects.get_or_create(name=city_name)
    else:
        city = City.objects.first()
        if not city:
            city = City.objects.create(name='Delhi')

    cinema = Cinema.objects.create(name=name, address=address, city=city)
    return Response(CinemaSerializer(cinema).data, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
@authentication_classes([authentication.TokenAuthentication])
def admin_create_screen(request):
    if not check_role(request.user, ['THEATRE_ADMIN', 'SUPERADMIN']):
        return Response({'error': 'Access denied: Theatre Admin role required.'}, status=status.HTTP_403_FORBIDDEN)
    """Allows creating a Screen and generating its layout directly."""
    cinema_id = request.data.get('cinema_id')
    name = request.data.get('name')
    rows = request.data.get('rows', ['A', 'B', 'C', 'D', 'E'])
    cols = request.data.get('cols', 8)

    if not cinema_id or not name:
        return Response({'error': 'Cinema ID and screen name are required'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        cinema = Cinema.objects.get(id=cinema_id)
        with transaction.atomic():
            screen = Screen.objects.create(cinema=cinema, name=name)
            
            # Generate seats
            seats_to_create = []
            for row in rows:
                for num in range(1, int(cols) + 1):
                    seat_type = 'CLASSIC'
                    if row in ['A', 'B']:
                        seat_type = 'PREMIUM'
                    elif row == 'E' or row == 'VIP':
                        seat_type = 'RECLINER'
                        
                    seats_to_create.append(Seat(
                        screen=screen,
                        row=row,
                        number=num,
                        seat_type=seat_type
                    ))
            Seat.objects.bulk_create(seats_to_create)
            
        return Response(ScreenSerializer(screen).data, status=status.HTTP_201_CREATED)
    except Cinema.DoesNotExist:
        return Response({'error': 'Cinema not found'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET', 'POST'])
@permission_classes([permissions.IsAuthenticated])
@authentication_classes([authentication.TokenAuthentication])
def admin_manage_users(request):
    if not check_role(request.user, ['SUPERADMIN']):
        return Response({'error': 'Access denied: Super Admin role required.'}, status=status.HTTP_403_FORBIDDEN)
    """GET: List users. POST: Block/unblock a user OR create a new user with a role."""
    if request.method == 'GET':
        users = User.objects.filter(is_superuser=False).order_by('id')
        users_data = []
        for u in users:
            profile, _ = UserProfile.objects.get_or_create(user=u)
            users_data.append({
                'id': u.id,
                'username': u.username,
                'email': u.email,
                'is_active': u.is_active,
                'reward_points': profile.reward_points,
                'role': profile.role
            })
        return Response(users_data)
    
    elif request.method == 'POST':
        user_id = request.data.get('user_id')
        if user_id:
            block_action = request.data.get('block', None)
            try:
                user = User.objects.get(id=user_id)
                if block_action is not None:
                    user.is_active = not block_action
                    user.save()
                return Response({
                    'id': user.id,
                    'username': user.username,
                    'is_active': user.is_active
                })
            except User.DoesNotExist:
                return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)
        
        # Otherwise, creation mode
        username = request.data.get('username')
        email = request.data.get('email', '')
        password = request.data.get('password')
        role = request.data.get('role', 'THEATRE_ADMIN')
        
        if not username or not password:
            return Response({'error': 'Username and password are required.'}, status=status.HTTP_400_BAD_REQUEST)
            
        if User.objects.filter(username=username).exists():
            return Response({'error': 'Username already exists.'}, status=status.HTTP_400_BAD_REQUEST)
            
        user = User.objects.create_user(username=username, email=email, password=password)
        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.role = role
        profile.save()
        
        if role in ['SUPERADMIN', 'THEATRE_ADMIN']:
            user.is_staff = True
            user.save()
            
        return Response({
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'is_active': user.is_active,
            'reward_points': profile.reward_points,
            'role': profile.role
        }, status=status.HTTP_201_CREATED)


@api_view(['GET', 'POST', 'DELETE', 'PUT'])
@permission_classes([permissions.IsAuthenticated])
@authentication_classes([authentication.TokenAuthentication])
def admin_coupons(request):
    if not check_role(request.user, ['SUPERADMIN']):
        return Response({'error': 'Access denied: Super Admin role required.'}, status=status.HTTP_403_FORBIDDEN)
    """List, create, and delete Coupons."""
    from decimal import Decimal
    if request.method == 'GET':
        coupons = Coupon.objects.all().order_by('-id')
        return Response(CouponSerializer(coupons, many=True).data)
    
    elif request.method == 'POST':
        code = request.data.get('code')
        discount_amount = request.data.get('discount_amount')
        expiry_date = request.data.get('expiry_date')

        if not code or not discount_amount or not expiry_date:
            return Response({'error': 'All fields are required'}, status=status.HTTP_400_BAD_REQUEST)

        coupon = Coupon.objects.create(
            code=code.upper(),
            discount_amount=Decimal(str(discount_amount)),
            expiry_date=expiry_date,
            is_active=True
        )
        return Response(CouponSerializer(coupon).data, status=status.HTTP_201_CREATED)
    
    elif request.method == 'PUT':
        coupon_id = request.data.get('coupon_id')
        try:
            coupon = Coupon.objects.get(id=coupon_id)
            coupon.is_active = not coupon.is_active
            coupon.save()
            return Response(CouponSerializer(coupon).data)
        except Coupon.DoesNotExist:
            return Response({'error': 'Coupon not found'}, status=status.HTTP_404_NOT_FOUND)
    
    elif request.method == 'DELETE':
        coupon_id = request.data.get('coupon_id')
        try:
            coupon = Coupon.objects.get(id=coupon_id)
            coupon.delete()
            return Response({'status': 'Coupon deleted successfully'})
        except Coupon.DoesNotExist:
            return Response({'error': 'Coupon not found'}, status=status.HTTP_404_NOT_FOUND)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
@authentication_classes([authentication.TokenAuthentication])
def admin_broadcast(request):
    if not check_role(request.user, ['SUPERADMIN']):
        return Response({'error': 'Access denied: Super Admin role required.'}, status=status.HTTP_403_FORBIDDEN)
    """Sends global broadcast to user notifications."""
    title = request.data.get('title')
    message = request.data.get('message')

    if not title or not message:
        return Response({'error': 'Title and message are required'}, status=status.HTTP_400_BAD_REQUEST)

    users = User.objects.filter(is_superuser=False)
    notifications = []
    for u in users:
        notifications.append(Notification(
            user=u,
            title=title,
            message=message,
            is_read=False
        ))
    Notification.objects.bulk_create(notifications)
    return Response({'status': f'Notification broadcasted to {len(notifications)} users.'}, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
@authentication_classes([authentication.TokenAuthentication])
def cinema_bookings(request):
    if not check_role(request.user, ['THEATRE_ADMIN', 'SUPERADMIN']):
        return Response({'error': 'Access denied: Theatre Admin role required.'}, status=status.HTTP_403_FORBIDDEN)
    """Detailed booking reports."""
    bookings = Booking.objects.all().order_by('-created_at')
    bookings_data = []
    for b in bookings:
        seats = ", ".join(f"{ss.seat.row}{ss.seat.number}" for ss in b.show_seats.all())
        bookings_data.append({
            'id': b.id,
            'movie_title': b.show.movie.title,
            'screen_name': b.show.screen.name,
            'theatre_name': b.show.cinema.name,
            'customer_username': b.user.username,
            'customer_email': b.user.email,
            'seats': seats,
            'booking_date': b.created_at.strftime('%Y-%m-%d %H:%M'),
            'showtime': f"{b.show.date} {b.show.start_time}",
            'final_amount': float(b.total_amount),
            'status': b.booking_status,
            'is_scanned': b.is_scanned
        })
    return Response(bookings_data)


@api_view(['GET', 'POST', 'DELETE'])
@permission_classes([permissions.IsAuthenticated])
@authentication_classes([authentication.TokenAuthentication])
def cinema_offers(request):
    if not check_role(request.user, ['THEATRE_ADMIN', 'SUPERADMIN']):
        return Response({'error': 'Access denied: Theatre Admin role required.'}, status=status.HTTP_403_FORBIDDEN)
    """List, create, and delete cinema-specific offers."""
    from decimal import Decimal
    if request.method == 'GET':
        offers = Offer.objects.all().order_by('-id')
        return Response(OfferSerializer(offers, many=True).data)
    
    elif request.method == 'POST':
        cinema_id = request.data.get('cinema_id')
        code = request.data.get('code')
        discount_percentage = request.data.get('discount_percentage')
        valid_from = request.data.get('valid_from')
        valid_to = request.data.get('valid_to')
        description = request.data.get('description')

        try:
            cinema = Cinema.objects.get(id=cinema_id)
            offer = Offer.objects.create(
                cinema=cinema,
                code=code.upper(),
                discount_percentage=Decimal(str(discount_percentage)),
                valid_from=valid_from,
                valid_to=valid_to,
                description=description
            )
            return Response(OfferSerializer(offer).data, status=status.HTTP_201_CREATED)
        except Cinema.DoesNotExist:
            return Response({'error': 'Cinema not found'}, status=status.HTTP_404_NOT_FOUND)
    
    elif request.method == 'DELETE':
        offer_id = request.data.get('offer_id')
        try:
            offer = Offer.objects.get(id=offer_id)
            offer.delete()
            return Response({'status': 'Offer deleted successfully'})
        except Offer.DoesNotExist:
            return Response({'error': 'Offer not found'}, status=status.HTTP_444_NOT_FOUND)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
@authentication_classes([authentication.TokenAuthentication])
def cinema_validate_ticket(request):
    if not check_role(request.user, ['THEATRE_ADMIN', 'SUPERADMIN']):
        return Response({'error': 'Access denied: Theatre Admin role required.'}, status=status.HTTP_403_FORBIDDEN)
    """Validate ticket scans."""
    token = request.data.get('token', '').strip()
    
    booking_id = None
    if token.startswith("TICKET-"):
        parts = token.split('-')
        if len(parts) >= 2:
            booking_id = parts[1]
    else:
        booking_id = token

    if not booking_id:
        return Response({'error': 'Invalid ticket token or code format.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        booking = Booking.objects.get(id=booking_id)
        
        if booking.booking_status != 'CONFIRMED':
            return Response({
                'success': False,
                'error': f"Ticket status is {booking.booking_status}. Check-in denied."
            }, status=status.HTTP_400_BAD_REQUEST)

        if booking.is_scanned:
            return Response({
                'success': False,
                'error': "Ticket has ALREADY been scanned and checked in!"
            }, status=status.HTTP_400_BAD_REQUEST)

        booking.is_scanned = True
        booking.save()

        seats = ", ".join(f"{ss.seat.row}{ss.seat.number}" for ss in booking.show_seats.all())
        return Response({
            'success': True,
            'message': "Ticket validated and checked in successfully!",
            'booking_details': {
                'id': booking.id,
                'customer': booking.user.username,
                'movie': booking.show.movie.title,
                'screen': booking.show.screen.name,
                'seats': seats,
                'showtime': f"{booking.show.date} {booking.show.start_time}"
            }
        })
    except Booking.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Ticket not found in system.'
        }, status=status.HTTP_404_NOT_FOUND)
    except ValueError:
        return Response({'error': 'Invalid ticket code value.'}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
@authentication_classes([authentication.TokenAuthentication])
def cinema_show_notifications(request):
    if not check_role(request.user, ['THEATRE_ADMIN', 'SUPERADMIN']):
        return Response({'error': 'Access denied: Theatre Admin role required.'}, status=status.HTTP_403_FORBIDDEN)
    """Alert customer booking holders for a show."""
    show_id = request.data.get('show_id')
    message = request.data.get('message')

    if not show_id or not message:
        return Response({'error': 'Show ID and message are required.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        show = Show.objects.get(id=show_id)
        bookings = Booking.objects.filter(show=show, booking_status='CONFIRMED')
        users = User.objects.filter(bookings__in=bookings).distinct()

        notifications = []
        for u in users:
            notifications.append(Notification(
                user=u,
                title=f"Update on Show: {show.movie.title}",
                message=message,
                is_read=False
            ))
        Notification.objects.bulk_create(notifications)
        return Response({'status': f'Notification sent to {len(notifications)} ticket holders.'}, status=status.HTTP_201_CREATED)
    except Show.DoesNotExist:
        return Response({'error': 'Show not found.'}, status=status.HTTP_404_NOT_FOUND)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
@authentication_classes([authentication.TokenAuthentication])
def admin_approve_cinema(request):
    if not check_role(request.user, ['SUPERADMIN']):
        return Response({'error': 'Access denied: Super Admin role required.'}, status=status.HTTP_403_FORBIDDEN)
    cinema_id = request.data.get('cinema_id')
    action = request.data.get('action') # 'APPROVE', 'REJECT', 'SUSPEND'
    
    if not cinema_id or not action:
        return Response({'error': 'Cinema ID and action are required.'}, status=status.HTTP_400_BAD_REQUEST)
        
    try:
        cinema = Cinema.objects.get(id=cinema_id)
        if action == 'APPROVE':
            cinema.status = 'APPROVED'
        elif action == 'REJECT':
            cinema.status = 'REJECTED'
        elif action == 'SUSPEND':
            cinema.status = 'SUSPENDED'
        else:
            return Response({'error': 'Invalid action.'}, status=status.HTTP_400_BAD_REQUEST)
        cinema.save()
        return Response({'status': f'Cinema status updated to {cinema.status}.', 'cinema': CinemaSerializer(cinema).data})
    except Cinema.DoesNotExist:
        return Response({'error': 'Cinema not found.'}, status=status.HTTP_404_NOT_FOUND)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
@authentication_classes([authentication.TokenAuthentication])
def admin_edit_cinema(request):
    if not check_role(request.user, ['SUPERADMIN']):
        return Response({'error': 'Access denied: Super Admin role required.'}, status=status.HTTP_403_FORBIDDEN)
    cinema_id = request.data.get('cinema_id')
    name = request.data.get('name')
    address = request.data.get('address')
    commission_rate = request.data.get('commission_rate')
    owner_username = request.data.get('owner_username')
    
    if not cinema_id:
        return Response({'error': 'Cinema ID is required.'}, status=status.HTTP_400_BAD_REQUEST)
        
    try:
        cinema = Cinema.objects.get(id=cinema_id)
        if name:
            cinema.name = name
        if address:
            cinema.address = address
        if commission_rate is not None:
            cinema.commission_rate = decimal.Decimal(str(commission_rate))
        if owner_username:
            try:
                owner_user = User.objects.get(username=owner_username)
                cinema.owner = owner_user
            except User.DoesNotExist:
                return Response({'error': f'User {owner_username} not found.'}, status=status.HTTP_400_BAD_REQUEST)
        cinema.save()
        return Response({'status': 'Cinema updated successfully.', 'cinema': CinemaSerializer(cinema).data})
    except Cinema.DoesNotExist:
        return Response({'error': 'Cinema not found.'}, status=status.HTTP_404_NOT_FOUND)


@api_view(['DELETE'])
@permission_classes([permissions.IsAuthenticated])
@authentication_classes([authentication.TokenAuthentication])
def admin_delete_cinema(request):
    if not check_role(request.user, ['SUPERADMIN']):
        return Response({'error': 'Access denied: Super Admin role required.'}, status=status.HTTP_403_FORBIDDEN)
    cinema_id = request.data.get('cinema_id') or request.query_params.get('cinema_id')
    if not cinema_id:
        return Response({'error': 'Cinema ID is required.'}, status=status.HTTP_400_BAD_REQUEST)
    try:
        cinema = Cinema.objects.get(id=cinema_id)
        cinema.delete()
        return Response({'status': 'Cinema deleted successfully.'})
    except Cinema.DoesNotExist:
        return Response({'error': 'Cinema not found.'}, status=status.HTTP_404_NOT_FOUND)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
@authentication_classes([authentication.TokenAuthentication])
def admin_approve_movie(request):
    if not check_role(request.user, ['SUPERADMIN']):
        return Response({'error': 'Access denied: Super Admin role required.'}, status=status.HTTP_403_FORBIDDEN)
    movie_id = request.data.get('movie_id')
    action = request.data.get('action') # 'APPROVE', 'REJECT', 'FEATURE', 'UNFEATURE', 'DELETE'
    
    if not movie_id or not action:
        return Response({'error': 'Movie ID and action are required.'}, status=status.HTTP_400_BAD_REQUEST)
        
    try:
        movie = Movie.objects.get(id=movie_id)
        if action == 'APPROVE':
            movie.is_approved = True
        elif action == 'REJECT':
            movie.is_approved = False
        elif action == 'FEATURE':
            movie.is_featured = True
        elif action == 'UNFEATURE':
            movie.is_featured = False
        elif action == 'DELETE':
            movie.delete()
            return Response({'status': 'Movie deleted successfully.'})
        else:
            return Response({'error': 'Invalid action.'}, status=status.HTTP_400_BAD_REQUEST)
        movie.save()
        return Response({'status': f'Movie action {action} complete.', 'movie': MovieSerializer(movie).data})
    except Movie.DoesNotExist:
        return Response({'error': 'Movie not found.'}, status=status.HTTP_404_NOT_FOUND)


# ----------------- QR VALIDATION & TICKET APIs -----------------

@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
@authentication_classes([authentication.TokenAuthentication])
def verify_ticket(request):
    booking_id = request.data.get('booking_id')
    token = request.data.get('token')
    
    device = request.META.get('HTTP_USER_AGENT', 'Unknown Device')
    ip_address = request.META.get('REMOTE_ADDR', '0.0.0.0')
    
    if not booking_id or not token:
        return Response({
            'success': False,
            'message': 'Invalid Ticket'
        }, status=status.HTTP_400_BAD_REQUEST)
        
    try:
        # Match UUID booking_id
        booking = Booking.objects.get(booking_id=booking_id)
        
        # Verify Token
        if booking.qr_token != token:
            ScanLog.objects.create(
                booking=booking,
                scanned_by=request.user,
                device=device,
                ip_address=ip_address,
                status='INVALID',
                remarks='Token mismatch'
            )
            return Response({
                'success': False,
                'message': 'Invalid Ticket'
            }, status=status.HTTP_400_BAD_REQUEST)
            
        # Verify Payment & Status
        if booking.booking_status != 'CONFIRMED':
            ScanLog.objects.create(
                booking=booking,
                scanned_by=request.user,
                device=device,
                ip_address=ip_address,
                status='INVALID',
                remarks=f'Booking status is {booking.booking_status}'
            )
            return Response({
                'success': False,
                'message': 'Invalid Ticket'
            }, status=status.HTTP_400_BAD_REQUEST)
            
        # Verify Duplicate Entry
        if booking.is_checked_in:
            ScanLog.objects.create(
                booking=booking,
                scanned_by=request.user,
                device=device,
                ip_address=ip_address,
                status='ALREADY_USED',
                remarks='Duplicate scan check'
            )
            checked_in_time_str = booking.checked_in_at.strftime('%Y-%m-%d %H:%M:%S') if booking.checked_in_at else "Unknown"
            return Response({
                'success': False,
                'message': 'Ticket Already Used',
                'previous_scan_time': checked_in_time_str
            }, status=status.HTTP_400_BAD_REQUEST)
            
        # Verify Expiration (Show time has passed beyond allowed entry window e.g., 2 hours)
        show = booking.show
        import datetime
        show_datetime = timezone.make_aware(datetime.datetime.combine(show.date, show.start_time))
        if timezone.now() > show_datetime + timezone.timedelta(hours=2):
            ScanLog.objects.create(
                booking=booking,
                scanned_by=request.user,
                device=device,
                ip_address=ip_address,
                status='EXPIRED',
                remarks='Show expired past entry window'
            )
            return Response({
                'success': False,
                'message': 'Ticket Expired'
            }, status=status.HTTP_400_BAD_REQUEST)
            
        # Grant entry!
        with transaction.atomic():
            booking = Booking.objects.select_for_update().get(id=booking.id)
            booking.is_checked_in = True
            booking.checked_in_at = timezone.now()
            booking.save()
            
            ScanLog.objects.create(
                booking=booking,
                scanned_by=request.user,
                device=device,
                ip_address=ip_address,
                status='SUCCESS',
                remarks='Successful entrance check-in'
            )
            
        seats_str = ", ".join(f"{ss.seat.row}{ss.seat.number}" for ss in booking.show_seats.all())
        check_in_time_str = booking.checked_in_at.strftime('%Y-%m-%d %H:%M:%S')
        
        return Response({
            'success': True,
            'message': 'Entry Allowed',
            'booking_details': {
                'id': booking.id,
                'booking_id': str(booking.booking_id),
                'customer': booking.user.username,
                'movie': show.movie.title,
                'screen': show.screen.name,
                'seats': seats_str,
                'showtime': f"{show.date} {show.start_time}",
                'checked_in_at': check_in_time_str
            }
        })
        
    except Booking.DoesNotExist:
        # Create a ScanLog without a booking reference for invalid scans
        ScanLog.objects.create(
            booking=None,
            scanned_by=request.user,
            device=device,
            ip_address=ip_address,
            status='INVALID',
            remarks=f'Booking not found for UUID: {booking_id}'
        )
        return Response({
            'success': False,
            'message': 'Invalid Ticket'
        }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
@authentication_classes([authentication.TokenAuthentication])
def list_bookings_api(request):
    if check_role(request.user, ['SUPERADMIN', 'THEATRE_ADMIN']):
        bookings = Booking.objects.all().order_by('-created_at')
    else:
        bookings = Booking.objects.filter(user=request.user).order_by('-created_at')
    serializer = BookingSerializer(bookings, many=True)
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
@authentication_classes([authentication.TokenAuthentication])
def booking_detail_api(request, booking_id):
    try:
        if len(booking_id) == 36 or '-' in booking_id:
            booking = Booking.objects.get(booking_id=booking_id)
        else:
            booking = Booking.objects.get(id=booking_id)
            
        if booking.user != request.user and not check_role(request.user, ['SUPERADMIN', 'THEATRE_ADMIN']):
            return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)
            
        serializer = BookingSerializer(booking)
        return Response(serializer.data)
    except Booking.DoesNotExist:
        return Response({'error': 'Booking not found'}, status=status.HTTP_404_NOT_FOUND)


@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def ticket_detail_api(request, booking_id):
    try:
        if len(booking_id) == 36 or '-' in booking_id:
            booking = Booking.objects.get(booking_id=booking_id)
        else:
            booking = Booking.objects.get(id=booking_id)
            
        token = request.query_params.get('token')
        
        is_authenticated = request.user and request.user.is_authenticated
        is_owner = is_authenticated and booking.user == request.user
        is_staff = is_authenticated and (request.user.is_staff or request.user.is_superuser or check_role(request.user, ['THEATRE_ADMIN', 'SUPERADMIN']))
        
        if not is_owner and not is_staff:
            if not token or booking.qr_token != token:
                return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)
                
        serializer = BookingSerializer(booking)
        return Response(serializer.data)
    except Booking.DoesNotExist:
        return Response({'error': 'Ticket not found'}, status=status.HTTP_404_NOT_FOUND)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
@authentication_classes([authentication.TokenAuthentication])
def list_scan_logs_api(request):
    if not check_role(request.user, ['SUPERADMIN', 'THEATRE_ADMIN']):
        return Response({'error': 'Access denied'}, status=status.HTTP_403_FORBIDDEN)
        
    logs = ScanLog.objects.all().select_related('booking', 'scanned_by', 'booking__show__movie').order_by('-scan_time')
    
    search_query = request.query_params.get('search')
    status_filter = request.query_params.get('status')
    
    if search_query:
        logs = logs.filter(
            Q(booking__booking_id__icontains=search_query) |
            Q(booking__show__movie__title__icontains=search_query) |
            Q(scanned_by__username__icontains=search_query)
        )
    if status_filter:
        logs = logs.filter(status=status_filter)
        
    logs_data = []
    for log in logs:
        logs_data.append({
            'id': log.id,
            'booking_id': str(log.booking.booking_id) if log.booking else 'INVALID',
            'movie_title': log.booking.show.movie.title if (log.booking and log.booking.show) else 'N/A',
            'customer': log.booking.user.username if log.booking else 'N/A',
            'scanner': log.scanned_by.username if log.scanned_by else 'System',
            'scan_time': log.scan_time.strftime('%Y-%m-%d %H:%M:%S'),
            'device': log.device,
            'ip_address': log.ip_address,
            'status': log.status,
            'remarks': log.remarks
        })
        
    return Response(logs_data)


from .pdf_utils import generate_booking_pdf

@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def download_ticket_pdf(request, booking_id=None):
    if not booking_id:
        booking_id = request.query_params.get('booking_id')
    if not booking_id:
        return Response({'error': 'Booking ID required'}, status=status.HTTP_400_BAD_REQUEST)
        
    try:
        if len(booking_id) == 36 or '-' in booking_id:
            booking = Booking.objects.get(booking_id=booking_id)
        else:
            booking = Booking.objects.get(id=booking_id)
            
        pdf_bytes = generate_booking_pdf(booking)
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="showzy_ticket_{booking_id}.pdf"'
        return response
    except Booking.DoesNotExist:
        return Response({'error': 'Booking not found'}, status=status.HTTP_404_NOT_FOUND)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
@authentication_classes([authentication.TokenAuthentication])
def mock_book_seats(request):
    show_id = request.data.get('show_id')
    if not show_id:
        return Response({'error': 'show_id is required'}, status=status.HTTP_400_BAD_REQUEST)
    return lock_seats(request._request, show_id=show_id)


# ─── COLLABORATIVE GROUP BOOKING SESSION VIEWS ────────────────────────────────
from api.models import GroupBookingSession

@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
@authentication_classes([authentication.TokenAuthentication])
def create_group_session(request, show_id):
    try:
        show = Show.objects.get(pk=show_id)
    except Show.DoesNotExist:
        return Response({'error': 'Show not found'}, status=status.HTTP_404_NOT_FOUND)
        
    session = GroupBookingSession.objects.create(
        show=show,
        created_by=request.user
    )
    return Response({'session_token': str(session.session_token)})


@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def get_group_session_seats(request, token):
    try:
        session = GroupBookingSession.objects.get(session_token=token)
    except (GroupBookingSession.DoesNotExist, ValueError):
        return Response({'error': 'Group booking session not found'}, status=status.HTTP_444_NOT_FOUND)
        
    clean_expired_locks_for_show(session.show.id)
    
    show_seats = ShowSeat.objects.filter(show=session.show).select_related('seat', 'booking', 'booking__user')
    
    seats_by_row = {}
    for ss in show_seats:
        row = ss.seat.row
        if row not in seats_by_row:
            seats_by_row[row] = []
            
        seat_data = {
            'seat_id': ss.seat.id,
            'row': ss.seat.row,
            'number': ss.seat.number,
            'seat_type': ss.seat.seat_type,
            'status': ss.status,
            'group_lock_status': 'AVAILABLE',
            'locked_by_username': None
        }
        
        if ss.status == 'LOCKED' and ss.booking:
            if ss.booking.group_session == session:
                if request.user.is_authenticated and ss.booking.user == request.user:
                    seat_data['group_lock_status'] = 'SELECTED_BY_ME'
                else:
                    seat_data['group_lock_status'] = 'SELECTED_BY_FRIEND'
                    seat_data['locked_by_username'] = ss.booking.user.username
            else:
                seat_data['group_lock_status'] = 'LOCKED_BY_OTHER'
        elif ss.status == 'BOOKED':
            seat_data['group_lock_status'] = 'LOCKED_BY_OTHER'
            
        seats_by_row[row].append(seat_data)
        
    for row in seats_by_row:
        seats_by_row[row] = sorted(seats_by_row[row], key=lambda x: x['number'])
        
    return Response({
        'show': ShowSerializer(session.show).data,
        'session_token': str(session.session_token),
        'seating_plan': seats_by_row
    })


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
@authentication_classes([authentication.TokenAuthentication])
def lock_group_seats(request, token):
    try:
        session = GroupBookingSession.objects.get(session_token=token)
    except (GroupBookingSession.DoesNotExist, ValueError):
        return Response({'error': 'Group booking session not found'}, status=status.HTTP_444_NOT_FOUND)
        
    seat_ids = request.data.get('seat_ids', [])
    if not seat_ids:
        return Response({'error': 'No seats specified'}, status=status.HTTP_400_BAD_REQUEST)
        
    clean_expired_locks_for_show(session.show.id)
    
    try:
        with transaction.atomic():
            show_seats = ShowSeat.objects.select_for_update().filter(
                show=session.show,
                seat_id__in=seat_ids
            ).select_related('seat')
            
            if len(show_seats) != len(seat_ids):
                return Response({'error': 'Some selected seats are invalid'}, status=status.HTTP_400_BAD_REQUEST)
                
            for ss in show_seats:
                if ss.status != 'AVAILABLE':
                    if ss.booking and ss.booking.group_session == session and ss.booking.user == request.user:
                        continue
                    return Response({'error': f"Seat {ss.seat.row}{ss.seat.number} is unavailable"}, status=status.HTTP_400_BAD_REQUEST)
            
            booking, created = Booking.objects.get_or_create(
                user=request.user,
                group_session=session,
                show=session.show,
                booking_status='PENDING',
                defaults={'total_amount': 0}
            )
            
            now = timezone.now()
            ticket_amount = decimal.Decimal(0)
            for ss in show_seats:
                ss.status = 'LOCKED'
                ss.locked_at = now
                ss.booking = booking
                ss.save()
                
            locked_seats = ShowSeat.objects.filter(booking=booking)
            for ls in locked_seats:
                seat_type = ls.seat.seat_type
                if seat_type == 'PREMIUM':
                    ticket_amount += session.show.premium_price
                elif seat_type == 'RECLINER':
                    ticket_amount += session.show.recliner_price
                else:
                    ticket_amount += session.show.classic_price
                    
            booking.total_amount = ticket_amount
            booking.save()
            
            return Response({
                'success': True,
                'booking_id': booking.id,
                'total_amount': float(booking.total_amount)
            })
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
@authentication_classes([authentication.TokenAuthentication])
def unlock_group_seats(request, token):
    try:
        session = GroupBookingSession.objects.get(session_token=token)
    except (GroupBookingSession.DoesNotExist, ValueError):
        return Response({'error': 'Group booking session not found'}, status=status.HTTP_444_NOT_FOUND)
        
    seat_ids = request.data.get('seat_ids', [])
    if not seat_ids:
        return Response({'error': 'No seats specified'}, status=status.HTTP_400_BAD_REQUEST)
        
    try:
        with transaction.atomic():
            show_seats = ShowSeat.objects.select_for_update().filter(
                show=session.show,
                seat_id__in=seat_ids,
                status='LOCKED',
                booking__user=request.user,
                booking__group_session=session
            )
            
            for ss in show_seats:
                booking = ss.booking
                ss.status = 'AVAILABLE'
                ss.locked_at = None
                ss.booking = None
                ss.save()
                
                ticket_amount = decimal.Decimal(0)
                locked_seats = ShowSeat.objects.filter(booking=booking)
                if locked_seats.exists():
                    for ls in locked_seats:
                        seat_type = ls.seat.seat_type
                        if seat_type == 'PREMIUM':
                            ticket_amount += session.show.premium_price
                        elif seat_type == 'RECLINER':
                            ticket_amount += session.show.recliner_price
                        else:
                            ticket_amount += session.show.classic_price
                    booking.total_amount = ticket_amount
                    booking.save()
                else:
                    booking.delete()
                    
            return Response({'success': True})
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
@authentication_classes([authentication.TokenAuthentication])
def checkout_group_seats(request, token):
    try:
        session = GroupBookingSession.objects.get(session_token=token)
    except (GroupBookingSession.DoesNotExist, ValueError):
        return Response({'error': 'Group booking session not found'}, status=status.HTTP_444_NOT_FOUND)
        
    try:
        with transaction.atomic():
            booking = Booking.objects.select_for_update().get(
                user=request.user,
                group_session=session,
                booking_status='PENDING'
            )
            
            stripe_pk = getattr(settings, 'STRIPE_PUBLIC_KEY', 'DEMO')
            stripe_sk = getattr(settings, 'STRIPE_SECRET_KEY', 'DEMO')

            stripe_client_secret = None
            stripe_payment_intent_id = None
            is_demo = True

            payment_amount = booking.total_amount

            if stripe_sk != 'DEMO' and stripe_pk != 'DEMO' and payment_amount > 0:
                try:
                    import stripe
                    stripe.api_key = stripe_sk
                    intent = stripe.PaymentIntent.create(
                        amount=int(payment_amount * 100),
                        currency='inr',
                        metadata={
                            'booking_id': str(booking.id),
                            'user_id': str(request.user.id),
                            'show_id': str(session.show.id)
                        }
                    )
                    stripe_client_secret = intent.client_secret
                    stripe_payment_intent_id = intent.id
                    booking.razorpay_order_id = stripe_payment_intent_id
                    is_demo = False
                except Exception:
                    booking.razorpay_order_id = f"pi_demo_{uuid.uuid4().hex[:12]}"
            else:
                booking.razorpay_order_id = f"pi_demo_{uuid.uuid4().hex[:12]}"

            booking.save()

            return Response({
                'booking_id': booking.id,
                'stripe_client_secret': stripe_client_secret,
                'stripe_public_key': stripe_pk if stripe_pk != 'DEMO' else None,
                'payment_intent_id': stripe_payment_intent_id or booking.razorpay_order_id,
                'total_amount': float(booking.total_amount),
                'is_demo': is_demo,
                'expires_at': (booking.created_at + timezone.timedelta(minutes=5)).isoformat()
            })
    except Booking.DoesNotExist:
        return Response({'error': 'No pending booking found for you in this session'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
@authentication_classes([authentication.TokenAuthentication])
def add_food_to_booking(request, booking_id):
    try:
        booking = Booking.objects.get(pk=booking_id, user=request.user)
    except Booking.DoesNotExist:
        return Response({'error': 'Booking not found'}, status=status.HTTP_404_NOT_FOUND)
        
    food_items = request.data.get('food_items', [])
    try:
        with transaction.atomic():
            booking.booking_foods.all().delete()
            
            ticket_amount = decimal.Decimal(0)
            show_seats = ShowSeat.objects.filter(booking=booking)
            for ss in show_seats:
                seat_type = ss.seat.seat_type
                if seat_type == 'PREMIUM':
                    ticket_amount += booking.show.premium_price
                elif seat_type == 'RECLINER':
                    ticket_amount += booking.show.recliner_price
                else:
                    ticket_amount += booking.show.classic_price
            
            food_total = decimal.Decimal(0)
            for food_data in food_items:
                try:
                    food_item = FoodItem.objects.get(pk=food_data['id'])
                    qty = int(food_data['quantity'])
                    if qty > 0:
                        BookingFood.objects.create(
                            booking=booking,
                            food_item=food_item,
                            quantity=qty
                        )
                        food_total += food_item.price * qty
                except FoodItem.DoesNotExist:
                    pass
            
            booking.total_amount = ticket_amount + food_total
            
            stripe_sk = getattr(settings, 'STRIPE_SECRET_KEY', 'DEMO')
            if stripe_sk != 'DEMO' and booking.total_amount > 0 and booking.razorpay_order_id and not booking.razorpay_order_id.startswith('pi_demo_'):
                try:
                    import stripe
                    stripe.api_key = stripe_sk
                    stripe.PaymentIntent.modify(
                        booking.razorpay_order_id,
                        amount=int(booking.total_amount * 100)
                    )
                except Exception:
                    pass
            
            booking.save()
            return Response({'success': True, 'total_amount': float(booking.total_amount)})
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
def seed_database(request):
    import populate_movies
    import populate_food

    populate_movies.populate()
    populate_food.populate()

    return HttpResponse("Database seeded successfully!")

