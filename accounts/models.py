import zoneinfo

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.core.exceptions import ValidationError
from django.db import models

DEFAULT_USER_TIMEZONE = "Europe/Lisbon"


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError("Users must have an email address")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True")
        return self._create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(
        default=False,
        help_text=(
            "Django admin login. Only superusers should have this; "
            "warehouse users work on the website via warehouse_* groups."
        ),
    )
    date_joined = models.DateTimeField(auto_now_add=True)
    timezone = models.CharField(
        max_length=64,
        default=DEFAULT_USER_TIMEZONE,
        help_text=(
            "IANA timezone name, e.g. Europe/Lisbon (UTC+1 summer / UTC+0 winter) "
            "or Asia/Singapore (UTC+8). Used for server-rendered dates."
        ),
    )
    warehouse_grade = models.PositiveSmallIntegerField(
        default=1,
        help_text=(
            "Grade within the warehouse group: operator 1–2, manager 1–3. "
            "warehouse_admins ignore this (always treated as 1 / unlimited)."
        ),
    )

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    def __str__(self):
        return self.email

    def clean(self):
        super().clean()
        try:
            zoneinfo.ZoneInfo(self.timezone)
        except (ValueError, KeyError) as exc:
            raise ValidationError(
                {"timezone": f"Unknown timezone: {self.timezone}"}
            ) from exc
