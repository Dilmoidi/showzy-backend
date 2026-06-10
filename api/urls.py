from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from . import views

urlpatterns = [
    # Authentication
    path('auth/register/', views.register_user, name='register'),
    path('auth/login/', views.login_user, name='login'),
    path('auth/profile/', views.get_user_profile, name='profile'),
    
    # JWT Authentication
    path('auth/jwt/login/', views.jwt_login, name='jwt_login'),
    path('auth/jwt/refresh/', TokenRefreshView.as_view(), name='jwt_refresh'),
    path('auth/jwt/theatre-admin-login/', views.theatre_admin_login, name='theatre_admin_login'),
    path('auth/jwt/profile/', views.get_jwt_profile, name='jwt_profile'),
    
    # Catalogue
    path('cities/', views.list_cities, name='list_cities'),
    path('movies/', views.list_movies, name='list_movies'),
    path('movies/<int:pk>/', views.movie_detail, name='movie_detail'),
    path('movies/<int:movie_id>/shows/', views.list_movie_shows, name='movie_shows'),
    
    # Seats and bookings
    path('shows/<int:show_id>/seats/', views.get_show_seats, name='show_seats'),
    path('shows/<int:show_id>/lock-seats/', views.lock_seats, name='lock_seats'),
    path('shows/<int:show_id>/group/create/', views.create_group_session, name='create_group_session'),
    path('shows/group/<uuid:token>/seats/', views.get_group_session_seats, name='get_group_session_seats'),
    path('shows/group/<uuid:token>/lock/', views.lock_group_seats, name='lock_group_seats'),
    path('shows/group/<uuid:token>/unlock/', views.unlock_group_seats, name='unlock_group_seats'),
    path('shows/group/<uuid:token>/checkout/', views.checkout_group_seats, name='checkout_group_seats'),
    path('bookings/verify/', views.verify_payment, name='verify_payment'),
    path('bookings/<int:booking_id>/cancel/', views.cancel_booking, name='cancel_booking'),
    path('bookings/<int:booking_id>/add-food/', views.add_food_to_booking, name='add_food_to_booking'),
    path('bookings/user/', views.get_user_bookings, name='user_bookings'),
    
    # Admin
    path('admin/movies/create/', views.create_movie, name='create_movie'),
    path('admin/shows/schedule/', views.schedule_show, name='schedule_show'),
    path('admin/stats/', views.admin_stats, name='admin_stats'),
    path('admin/cinemas/', views.admin_list_cinemas, name='admin_cinemas'),
    path('admin/cinemas/create/', views.admin_create_cinema, name='admin_create_cinema'),
    path('admin/cinemas/approve/', views.admin_approve_cinema, name='admin_approve_cinema'),
    path('admin/cinemas/edit/', views.admin_edit_cinema, name='admin_edit_cinema'),
    path('admin/cinemas/delete/', views.admin_delete_cinema, name='admin_delete_cinema'),
    path('admin/movies/approve/', views.admin_approve_movie, name='admin_approve_movie'),
    path('admin/screens/', views.admin_list_screens, name='admin_screens'),
    path('admin/screens/create/', views.admin_create_screen, name='admin_create_screen'),
    path('admin/users/', views.admin_manage_users, name='admin_manage_users'),
    path('admin/coupons/', views.admin_coupons, name='admin_coupons'),
    path('admin/broadcast/', views.admin_broadcast, name='admin_broadcast'),
    
    # Cinema Management
    path('cinema/bookings/', views.cinema_bookings, name='cinema_bookings'),
    path('cinema/offers/', views.cinema_offers, name='cinema_offers'),
    path('cinema/validate-ticket/', views.cinema_validate_ticket, name='cinema_validate_ticket'),
    path('cinema/notify-customers/', views.cinema_show_notifications, name='cinema_show_notifications'),
    
    # Advanced Features
    path('recommendations/', views.get_ai_recommendations, name='ai_recommendations'),
    path('food/', views.list_food_items, name='food_list'),
    path('profile/', views.get_profile_details, name='profile_details'),
    path('bookings/split-pay/', views.simulate_split_payment, name='split_payment_simulate'),
    
    # QR Ticket System
    path('theatre-admin/dashboard/', views.theatre_admin_dashboard, name='theatre_admin_dashboard'),
    path('theatre-admin/revenue/', views.theatre_admin_revenue, name='theatre_admin_revenue'),
    path('theatre-admin/bookings/', views.theatre_admin_bookings, name='theatre_admin_bookings'),
    path('theatre-admin/verify-ticket/', views.theatre_admin_verify_ticket, name='theatre_admin_verify_ticket'),
    path('theatre-admin/scan-logs/', views.theatre_admin_scan_logs, name='theatre_admin_scan_logs'),
    path('theatre-admin/shows/', views.theatre_admin_shows, name='theatre_admin_shows'),
    path('theatre-admin/shows/<int:show_id>/delete/', views.theatre_admin_delete_show, name='theatre_admin_delete_show'),
    
    path('verify-ticket/', views.verify_ticket, name='verify_ticket'),
    path('bookings/', views.list_bookings_api, name='list_bookings_api'),
    path('booking/<str:booking_id>/', views.booking_detail_api, name='booking_detail_api'),
    path('ticket/<str:booking_id>/', views.ticket_detail_api, name='ticket_detail_api'),
    path('scan-logs/', views.list_scan_logs_api, name='list_scan_logs_api'),
    path('download-ticket/', views.download_ticket_pdf, name='download_ticket_pdf_query'),
    path('download-ticket/<str:booking_id>/', views.download_ticket_pdf, name='download_ticket_pdf'),
    path('book/', views.mock_book_seats, name='mock_book_seats'),
   ]
