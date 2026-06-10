import datetime
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone
from api.models import City, Movie, Cinema, Screen, Seat, Show, ShowSeat, FoodItem, UserProfile, BookingFood, GroupBooking, GroupMemberSplit

class Command(BaseCommand):
    help = 'Seeds the database with cities, movies, cinemas, screens, seats, and shows.'

    def handle(self, *args, **kwargs):
        self.stdout.write('Seeding database...')
        
        # 1. Clear existing data
        GroupMemberSplit.objects.all().delete()
        GroupBooking.objects.all().delete()
        BookingFood.objects.all().delete()
        ShowSeat.objects.all().delete()
        Show.objects.all().delete()
        Seat.objects.all().delete()
        Screen.objects.all().delete()
        Cinema.objects.all().delete()
        Movie.objects.all().delete()
        City.objects.all().delete()
        FoodItem.objects.all().delete()
        UserProfile.objects.all().delete()
        
        # Delete all users to ensure a clean start matching requested credentials
        User.objects.all().delete()
        
        # Create Super Admin
        superadmin = User.objects.create(username='superadmin', is_superuser=True, is_staff=True)
        superadmin.set_password('adminpass')
        superadmin.save()
        profile_sa = superadmin.profile
        profile_sa.role = 'SUPERADMIN'
        profile_sa.save()
        self.stdout.write('Created superuser: superadmin / adminpass')
            
        # Create Theatre Admin
        theatreadmin = User.objects.create(username='theatreadmin', is_superuser=False, is_staff=True)
        theatreadmin.set_password('adminpass')
        theatreadmin.save()
        profile_ta = theatreadmin.profile
        profile_ta.role = 'THEATRE_ADMIN'
        profile_ta.save()
        self.stdout.write('Created theatreadmin: theatreadmin / adminpass')

        # Create Regular User
        dilmo = User.objects.create(username='dilmo', is_superuser=False, is_staff=False)
        dilmo.set_password('dilmopass')
        dilmo.save()
        profile_u = dilmo.profile
        profile_u.role = 'USER'
        profile_u.save()
        self.stdout.write('Created regular user: dilmo / dilmopass')

        # 2. Create Cities
        cities_data = ['Mumbai', 'Delhi', 'Bengaluru', 'Kochi', 'Chennai']
        cities = [City(name=name) for name in cities_data]
        City.objects.bulk_create(cities)
        cities_dict = {c.name: c for c in City.objects.all()}
        
        self.stdout.write(f'Created {len(cities_data)} cities.')

        # 3. Create Movies
        movies_data = [
            {
                'title': 'Parimala and Co',
                'description': 'A dark comedy centered around a chaotic family whose tangled relationships and unpredictable situations lead to emotionally charged and absurd moments, blending humor with drama.',
                'duration_minutes': 139,
                'language': 'Tamil',
                'genre': 'Comedy, Drama',
                'poster_url': 'https://images.unsplash.com/photo-1594909122845-11baa439b7bf?w=500',
                'release_date': datetime.date(2026, 6, 5),
            },
            {
                'title': 'Disclosure Day',
                'description': 'Directed by Steven Spielberg. A high-octane psychological thriller exploring secure timeline decoders and covert corporate anti-gravity research programs in the year 2026.',
                'duration_minutes': 125,
                'language': 'English',
                'genre': 'Thriller, Sci-Fi',
                'poster_url': 'https://images.unsplash.com/photo-1478720143022-90994772042a?w=500',
                'release_date': datetime.date(2026, 6, 12),
            },
            {
                'title': 'Badhu All Right Che',
                'description': 'A hilarious Gujarati family comedy involving a vacation trip to a hill station that turns into a chaotic sequence of mistaken identities and fun-filled reconciliations.',
                'duration_minutes': 130,
                'language': 'Gujarati',
                'genre': 'Comedy',
                'poster_url': 'https://images.unsplash.com/photo-1517604931442-7e0c8ed2963c?w=500',
                'release_date': datetime.date(2026, 6, 12),
            },
            {
                'title': 'Bharat Bhhagya Viddhaata',
                'description': 'A suspenseful national security drama focusing on complex decryption keys, hidden databases, and agents operating in the deep shadows.',
                'duration_minutes': 142,
                'language': 'Hindi',
                'genre': 'Thriller, Action',
                'poster_url': 'https://images.unsplash.com/photo-1536440136628-849c177e76a1?w=500',
                'release_date': datetime.date(2026, 6, 12),
            },
            {
                'title': 'Backrooms',
                'description': 'A terrifying horror film exploring the infinite liminal spaces of yellow hallways, fluorescent hums, and the creatures lurking inside them.',
                'duration_minutes': 110,
                'language': 'English',
                'genre': 'Horror, Sci-Fi',
                'poster_url': 'https://images.unsplash.com/photo-1509198397868-475647b2a1e5?w=500',
                'release_date': datetime.date(2026, 6, 12),
            },
            {
                'title': 'Michael',
                'description': 'The biography of the legend who changed music. Details the journeys, the recording sessions, and the global pop phenomenon of Michael Jackson.',
                'duration_minutes': 135,
                'language': 'English',
                'genre': 'Biography, Drama, Music',
                'poster_url': 'https://images.unsplash.com/photo-1511671782779-c97d3d27a1d4?w=500',
                'release_date': datetime.date(2026, 6, 5),
            },
            {
                'title': 'The Sheep Detectives',
                'description': 'An animated adventure following two fleece-bound sheep investigators attempting to track down the meadow grass thief.',
                'duration_minutes': 95,
                'language': 'English',
                'genre': 'Animation, Comedy, Adventure',
                'poster_url': 'https://images.unsplash.com/photo-1583511655857-d19b40a7a54e?w=500',
                'release_date': datetime.date(2026, 6, 5),
            },
            {
                'title': 'Mandalorian & Grogu',
                'description': 'The legendary space bounty hunter Mandalorian and his companion Grogu secure galactic sectors and establish star system locks.',
                'duration_minutes': 120,
                'language': 'English',
                'genre': 'Action, Adventure, Sci-Fi',
                'poster_url': 'https://images.unsplash.com/photo-1593085512500-5d55148d6f0d?w=500',
                'release_date': datetime.date(2026, 6, 5),
            },
        ]
        
        movies = [Movie(**data) for data in movies_data]
        for idx, m in enumerate(movies):
            m.is_approved = True
            if idx in [1, 2]: # Feature a couple of movies (Disclosure Day, Badhu All Right Che)
                m.is_featured = True
        Movie.objects.bulk_create(movies)
        movies_list = list(Movie.objects.all())
        
        self.stdout.write(f'Created {len(movies_list)} movies.')

        # 4. Create Cinemas (Theatres)
        cinemas_data = [
            {'name': 'PVR ICON Versova', 'address': 'Lallubhai Park Road, Andheri West', 'city': 'Mumbai'},
            {'name': 'INOX CR2 Nariman Point', 'address': 'Barrister Rajni Patel Marg, Nariman Point', 'city': 'Mumbai'},
            {'name': 'PVR Plaza Connaught Place', 'address': 'H-Block, Connaught Place', 'city': 'Delhi'},
            {'name': 'Delite Cinema', 'address': 'Asaf Ali Road, Daryaganj', 'city': 'Delhi'},
            {'name': 'PVR Forum Mall Koramangala', 'address': 'Hosur Road, Koramangala', 'city': 'Bengaluru'},
            {'name': 'URVASHI Theater', 'address': 'Siddaiah Road, Lalbagh', 'city': 'Bengaluru'},
            {'name': 'PVR Lulu Mall', 'address': 'Lulu Mall, Edapally', 'city': 'Kochi'},
            {'name': 'Shenoys Theater', 'address': 'Shenoys Junction, MG Road', 'city': 'Kochi'},
            {'name': 'PVR VR Chennai', 'address': 'Jawaharlal Nehru Road, Anna Nagar', 'city': 'Chennai'},
            {'name': 'Sathyam Cinemas', 'address': 'Thiru Vi Ka Road, Royapettah', 'city': 'Chennai'},
        ]
        
        cinemas = []
        for c_data in cinemas_data:
            city_obj = cities_dict[c_data['city']]
            cinemas.append(Cinema(
                name=c_data['name'], 
                address=c_data['address'], 
                city=city_obj,
                status='APPROVED',
                owner=theatreadmin,
                commission_rate=10.00
            ))
        Cinema.objects.bulk_create(cinemas)
        cinemas_list = list(Cinema.objects.all())
        
        self.stdout.write(f'Created {len(cinemas_list)} cinemas.')

        # 5. Create Screens and Seats
        screens = []
        for cinema in cinemas_list:
            screens.append(Screen(name='Audi 1 (IMAX)', cinema=cinema))
            screens.append(Screen(name='Audi 2 (Premium)', cinema=cinema))
        Screen.objects.bulk_create(screens)
        screens_list = list(Screen.objects.all())
        
        self.stdout.write(f'Created {len(screens_list)} screens.')

        # Generating seats for all screens
        seats_to_create = []
        for screen in screens_list:
            # Rows A, B, C: Classic (10 seats per row)
            for row in ['A', 'B', 'C']:
                for num in range(1, 11):
                    seats_to_create.append(Seat(screen=screen, row=row, number=num, seat_type='CLASSIC'))
            
            # Rows D, E, F: Premium (10 seats per row)
            for row in ['D', 'E', 'F']:
                for num in range(1, 11):
                    seats_to_create.append(Seat(screen=screen, row=row, number=num, seat_type='PREMIUM'))
            
            # Rows G, H: Recliner (8 seats per row)
            for row in ['G', 'H']:
                for num in range(1, 9):
                    seats_to_create.append(Seat(screen=screen, row=row, number=num, seat_type='RECLINER'))
                    
        Seat.objects.bulk_create(seats_to_create)
        self.stdout.write(f'Created {Seat.objects.count()} seats.')

        # 6. Create Shows (Today, Tomorrow, Day After Tomorrow)
        today = datetime.date.today()
        dates = [today, today + datetime.timedelta(days=1), today + datetime.timedelta(days=2)]
        
        show_times = [
            (datetime.time(10, 0), datetime.time(12, 30)),
            (datetime.time(13, 45), datetime.time(16, 30)),
            (datetime.time(17, 30), datetime.time(20, 15)),
            (datetime.time(21, 0), datetime.time(23, 45)),
        ]
        
        shows_to_create = []
        # Create a selection of shows to keep it fast but fully functional
        # We will loop through the cinemas and schedule a few movies
        import random
        random.seed(42) # Consistent seeding
        
        for date in dates:
            for cinema in cinemas_list:
                # Schedule shows on Audi 1 & Audi 2
                for idx, screen in enumerate(cinema.screens.all()):
                    # Pick a different movie for each screen/day
                    movie = random.choice(movies_list)
                    
                    # Schedule 2 showtimes per screen per day
                    for time_idx in [0, 2] if idx == 0 else [1, 3]:
                        start, end = show_times[time_idx]
                        
                        shows_to_create.append(Show(
                            movie=movie,
                            screen=screen,
                            cinema=cinema,
                            date=date,
                            start_time=start,
                            end_time=end,
                            classic_price=150.00,
                            premium_price=220.00,
                            recliner_price=400.00
                        ))
                        
        Show.objects.bulk_create(shows_to_create)
        all_shows = list(Show.objects.all())
        self.stdout.write(f'Scheduled {len(all_shows)} shows.')

        # 7. Generate ShowSeats for all Shows
        self.stdout.write('Generating ShowSeat availability mapping (this may take a few seconds)...')
        show_seats_to_create = []
        for show in all_shows:
            seats = Seat.objects.filter(screen=show.screen)
            for seat in seats:
                # Randomly make a few seats pre-booked for visual realism (say, 15% booking rate)
                status = 'AVAILABLE'
                if random.random() < 0.15:
                    status = 'BOOKED'
                    
                show_seats_to_create.append(ShowSeat(
                    show=show,
                    seat=seat,
                    status=status
                ))
                
        # Bulk create ShowSeats in chunks to prevent SQLite variable limits
        chunk_size = 999
        for i in range(0, len(show_seats_to_create), chunk_size):
            ShowSeat.objects.bulk_create(show_seats_to_create[i:i + chunk_size])
            
        self.stdout.write(f'Database seeded successfully! Created {ShowSeat.objects.count()} ShowSeat maps.')

        # 8. Create FoodItems for dynamic checkout pre-ordering
        self.stdout.write('Seeding FoodItem canteen database...')
        food_items_data = [
            {
                'name': 'Caramel Popcorn (L)',
                'description': 'Sweet and crunchy classic caramel glazed jumbo popcorn tub.',
                'price': 180.00,
                'image_url': 'https://images.unsplash.com/photo-1578849278619-e73505e9610f?w=300'
            },
            {
                'name': 'Cheese Popcorn (L)',
                'description': 'Salty jumbo popcorn tub loaded with melted cheddar cheese dust.',
                'price': 190.00,
                'image_url': 'https://images.unsplash.com/photo-1505686994434-e3cc5abf1330?w=300'
            },
            {
                'name': 'Loaded Nachos',
                'description': 'Crispy corn tortilla chips served with warm cheddar cheese sauce dip.',
                'price': 220.00,
                'image_url': 'https://images.unsplash.com/photo-1513456852971-30c0b8199d4d?w=300'
            },
            {
                'name': 'Pepsi Cyber-Can',
                'description': 'Chilled 330ml aerated classic cola can.',
                'price': 90.00,
                'image_url': 'https://images.unsplash.com/photo-1622483767028-3f66f32aef97?w=300'
            },
            {
                'name': 'Mineral Water Can',
                'description': 'Chilled premium packaged drinking water can.',
                'price': 50.00,
                'image_url': 'https://images.unsplash.com/photo-1608885898957-a599fb1b4656?w=300'
            }
        ]
        
        food_items = [FoodItem(**data) for data in food_items_data]
        FoodItem.objects.bulk_create(food_items)
        self.stdout.write(f'Seeded {FoodItem.objects.count()} Canteen Food Items.')

