
from django.contrib import admin
from .models import Client, Category, Operation, Budget

admin.site.register(Client)
admin.site.register(Category)
admin.site.register(Operation)
admin.site.register(Budget)
