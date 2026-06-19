from django.db import models

class UserRegistration(models.Model):
    name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    industry = models.CharField(max_length=100)
    password = models.CharField(max_length=255, default="")
    def __str__(self):
        return self.name