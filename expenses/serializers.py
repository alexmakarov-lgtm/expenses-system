
from rest_framework import serializers
from datetime import date
from .models import Client, Category, Operation, Budget


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = Client
        fields = ["id", "username", "email", "password"]

    def create(self, data):
        return Client.objects.create_user(**data)


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name", "type", "color"]


class OperationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Operation
        fields = ["id", "category", "type", "amount", "date", "comment"]

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Сумма должна быть больше нуля")
        return value

    def validate_date(self, value):
        if value > date.today():
            raise serializers.ValidationError("Дата не может быть в будущем")
        return value

    def validate(self, data):
        if data["category"].type != data["type"]:
            raise serializers.ValidationError("Тип категории не совпадает с типом операции")
        return data


class BudgetSerializer(serializers.ModelSerializer):
    spent = serializers.SerializerMethodField()
    exceeded = serializers.SerializerMethodField()

    class Meta:
        model = Budget
        fields = ["id", "category", "amount", "period", "spent", "exceeded"]

    def get_spent(self, obj):
        return obj.spent()

    def get_exceeded(self, obj):
        return obj.is_exceeded()

    def validate_category(self, value):
        if value.type != "expense":
            raise serializers.ValidationError("Бюджет только для расходов")
        return value
