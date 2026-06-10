import datetime
from django.utils import timezone
from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from api.models import City, Movie, Cinema, Screen, Seat, Show, ShowSeat, Booking

class BookMyScreenTests(APITestCase):

    def setUp(self):
        # Create user
        self.user1 = User.objects.create_user(username='user1', password='pwd123password')
        self.user2 = User.objects.create_user(username='user2', password='pwd123password')
        
        # Create city
        self.city = City.objects.create(name='Mumbai')
        
        # Create movie
        self.movie = Movie.objects.create(
            title='Spider-Man',
            description='Action movie',
            duration_minutes=120,
            language='English',
            genre='Action',
            release_date=datetime.date.today()
        )
        
        # Create cinema & screen
        self.cinema = Cinema.objects.create(name='PVR Versova', address='Andheri', city=self.city)
        self.screen = Screen.objects.create(name='Audi 1', cinema=self.cinema)
        
        # Create seats
        self.seat1 = Seat.objects.create(screen=self.screen, row='A', number=1, seat_type='CLASSIC')
        self.seat2 = Seat.objects.create(screen=self.screen, row='A', number=2, seat_type='CLASSIC')
        
        # Create show
        self.show = Show.objects.create(
            movie=self.movie,
            screen=self.screen,
            cinema=self.cinema,
            date=datetime.date.today(),
            start_time=datetime.time(18, 0),
            end_time=datetime.time(20, 0),
            classic_price=100.00,
            premium_price=200.00,
            recliner_price=300.00
        )
        
        # Map ShowSeats
        self.show_seat1 = ShowSeat.objects.create(show=self.show, seat=self.seat1, status='AVAILABLE')
        self.show_seat2 = ShowSeat.objects.create(show=self.show, seat=self.seat2, status='AVAILABLE')

    def test_user_registration_and_login(self):
        # Test Register
        register_url = reverse('register')
        data = {
            'username': 'newuser',
            'email': 'new@example.com',
            'password': 'newpassword123'
        }
        response = self.client.post(register_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('token', response.data)
        
        # Test Login
        login_url = reverse('login')
        login_data = {
            'username': 'newuser',
            'password': 'newpassword123'
        }
        response = self.client.post(login_url, login_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('token', response.data)

    def test_lock_seats_and_prevent_double_lock(self):
        # Authenticate user 1
        self.client.force_authenticate(user=self.user1)
        
        # Lock seats
        lock_url = reverse('lock_seats', args=[self.show.id])
        data = {'seat_ids': [self.seat1.id, self.seat2.id]}
        response = self.client.post(lock_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('booking_id', response.data)
        
        # Verify status updated to LOCKED in DB
        self.show_seat1.refresh_from_db()
        self.assertEqual(self.show_seat1.status, 'LOCKED')
        
        # Authenticate user 2
        self.client.force_authenticate(user=self.user2)
        
        # Try locking again - should fail
        response = self.client.post(lock_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('already booked or locked', response.data['error'])

    def test_seat_lock_expiration(self):
        # Manually lock a seat and set back locked_at by 6 minutes
        booking = Booking.objects.create(
            user=self.user1,
            show=self.show,
            booking_status='PENDING',
            total_amount=100.00
        )
        
        self.show_seat1.status = 'LOCKED'
        self.show_seat1.locked_at = timezone.now() - timezone.timedelta(minutes=6)
        self.show_seat1.booking = booking
        self.show_seat1.save()
        
        # Authenticate user 2
        self.client.force_authenticate(user=self.user2)
        
        # Lock URL - trying to lock seat 1.
        # It should succeed because seat 1's lock is expired (created 6 minutes ago).
        lock_url = reverse('lock_seats', args=[self.show.id])
        data = {'seat_ids': [self.seat1.id]}
        response = self.client.post(lock_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.show_seat1.refresh_from_db()
        # Seat 1 is now locked by the new booking
        self.assertEqual(self.show_seat1.booking.id, response.data['booking_id'])
        self.assertEqual(self.show_seat1.status, 'LOCKED')

    def test_payment_verification_flow(self):
        # Authenticate user 1
        self.client.force_authenticate(user=self.user1)
        
        # Lock seats
        lock_url = reverse('lock_seats', args=[self.show.id])
        lock_response = self.client.post(lock_url, {'seat_ids': [self.seat1.id]}, format='json')
        booking_id = lock_response.data['booking_id']
        
        # Verify Payment (Demo Bypass path)
        verify_url = reverse('verify_payment')
        data = {
            'booking_id': booking_id,
            'demo_success': True
        }
        
        # Under TestCase, transactions commit at the end, but DRF view executes lambdas in transaction.on_commit
        # We can verify that it successfully processes.
        response = self.client.post(verify_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'SUCCESS')
        
        # Check booking status is CONFIRMED and seat is BOOKED
        booking = Booking.objects.get(pk=booking_id)
        self.assertEqual(booking.booking_status, 'CONFIRMED')
        
        self.show_seat1.refresh_from_db()
        self.assertEqual(self.show_seat1.status, 'BOOKED')

    def test_email_dispatch_flow(self):
        from django.core import mail
        from api.tasks import send_booking_email_sync
        
        # Create a confirmed booking
        booking = Booking.objects.create(
            user=self.user1,
            show=self.show,
            booking_status='CONFIRMED',
            total_amount=150.00
        )
        self.show_seat1.booking = booking
        self.show_seat1.status = 'BOOKED'
        self.show_seat1.save()
        
        # Clear outbox
        mail.outbox = []
        
        # Call email dispatcher synchronously
        success = send_booking_email_sync(booking.id)
        self.assertTrue(success)
        
        # Verify one email was sent
        self.assertEqual(len(mail.outbox), 1)
        sent_mail = mail.outbox[0]
        self.assertIn("Ticket Confirmed!", sent_mail.subject)
        self.assertEqual(sent_mail.to, [self.user1.email or "customer@example.com"])
        self.assertIn("Spider-Man", sent_mail.body)

    def test_advanced_experience_features(self):
        from api.models import FoodItem, UserProfile
        
        # 1. Seed Food Items
        popcorn = FoodItem.objects.create(name='Popcorn', price=100.00)
        soda = FoodItem.objects.create(name='Soda', price=50.00)
        
        self.client.force_authenticate(user=self.user1)
        
        # 2. Test Lock Seats with Food and Split Payment
        lock_url = reverse('lock_seats', args=[self.show.id])
        data = {
            'seat_ids': [self.seat1.id],
            'food_items': [{'id': popcorn.id, 'quantity': 2}, {'id': soda.id, 'quantity': 1}],
            'split_emails': ['friend1@example.com', 'friend2@example.com']
        }
        
        response = self.client.post(lock_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        booking_id = response.data['booking_id']
        
        # Total amount: Ticket (100) + Popcorn x2 (200) + Soda x1 (50) = 350 INR
        # Friends split: total parties = 3 (user + 2 friends). Amount per person = 350 / 3 = 116.67
        self.assertAlmostEqual(response.data['total_amount'], 350.00)
        self.assertAlmostEqual(response.data['amount_per_person'], 116.67, places=2)
        
        # 3. Verify Payment
        verify_url = reverse('verify_payment')
        verify_data = {
            'booking_id': booking_id,
            'demo_success': True
        }
        
        verify_response = self.client.post(verify_url, verify_data, format='json')
        self.assertEqual(verify_response.status_code, status.HTTP_200_OK)
        
        # 4. Verify Gamification: points awarded & badges unlocked
        # Total booking amount = 350. Points = 10% = 35 points
        profile = UserProfile.objects.get(user=self.user1)
        self.assertEqual(profile.reward_points, 35)
        # Should have Cinema Pioneer, Snack Commander, and Squad Leader badges!
        self.assertIn("CINEMA_PIONEER", profile.badges)
        self.assertIn("SNACK_COMMANDER", profile.badges)
        self.assertIn("SQUAD_LEADER", profile.badges)
        
        # 5. Test Profile details API
        profile_url = reverse('profile_details')
        profile_response = self.client.get(profile_url)
        self.assertEqual(profile_response.status_code, status.HTTP_200_OK)
        self.assertEqual(profile_response.data['profile']['reward_points'], 35)


