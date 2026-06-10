from rest_framework import permissions
from .models import UserProfile

class IsTheatreAdmin(permissions.BasePermission):
    """Permission class to check if user is a Theatre Admin."""
    message = "You must be a Theatre Admin to access this resource."
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        try:
            profile = UserProfile.objects.get(user=request.user)
            return profile.role in ['THEATRE_ADMIN', 'SUPERADMIN']
        except UserProfile.DoesNotExist:
            return False

class IsSuperAdmin(permissions.BasePermission):
    """Permission class to check if user is a Super Admin."""
    message = "You must be a Super Admin to access this resource."
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        try:
            profile = UserProfile.objects.get(user=request.user)
            return profile.role == 'SUPERADMIN'
        except UserProfile.DoesNotExist:
            return False

class IsTheatreAdminOrReadOnly(permissions.BasePermission):
    """Permission class that allows Theatre Admin to edit, others can only read."""
    
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        
        if not request.user or not request.user.is_authenticated:
            return False
        
        try:
            profile = UserProfile.objects.get(user=request.user)
            return profile.role in ['THEATRE_ADMIN', 'SUPERADMIN']
        except UserProfile.DoesNotExist:
            return False
