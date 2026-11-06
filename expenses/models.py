
from django.contrib.auth.models import AbstractUser
from django.db import models


class Client(AbstractUser):
    """Пользователь системы."""
    pass


class Category(models.Model):
    TYPES = [("expense", "Расход"), ("income", "Доход")]

    client = models.ForeignKey(Client, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    type = models.CharField(max_length=10, choices=TYPES)
    color = models.CharField(max_length=7, default="#000000")

    class Meta:
        unique_together = ("client", "name")

    def __str__(self):
        return self.name


class Operation(models.Model):
    """Операция: доход или расход."""
    TYPES = [("expense", "Расход"), ("income", "Доход")]

    client = models.ForeignKey(Client, on_delete=models.CASCADE)
    category = models.ForeignKey(Category, on_delete=models.PROTECT)
    type = models.CharField(max_length=10, choices=TYPES)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    date = models.DateField()
    comment = models.CharField(max_length=255, blank=True)

    def signed_amount(self):
        return -self.amount if self.type == "expense" else self.amount

    def __str__(self):
        return f"{self.get_type_display()} {self.amount}"


class Budget(models.Model):
    client = models.ForeignKey(Client, on_delete=models.CASCADE)
    category = models.ForeignKey(Category, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    period = models.CharField(max_length=7)  # YYYY-MM

    def spent(self):
        year, month = map(int, self.period.split("-"))
        qs = Operation.objects.filter(
            client=self.client,
            category=self.category,
            type="expense",
            date__year=year,
            date__month=month,
        )
        total = qs.aggregate(models.Sum("amount"))["amount__sum"]
        return total or 0

    def is_exceeded(self):
        return self.spent() > self.amount

    def __str__(self):
        return f"Бюджет {self.category.name} на {self.period}"
