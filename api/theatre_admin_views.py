import datetime
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework import status, permissions, authentication
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework_simplejwt.authentication import JWTAuthentication

from .models import Cinema, Booking, Show, ScanLog
from .serializers import BookingSerializer

def check_role(user, allowed_roles):
    if user.is_superuser:
        return True
    try:
        return user.profile.role in allowed_roles
    except Exception:
        return False

# ----------------- THEATRE ADMIN DASHBOARD VIEWS -----------------

@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
@authentication_classes([JWTAuthentication])
def theatre_admin_dashboard(request):
    if not check_role(request.user, ['THEATRE_ADMIN', 'SUPERADMIN']):
        return Response({'error': 'Access denied: Theatre Admin role required.'}, status=status.HTTP_403_FORBIDDEN)
        
    today = timezone.now().date()
    start_of_day = timezone.make_aware(timezone.datetime.combine(today, timezone.datetime.min.time()))
    end_of_day = timezone.make_aware(timezone.datetime.combine(today, timezone.datetime.max.time()))
    
    admin_cinemas = Cinema.objects.filter(owner=request.user)
    if not admin_cinemas.exists() and check_role(request.user, ['SUPERADMIN']):
        admin_cinemas = Cinema.objects.all()

    todays_shows = Show.objects.filter(cinema__in=admin_cinemas, date=today)
    todays_bookings = Booking.objects.filter(show__in=todays_shows, booking_status='CONFIRMED')
    
    todays_shows_count = todays_shows.count()
    todays_bookings_count = todays_bookings.count()
    tickets_scanned_today = todays_bookings.filter(is_checked_in=True).count()
    pending_entries = todays_bookings_count - tickets_scanned_today
    revenue_today = sum(b.total_amount for b in todays_bookings)
    
    # Hourly charts mock for today (group by hour of booking creation)
    hourly_bookings = []
    hourly_checkins = []
    for i in range(12, 24):
        hourly_bookings.append({'hour': f"{i}:00", 'bookings': 0})
        hourly_checkins.append({'hour': f"{i}:00", 'checkins': 0})

    for b in todays_bookings:
        hour = b.created_at.hour
        hour_str = f"{hour}:00"
        for h in hourly_bookings:
            if h['hour'] == hour_str:
                h['bookings'] += 1
        
        if b.is_checked_in and b.checked_in_at:
            cin_hour = b.checked_in_at.hour
            cin_hour_str = f"{cin_hour}:00"
            for h in hourly_checkins:
                if h['hour'] == cin_hour_str:
                    h['checkins'] += 1
                    
    return Response({
        'todays_shows': todays_shows_count,
        'todays_bookings': todays_bookings_count,
        'tickets_scanned': tickets_scanned_today,
        'pending_entries': pending_entries,
        'revenue_today': float(revenue_today),
        'hourly_bookings': hourly_bookings,
        'hourly_checkins': hourly_checkins
    })

@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
@authentication_classes([JWTAuthentication])
def theatre_admin_revenue(request):
    if not check_role(request.user, ['THEATRE_ADMIN', 'SUPERADMIN']):
        return Response({'error': 'Access denied: Theatre Admin role required.'}, status=status.HTTP_403_FORBIDDEN)
        
    today = timezone.now().date()
    start_of_today = timezone.make_aware(timezone.datetime.combine(today, timezone.datetime.min.time()))
    start_of_week = start_of_today - timezone.timedelta(days=today.weekday())
    start_of_month = timezone.make_aware(timezone.datetime.combine(today.replace(day=1), timezone.datetime.min.time()))
    
    admin_cinemas = Cinema.objects.filter(owner=request.user)
    if not admin_cinemas.exists() and check_role(request.user, ['SUPERADMIN']):
        admin_cinemas = Cinema.objects.all()

    bookings = Booking.objects.filter(show__cinema__in=admin_cinemas, booking_status='CONFIRMED')
    
    rev_today = sum(b.total_amount for b in bookings.filter(created_at__gte=start_of_today))
    rev_week = sum(b.total_amount for b in bookings.filter(created_at__gte=start_of_week))
    rev_month = sum(b.total_amount for b in bookings.filter(created_at__gte=start_of_month))
    
    return Response({
        'revenue_today': float(rev_today),
        'revenue_week': float(rev_week),
        'revenue_month': float(rev_month)
    })

@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
@authentication_classes([JWTAuthentication])
def theatre_admin_bookings(request):
    if not check_role(request.user, ['THEATRE_ADMIN', 'SUPERADMIN']):
        return Response({'error': 'Access denied.'}, status=status.HTTP_403_FORBIDDEN)
        
    admin_cinemas = Cinema.objects.filter(owner=request.user)
    if not admin_cinemas.exists() and check_role(request.user, ['SUPERADMIN']):
        admin_cinemas = Cinema.objects.all()

    bookings = Booking.objects.filter(show__cinema__in=admin_cinemas).order_by('-created_at')
    
    search = request.query_params.get('search', '')
    if search:
        bookings = bookings.filter(
            Q(booking_id__icontains=search) | 
            Q(user__username__icontains=search) | 
            Q(show__movie__title__icontains=search)
        )
        
    serializer = BookingSerializer(bookings[:100], many=True)
    return Response(serializer.data)

@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
@authentication_classes([JWTAuthentication])
def theatre_admin_scan_logs(request):
    if not check_role(request.user, ['THEATRE_ADMIN', 'SUPERADMIN']):
        return Response({'error': 'Access denied.'}, status=status.HTTP_403_FORBIDDEN)
        
    admin_cinemas = Cinema.objects.filter(owner=request.user)
    if not admin_cinemas.exists() and check_role(request.user, ['SUPERADMIN']):
        admin_cinemas = Cinema.objects.all()

    logs = ScanLog.objects.filter(booking__show__cinema__in=admin_cinemas).order_by('-scan_time')
    
    logs_data = []
    for log in logs[:100]:
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

@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
@authentication_classes([JWTAuthentication])
def theatre_admin_verify_ticket(request):
    if not check_role(request.user, ['THEATRE_ADMIN', 'SUPERADMIN']):
        return Response({'error': 'Access denied: Theatre Admin role required.'}, status=status.HTTP_403_FORBIDDEN)
        
    booking_id = request.data.get('booking_id')
    token = request.data.get('token', '')
    
    device = request.META.get('HTTP_USER_AGENT', 'Unknown Device')
    ip_address = request.META.get('REMOTE_ADDR', '0.0.0.0')
    
    if not booking_id:
        return Response({'success': False, 'message': 'Invalid QR Data: No booking ID provided'}, status=status.HTTP_400_BAD_REQUEST)
        
    booking_id = str(booking_id).strip()
    if booking_id.upper().startswith('#SZ-'):
        booking_id = booking_id[4:]
    elif booking_id.upper().startswith('SZ-'):
        booking_id = booking_id[3:]
        
    try:
        with transaction.atomic():
            # Match UUID booking_id or fall back to integer primary key lookup
            if '-' in booking_id or len(booking_id) == 36:
                booking = Booking.objects.select_for_update().get(booking_id=booking_id)
            else:
                booking = Booking.objects.select_for_update().get(id=booking_id)
            
            # Check Theatre Ownership (bypass for SUPERADMIN and user 'admin')
            is_owner = (booking.show.cinema.owner == request.user)
            if not is_owner and not (check_role(request.user, ['SUPERADMIN']) or request.user.username == 'admin'):
                ScanLog.objects.create(booking=booking, scanned_by=request.user, device=device, ip_address=ip_address, status='INVALID', remarks='Wrong Theatre')
                return Response({'success': False, 'message': 'Wrong Theatre: You are not authorized to validate this ticket.'}, status=status.HTTP_400_BAD_REQUEST)
                
            # Verify Token (skip if token not provided — manual admin entry)
            if token and booking.qr_token and booking.qr_token != token:
                ScanLog.objects.create(booking=booking, scanned_by=request.user, device=device, ip_address=ip_address, status='INVALID', remarks='Token mismatch')
                return Response({'success': False, 'message': 'Invalid Token'}, status=status.HTTP_400_BAD_REQUEST)
                
            # Verify Status
            if booking.booking_status != 'CONFIRMED':
                ScanLog.objects.create(booking=booking, scanned_by=request.user, device=device, ip_address=ip_address, status='INVALID', remarks=f'Status: {booking.booking_status}')
                return Response({'success': False, 'message': f'Ticket {booking.booking_status}'}, status=status.HTTP_400_BAD_REQUEST)
                
            # Verify Not Checked In
            if booking.is_checked_in:
                ScanLog.objects.create(booking=booking, scanned_by=request.user, device=device, ip_address=ip_address, status='ALREADY_USED', remarks='Duplicate scan check')
                checked_in_time_str = booking.checked_in_at.strftime('%Y-%m-%d %H:%M:%S') if booking.checked_in_at else "Unknown"
                return Response({'success': False, 'message': 'Ticket Already Used', 'previous_scan_time': checked_in_time_str}, status=status.HTTP_400_BAD_REQUEST)
                
            # Grant entry
            booking.is_checked_in = True
            booking.checked_in_at = timezone.now()
            booking.save()
            
            ScanLog.objects.create(booking=booking, scanned_by=request.user, device=device, ip_address=ip_address, status='SUCCESS', remarks='Successful entrance check-in')
            
        seats_str = ", ".join(f"{ss.seat.row}{ss.seat.number}" for ss in booking.show_seats.all())
        return Response({
            'success': True,
            'message': 'Entry Allowed',
            'booking_details': {
                'id': booking.id,
                'booking_id': str(booking.booking_id),
                'customer': booking.user.username,
                'movie': booking.show.movie.title,
                'screen': booking.show.screen.name,
                'seats': seats_str,
                'showtime': f"{booking.show.date} {booking.show.start_time}",
                'checked_in_at': booking.checked_in_at.strftime('%Y-%m-%d %H:%M:%S')
            }
        })
    except Booking.DoesNotExist:
        ScanLog.objects.create(booking=None, scanned_by=request.user, device=device, ip_address=ip_address, status='INVALID', remarks='Booking not found')
        return Response({'success': False, 'message': 'Booking not found'}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
@authentication_classes([JWTAuthentication])
def theatre_admin_shows(request):
    if not check_role(request.user, ['THEATRE_ADMIN', 'SUPERADMIN']):
        return Response({'error': 'Access denied: Theatre Admin role required.'}, status=status.HTTP_403_FORBIDDEN)
    
    admin_cinemas = Cinema.objects.filter(owner=request.user)
    if not admin_cinemas.exists() and check_role(request.user, ['SUPERADMIN']):
        admin_cinemas = Cinema.objects.all()
        
    shows = Show.objects.filter(cinema__in=admin_cinemas).order_by('-date', '-start_time')
    from .serializers import ShowSerializer
    return Response(ShowSerializer(shows, many=True).data)

@api_view(['DELETE'])
@permission_classes([permissions.IsAuthenticated])
@authentication_classes([JWTAuthentication])
def theatre_admin_delete_show(request, show_id):
    if not check_role(request.user, ['THEATRE_ADMIN', 'SUPERADMIN']):
        return Response({'error': 'Access denied: Theatre Admin role required.'}, status=status.HTTP_403_FORBIDDEN)
    
    try:
        if request.user.is_superuser or request.user.profile.role == 'SUPERADMIN':
            show = Show.objects.get(pk=show_id)
        else:
            admin_cinemas = Cinema.objects.filter(owner=request.user)
            show = Show.objects.get(pk=show_id, cinema__in=admin_cinemas)
            
        show.delete()
        return Response({'message': 'Show deleted successfully'}, status=status.HTTP_200_OK)
    except Show.DoesNotExist:
        return Response({'error': 'Show not found or access denied'}, status=status.HTTP_404_NOT_FOUND)
