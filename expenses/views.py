
import csv
from django.http import HttpResponse
from django.db import transaction
from rest_framework import viewsets
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework.decorators import action

from .models import Client, Category, Operation, Budget
from .serializers import (
    RegisterSerializer, CategorySerializer,
    OperationSerializer, BudgetSerializer,
)


class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        s = RegisterSerializer(data=request.data)
        if s.is_valid():
            s.save()
            return Response({"ok": "Пользователь создан"}, status=201)
        return Response(s.errors, status=400)


class CategoryViewSet(viewsets.ModelViewSet):
    serializer_class = CategorySerializer

    def get_queryset(self):
        return Category.objects.filter(client=self.request.user)

    def perform_create(self, serializer):
        serializer.save(client=self.request.user)

    def destroy(self, request, *args, **kwargs):
        cat = self.get_object()
        if Operation.objects.filter(category=cat).exists():
            return Response({"error": "Нельзя удалить: по категории есть операции"}, status=400)
        Budget.objects.filter(category=cat).delete()
        cat.delete()
        return Response(status=204)


class OperationViewSet(viewsets.ModelViewSet):
    serializer_class = OperationSerializer

    def get_queryset(self):
        qs = Operation.objects.filter(client=self.request.user)
        start = self.request.query_params.get("start")
        end = self.request.query_params.get("end")
        cat = self.request.query_params.get("category")
        op_type = self.request.query_params.get("type")
        if start:
            qs = qs.filter(date__gte=start)
        if end:
            qs = qs.filter(date__lte=end)
        if cat:
            qs = qs.filter(category_id=cat)
        if op_type in ("expense", "income"):
            qs = qs.filter(type=op_type)
        return qs.order_by("-date")

    def perform_create(self, serializer):
        with transaction.atomic():
            op = serializer.save(client=self.request.user)
            budget = Budget.objects.filter(
                client=self.request.user,
                category=op.category,
                period=op.date.strftime("%Y-%m"),
            ).first()
            self._limit_warning = None
            if budget and op.type == "expense" and budget.is_exceeded():
                self._limit_warning = {
                    "message": f"Превышен лимит: потрачено {budget.spent()} из {budget.amount}"
                }

    def create(self, request, *args, **kwargs):
        response = super().create(request, *args, **kwargs)
        if getattr(self, "_limit_warning", None):
            response.data["limit_warning"] = self._limit_warning
        return response


class BudgetViewSet(viewsets.ModelViewSet):
    serializer_class = BudgetSerializer

    def get_queryset(self):
        return Budget.objects.filter(client=self.request.user)

    def perform_create(self, serializer):
        serializer.save(client=self.request.user)

    @action(detail=True, methods=["get"])
    def status(self, request, pk=None):
        b = self.get_object()
        return Response({"spent": b.spent(), "exceeded": b.is_exceeded()})


class ReportView(APIView):
    def get(self, request):
        start = request.query_params.get("start")
        end = request.query_params.get("end")
        if not start or not end:
            return Response({"error": "Нужны параметры start и end"}, status=400)

        ops = Operation.objects.filter(client=request.user, date__gte=start, date__lte=end)

        by_category = {}
        for op in ops.filter(type="expense"):
            name = op.category.name
            by_category[name] = by_category.get(name, 0) + float(op.amount)

        total_income = sum(float(o.amount) for o in ops.filter(type="income"))
        total_expense = sum(float(o.amount) for o in ops.filter(type="expense"))

        result = {
            "start": start,
            "end": end,
            "total_income": total_income,
            "total_expense": total_expense,
            "balance": total_income - total_expense,
            "by_category": by_category,
        }

        if request.query_params.get("export") == "csv":
            response = HttpResponse(content_type="text/csv; charset=utf-8")
            response["Content-Disposition"] = 'attachment; filename="report.csv"'
            response.write("\ufeff")
            writer = csv.writer(response, delimiter=";")
            writer.writerow(["Период", start, end])
            writer.writerow(["Доходы", total_income])
            writer.writerow(["Расходы", total_expense])
            writer.writerow(["Баланс", total_income - total_expense])
            writer.writerow([])
            writer.writerow(["Категория", "Сумма"])
            for name, total in by_category.items():
                writer.writerow([name, total])
            return response

        return Response(result)
