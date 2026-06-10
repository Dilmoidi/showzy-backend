import os
import django
import datetime

# Setup django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bookmyscreen.settings')
django.setup()

from api.models import Movie, Cinema, Screen, Seat, Show, ShowSeat

def populate():
    print("Starting movie population...")
    
    # 1. Define movies list with high-quality images and details
    movies_data = [
        {
            "title": "Dune: Part Two",
            "description": "Paul Atreides unites with Chani and the Fremen while seeking revenge against the conspirators who destroyed his family.",
            "duration_minutes": 166,
            "language": "English",
            "genre": "Sci-Fi, Action, Adventure",
            "poster_url": "https://images.unsplash.com/photo-1534447677768-be436bb09401?w=500&auto=format&fit=crop&q=60", # Space/Desert vibe
            "release_date": "2024-03-01",
            "is_active": True,
            "is_approved": True,
            "is_featured": True
        },
        {
            "title": "Oppenheimer",
            "description": "The story of American scientist J. Robert Oppenheimer and his role in the development of the atomic bomb.",
            "duration_minutes": 180,
            "language": "English",
            "genre": "Drama, Biography, History",
            "poster_url": "https://images.unsplash.com/photo-1461360370896-922624d12aa1?w=500&auto=format&fit=crop&q=60", # Vintage science vibe
            "release_date": "2023-07-21",
            "is_active": True,
            "is_approved": True,
            "is_featured": True
        },
        {
            "title": "Deadpool & Wolverine",
            "description": "Wolverine is recovering from his injuries when he crosses paths with the loudmouth, Deadpool. They team up to defeat a common enemy.",
            "duration_minutes": 128,
            "language": "English",
            "genre": "Action, Comedy, Sci-Fi",
            "poster_url": "https://images.unsplash.com/photo-1608889175123-8ee362201f81?w=500&auto=format&fit=crop&q=60", # Comic/Action vibe
            "release_date": "2024-07-26",
            "is_active": True,
            "is_approved": True,
            "is_featured": True
        },
        {
            "title": "Inside Out 2",
            "description": "Follow Riley, in her teenage years, encountering new emotions.",
            "duration_minutes": 96,
            "language": "English",
            "genre": "Animation, Family, Comedy",
            "poster_url": "https://images.unsplash.com/photo-1509198397868-475647b2a1e5?w=500&auto=format&fit=crop&q=60", # Colorful/Teen vibe
            "release_date": "2024-06-14",
            "is_active": True,
            "is_approved": True,
            "is_featured": False
        },
        {
            "title": "Kalki 2898 AD",
            "description": "A modern avatar of Vishnu, a Hindu god, who is believed to have descended to earth to protect the world from evil forces.",
            "duration_minutes": 181,
            "language": "Telugu",
            "genre": "Sci-Fi, Action, Fantasy",
            "poster_url": "https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?w=500&auto=format&fit=crop&q=60", # Mythological sci-fi vibe
            "release_date": "2024-06-27",
            "is_active": True,
            "is_approved": True,
            "is_featured": True
        },
        {
            "title": "Jawan",
            "description": "A high-octane action thriller which outlines the emotional journey of a man who is set to rectify the wrongs in the society.",
            "duration_minutes": 168,
            "language": "Hindi",
            "genre": "Action, Thriller",
            "poster_url": "https://images.unsplash.com/photo-1536440136628-849c177e76a1?w=500&auto=format&fit=crop&q=60", # Cinema reel vibe
            "release_date": "2023-09-07",
            "is_active": True,
            "is_approved": True,
            "is_featured": False
        }
    ]

    created_movies = []
    for m_info in movies_data:
        movie, created = Movie.objects.get_or_create(
            title=m_info["title"],
            defaults={
                "description": m_info["description"],
                "duration_minutes": m_info["duration_minutes"],
                "language": m_info["language"],
                "genre": m_info["genre"],
                "poster_url": m_info["poster_url"],
                "release_date": m_info["release_date"],
                "is_active": m_info["is_active"],
                "is_approved": m_info["is_approved"],
                "is_featured": m_info["is_featured"]
            }
        )
        if created:
            print(f"Created movie: {movie.title}")
        else:
            # Update poster URL and featured status just to ensure high quality and featured slides
            movie.poster_url = m_info["poster_url"]
            movie.is_featured = m_info["is_featured"]
            movie.is_approved = True
            movie.is_active = True
            movie.save()
            print(f"Updated movie poster/fields: {movie.title}")
        created_movies.append(movie)

    # 2. Get all Cinemas and Screens
    cinemas = Cinema.objects.all()
    screens = Screen.objects.all()
    
    print(f"Found {cinemas.count()} cinemas and {screens.count()} screens across all cities.")

    # 3. Schedule shows for the next 3 days
    today = datetime.date.today()
    dates = [today, today + datetime.timedelta(days=1), today + datetime.timedelta(days=2)]
    
    show_timings = [
        {"start": "10:30:00", "end": "13:30:00"},
        {"start": "14:15:00", "end": "17:15:00"},
        {"start": "18:00:00", "end": "21:00:00"},
        {"start": "21:45:00", "end": "00:45:00"}
    ]

    show_count = 0
    show_seat_count = 0

    for idx, screen in enumerate(screens):
        # Pick 2 movies per screen to rotate shows
        movie_1 = created_movies[idx % len(created_movies)]
        movie_2 = created_movies[(idx + 1) % len(created_movies)]
        
        seats = list(Seat.objects.filter(screen=screen))
        if not seats:
            print(f"Generating default seats for screen: {screen}")
            # generate default layout (A to E, cols 8)
            seats_to_create = []
            for row in ['A', 'B', 'C', 'D', 'E']:
                for num in range(1, 9):
                    seat_type = 'CLASSIC'
                    if row in ['A', 'B']:
                        seat_type = 'PREMIUM'
                    elif row == 'E':
                        seat_type = 'RECLINER'
                    seats_to_create.append(Seat(screen=screen, row=row, number=num, seat_type=seat_type))
            Seat.objects.bulk_create(seats_to_create)
            seats = list(Seat.objects.filter(screen=screen))

        for date in dates:
            for t_idx, timing in enumerate(show_timings):
                # Alternate movies
                selected_movie = movie_1 if t_idx % 2 == 0 else movie_2
                
                # Check if show already exists
                show, created = Show.objects.get_or_create(
                    movie=selected_movie,
                    screen=screen,
                    cinema=screen.cinema,
                    date=date,
                    start_time=timing["start"],
                    defaults={
                        "end_time": timing["end"],
                        "classic_price": 180.00,
                        "premium_price": 280.00,
                        "recliner_price": 500.00
                    }
                )
                
                if created:
                    show_count += 1
                    # Generate Show Seats
                    show_seats = [
                        ShowSeat(show=show, seat=seat, status='AVAILABLE')
                        for seat in seats
                    ]
                    ShowSeat.objects.bulk_create(show_seats)
                    show_seat_count += len(show_seats)

    print(f"Successfully scheduled {show_count} new shows and generated {show_seat_count} ShowSeat mappings!")

if __name__ == '__main__':
    populate()
