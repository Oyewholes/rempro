from rest_framework.routers import DefaultRouter
from django.urls import path, include
from appone.views import (
    AuthViewSet, OTPViewSet, FreelancerProfileViewSet,
    CompanyProfileViewSet, JobPostingViewSet, JobApplicationViewSet,
    ContractViewSet, PaymentViewSet, WorkspaceViewSet, TaskViewSet,
    MessageViewSet, AdminViewSet
)

router = DefaultRouter()


router.register('auth', AuthViewSet, basename='auth')
router.register('otp', OTPViewSet, basename='otp')

# Profile Management
router.register('freelancers', FreelancerProfileViewSet, basename='freelancer')
router.register('companies', CompanyProfileViewSet, basename='company')

# Core Business Logic
router.register('jobs', JobPostingViewSet, basename='job')
router.register('applications', JobApplicationViewSet, basename='application')
router.register('contracts', ContractViewSet, basename='contract')
router.register('payments', PaymentViewSet, basename='payment')

# Collaboration & Communication
router.register('workspaces', WorkspaceViewSet, basename='workspace')
router.register('tasks', TaskViewSet, basename='task')
router.register('messages', MessageViewSet, basename='message')

# Admin Functions (Usually highly restricted)
router.register('admin', AdminViewSet, basename='admin')


# The API URLs are now determined automatically by the router.
# The `router.urls` automatically includes the API root views.
urlpatterns = [
    path('', include(router.urls)),
]