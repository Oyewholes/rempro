from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)
from rest_framework.routers import DefaultRouter

from appone.views import (
    AdminViewSet,
    AuthViewSet,
    CompanyProfileViewSet,
    ContractViewSet,
    FreelancerProfileViewSet,
    JobApplicationViewSet,
    JobPostingViewSet,
    MessageViewSet,
    OTPViewSet,
    PaymentViewSet,
    PaystackWebhookView,
    TaskViewSet,
    WorkspaceViewSet,
)

router = DefaultRouter()
router.register(r"auth", AuthViewSet, basename="auth")
router.register(r"otp", OTPViewSet, basename="otp")
router.register(
    r"freelancers",
    FreelancerProfileViewSet,
    basename="freelancer",
)
router.register(r"companies", CompanyProfileViewSet, basename="company")
router.register(r"jobs", JobPostingViewSet, basename="job")
router.register(r"applications", JobApplicationViewSet, basename="application")
router.register(r"contracts", ContractViewSet, basename="contract")
router.register(r"workspaces", WorkspaceViewSet, basename="workspace")
router.register(r"tasks", TaskViewSet, basename="task")
router.register(r"messages", MessageViewSet, basename="message")
router.register(r"payments", PaymentViewSet, basename="payment")
router.register(r"admin-actions", AdminViewSet, basename="admin-action")

urlpatterns = [
    path("", include(router.urls)),
    path("schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "docs/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
    path(
        "redoc/",
        SpectacularRedocView.as_view(url_name="schema"),
        name="redoc",
    ),
    path(
        "webhooks/paystack/",
        PaystackWebhookView.as_view(),
        name="paystack-webhook",
    ),
]
