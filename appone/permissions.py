from rest_framework import permissions


class IsFreelancer(permissions.BasePermission):
    """
    Permission check for freelancer users
    """

    def has_permission(self, request, view):
        return (
                request.user and
                request.user.is_authenticated and
                request.user.user_type == 'freelancer' and
                hasattr(request.user, 'freelancer_profile')
        )


class IsCompany(permissions.BasePermission):
    """
    Permission check for company users
    """

    def has_permission(self, request, view):
        return (
                request.user and
                request.user.is_authenticated and
                request.user.user_type == 'company' and
                hasattr(request.user, 'company_profile')
        )


class IsAdmin(permissions.BasePermission):
    """
    Permission check for admin users
    """

    def has_permission(self, request, view):
        return (
                request.user and
                request.user.is_authenticated and
                request.user.user_type == 'admin' and
                request.user.is_staff
        )


class IsFreelancerOrCompany(permissions.BasePermission):
    """
    Permission check for either freelancer or company users
    """

    def has_permission(self, request, view):
        return (
                request.user and
                request.user.is_authenticated and
                request.user.user_type in ['freelancer', 'company']
        )


class IsVerifiedFreelancer(permissions.BasePermission):
    """
    Permission check for verified freelancer users
    """

    def has_permission(self, request, view):
        return (
                request.user and
                request.user.is_authenticated and
                request.user.user_type == 'freelancer' and
                hasattr(request.user, 'freelancer_profile') and
                request.user.freelancer_profile.verification_status == 'verified'
        )


class IsVerifiedCompany(permissions.BasePermission):
    """
    Permission check for verified company users
    """

    def has_permission(self, request, view):
        return (
                request.user and
                request.user.is_authenticated and
                request.user.user_type == 'company' and
                hasattr(request.user, 'company_profile') and
                request.user.company_profile.verification_status == 'verified'
        )


class IsOwnerOrReadOnly(permissions.BasePermission):
    """
    Object-level permission to only allow owners of an object to edit it.
    """

    def has_object_permission(self, request, view, obj):
        # Read permissions are allowed to any request
        if request.method in permissions.SAFE_METHODS:
            return True

        # Write permissions are only allowed to the owner
        if hasattr(obj, 'user'):
            return obj.user == request.user
        elif hasattr(obj, 'freelancer'):
            return hasattr(request.user, 'freelancer_profile') and obj.freelancer == request.user.freelancer_profile
        elif hasattr(obj, 'company'):
            return hasattr(request.user, 'company_profile') and obj.company == request.user.company_profile

        return False