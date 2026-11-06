
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import RegisterView, CategoryViewSet, OperationViewSet, BudgetViewSet, ReportView

router = DefaultRouter()
router.register("categories", CategoryViewSet, basename="category")
router.register("operations", OperationViewSet, basename="operation")
router.register("budgets", BudgetViewSet, basename="budget")

urlpatterns = [
    path("register/", RegisterView.as_view()),
    path("reports/", ReportView.as_view()),
    path("", include(router.urls)),
]
