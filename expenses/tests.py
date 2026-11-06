from decimal import Decimal
from datetime import date, timedelta
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status

from .models import Category, Operation, Budget


User = get_user_model()


class BaseTestCase(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="alex", password="testpass123", email="alex@test.ru"
        )
        self.client.force_authenticate(user=self.user)
        self.cat_expense = Category.objects.create(
            client=self.user, name="Еда", type="expense", color="#FF0000"
        )
        self.cat_income = Category.objects.create(
            client=self.user, name="Зарплата", type="income", color="#00AA00"
        )


class ModelTests(BaseTestCase):
    def test_signed_amount_expense(self):
        op = Operation.objects.create(
            client=self.user, category=self.cat_expense,
            type="expense", amount=Decimal("500.00"), date=date.today()
        )
        self.assertEqual(op.signed_amount(), Decimal("-500.00"))

    def test_signed_amount_income(self):
        op = Operation.objects.create(
            client=self.user, category=self.cat_income,
            type="income", amount=Decimal("50000.00"), date=date.today()
        )
        self.assertEqual(op.signed_amount(), Decimal("50000.00"))

    def test_budget_spent_empty(self):
        b = Budget.objects.create(
            client=self.user, category=self.cat_expense,
            amount=Decimal("1000.00"), period=date.today().strftime("%Y-%m")
        )
        self.assertEqual(b.spent(), 0)

    def test_budget_spent_with_operations(self):
        Budget.objects.create(
            client=self.user, category=self.cat_expense,
            amount=Decimal("1000.00"), period=date.today().strftime("%Y-%m")
        )
        Operation.objects.create(
            client=self.user, category=self.cat_expense,
            type="expense", amount=Decimal("300.00"), date=date.today()
        )
        Operation.objects.create(
            client=self.user, category=self.cat_expense,
            type="expense", amount=Decimal("200.00"), date=date.today()
        )
        self.assertEqual(Budget.objects.first().spent(), Decimal("500.00"))

    def test_budget_is_exceeded_false(self):
        Budget.objects.create(
            client=self.user, category=self.cat_expense,
            amount=Decimal("1000.00"), period=date.today().strftime("%Y-%m")
        )
        Operation.objects.create(
            client=self.user, category=self.cat_expense,
            type="expense", amount=Decimal("500.00"), date=date.today()
        )
        self.assertFalse(Budget.objects.first().is_exceeded())

    def test_budget_is_exceeded_true(self):
        Budget.objects.create(
            client=self.user, category=self.cat_expense,
            amount=Decimal("100.00"), period=date.today().strftime("%Y-%m")
        )
        Operation.objects.create(
            client=self.user, category=self.cat_expense,
            type="expense", amount=Decimal("500.00"), date=date.today()
        )
        self.assertTrue(Budget.objects.first().is_exceeded())

    def test_category_str(self):
        self.assertEqual(str(self.cat_expense), "Еда")


class RegisterTests(APITestCase):
    def test_register_ok(self):
        resp = self.client.post(reverse("register"), {
            "username": "newuser", "email": "new@test.ru",
            "password": "StrongPass123"
        }, format="json")
        self.assertEqual(resp.status_code, 201)
        self.assertTrue(User.objects.filter(username="newuser").exists())

    def test_register_bad_data(self):
        resp = self.client.post(reverse("register"), {"username": "x"}, format="json")
        self.assertEqual(resp.status_code, 400)


class CategoryTests(BaseTestCase):
    def test_list_categories(self):
        resp = self.client.get(reverse("category-list"))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 2)

    def test_create_category(self):
        resp = self.client.post(reverse("category-list"), {
            "name": "Транспорт", "type": "expense", "color": "#0000FF"
        }, format="json")
        self.assertEqual(resp.status_code, 201)

    def test_update_category(self):
        resp = self.client.patch(
            reverse("category-detail", args=[self.cat_expense.id]),
            {"name": "Еда дома"}, format="json"
        )
        self.assertEqual(resp.status_code, 200)

    def test_delete_category_without_operations(self):
        cat = Category.objects.create(client=self.user, name="Пустая", type="expense")
        resp = self.client.delete(reverse("category-detail", args=[cat.id]))
        self.assertEqual(resp.status_code, 204)

    def test_delete_category_with_operations_forbidden(self):
        Operation.objects.create(
            client=self.user, category=self.cat_expense,
            type="expense", amount=100, date=date.today()
        )
        resp = self.client.delete(reverse("category-detail", args=[self.cat_expense.id]))
        self.assertEqual(resp.status_code, 400)

    def test_delete_category_removes_budget(self):
        cat = Category.objects.create(client=self.user, name="С бюджетом", type="expense")
        Budget.objects.create(client=self.user, category=cat, amount=1000, period="2026-11")
        resp = self.client.delete(reverse("category-detail", args=[cat.id]))
        self.assertEqual(resp.status_code, 204)
        self.assertEqual(Budget.objects.filter(category=cat).count(), 0)


class OperationTests(BaseTestCase):
    def test_create_expense_ok(self):
        resp = self.client.post(reverse("operation-list"), {
            "category": self.cat_expense.id, "type": "expense",
            "amount": "500.00", "date": date.today().isoformat(),
            "comment": "Обед",
        }, format="json")
        self.assertEqual(resp.status_code, 201)

    def test_create_income_ok(self):
        resp = self.client.post(reverse("operation-list"), {
            "category": self.cat_income.id, "type": "income",
            "amount": "50000.00", "date": date.today().isoformat(),
        }, format="json")
        self.assertEqual(resp.status_code, 201)

    def test_create_negative_amount_fails(self):
        resp = self.client.post(reverse("operation-list"), {
            "category": self.cat_expense.id, "type": "expense",
            "amount": "-100.00", "date": date.today().isoformat(),
        }, format="json")
        self.assertEqual(resp.status_code, 400)

    def test_create_future_date_fails(self):
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        resp = self.client.post(reverse("operation-list"), {
            "category": self.cat_expense.id, "type": "expense",
            "amount": "100.00", "date": tomorrow,
        }, format="json")
        self.assertEqual(resp.status_code, 400)

    def test_create_type_mismatch_fails(self):
        resp = self.client.post(reverse("operation-list"), {
            "category": self.cat_income.id, "type": "expense",
            "amount": "100.00", "date": date.today().isoformat(),
        }, format="json")
        self.assertEqual(resp.status_code, 400)

    def test_create_with_limit_warning(self):
        Budget.objects.create(
            client=self.user, category=self.cat_expense,
            amount=100, period=date.today().strftime("%Y-%m")
        )
        resp = self.client.post(reverse("operation-list"), {
            "category": self.cat_expense.id, "type": "expense",
            "amount": "500.00", "date": date.today().isoformat(),
        }, format="json")
        self.assertEqual(resp.status_code, 201)
        self.assertIn("limit_warning", resp.data)

    def test_update_operation(self):
        op = Operation.objects.create(
            client=self.user, category=self.cat_expense,
            type="expense", amount=100, date=date.today()
        )
        resp = self.client.patch(
            reverse("operation-detail", args=[op.id]),
            {"amount": "250.00"}, format="json"
        )
        self.assertEqual(resp.status_code, 200)

    def test_delete_operation(self):
        op = Operation.objects.create(
            client=self.user, category=self.cat_expense,
            type="expense", amount=100, date=date.today()
        )
        resp = self.client.delete(reverse("operation-detail", args=[op.id]))
        self.assertEqual(resp.status_code, 204)

    def test_filter_by_type(self):
        Operation.objects.create(
            client=self.user, category=self.cat_expense,
            type="expense", amount=100, date=date.today()
        )
        Operation.objects.create(
            client=self.user, category=self.cat_income,
            type="income", amount=5000, date=date.today()
        )
        resp = self.client.get(reverse("operation-list") + "?type=expense")
        self.assertEqual(len(resp.data), 1)

    def test_filter_by_date_range(self):
        Operation.objects.create(
            client=self.user, category=self.cat_expense,
            type="expense", amount=100, date=date(2026, 1, 15)
        )
        Operation.objects.create(
            client=self.user, category=self.cat_expense,
            type="expense", amount=200, date=date(2026, 6, 15)
        )
        resp = self.client.get(reverse("operation-list") + "?start=2026-01-01&end=2026-01-31")
        self.assertEqual(len(resp.data), 1)


class BudgetTests(BaseTestCase):
    def test_create_budget_ok(self):
        resp = self.client.post(reverse("budget-list"), {
            "category": self.cat_expense.id, "amount": "10000.00", "period": "2026-11",
        }, format="json")
        self.assertEqual(resp.status_code, 201)

    def test_create_budget_for_income_forbidden(self):
        resp = self.client.post(reverse("budget-list"), {
            "category": self.cat_income.id, "amount": "10000.00", "period": "2026-11",
        }, format="json")
        self.assertEqual(resp.status_code, 400)

    def test_budget_status(self):
        b = Budget.objects.create(
            client=self.user, category=self.cat_expense,
            amount=1000, period=date.today().strftime("%Y-%m")
        )
        Operation.objects.create(
            client=self.user, category=self.cat_expense,
            type="expense", amount=2000, date=date.today()
        )
        resp = self.client.get(reverse("budget-status", args=[b.id]))
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data["exceeded"])


class ReportTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        Operation.objects.create(
            client=self.user, category=self.cat_expense,
            type="expense", amount=Decimal("1500.00"), date=date(2026, 11, 1)
        )
        Operation.objects.create(
            client=self.user, category=self.cat_income,
            type="income", amount=Decimal("50000.00"), date=date(2026, 11, 1)
        )

    def test_report_ok(self):
        resp = self.client.get(reverse("report") + "?start=2026-11-01&end=2026-11-30")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["total_income"], 50000.0)
        self.assertEqual(resp.data["total_expense"], 1500.0)

    def test_report_no_dates(self):
        resp = self.client.get(reverse("report"))
        self.assertEqual(resp.status_code, 400)

    def test_report_csv_export(self):
        resp = self.client.get(reverse("report") + "?start=2026-11-01&end=2026-11-30&export=csv")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("text/csv", resp["Content-Type"])


class PermissionTests(APITestCase):
    def test_unauthorized_access_denied(self):
        resp = self.client.get(reverse("category-list"))
        self.assertEqual(resp.status_code, 403)