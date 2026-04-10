from datetime import datetime
from django.db.models import Max
from django.contrib.auth.models import User
from django.core.mail import send_mail
import random
import string

from .models import Student, SchoolSettings


# =================================================
# STUDENT ID GENERATION
# =================================================
def generate_student_id(classroom):
    year = datetime.now().year
    year_code = str(year)[-2:]           # 2026 → "26"
    prefix = f"{year_code}STD"

    last_student = Student.objects.filter(
        classroom=classroom,
        admission_year=year
    ).aggregate(
        max_seq=Max('sequence_number')
    )

    next_sequence = (last_student['max_seq'] or 0) + 1
    sequence_code = str(next_sequence).zfill(3)

    student_id = f"{prefix}{sequence_code}"

    return student_id, year, next_sequence


# =================================================
# STUDENT CREDENTIALS GENERATION
# =================================================
def generate_student_credentials(student_id):
    settings = SchoolSettings.objects.first()
    domain = settings.email_domain

    username = student_id.lower()
    email = f"{username}@{domain}"

    return username, email


# =================================================
# TEACHER CREDENTIALS GENERATION
# =================================================
def generate_teacher_credentials(full_name):
    settings = SchoolSettings.objects.first()
    domain = settings.email_domain

    names = full_name.lower().split()
    base_username = f"{names[0]}.{names[1]}"
    username = base_username

    counter = 1
    while User.objects.filter(username=username).exists():
        counter += 1
        username = f"{base_username}{counter}"

    email = f"{username}@{domain}"

    return username, email


# =================================================
# STRONG PASSWORD GENERATOR (6–8 CHARACTERS)
# =================================================
def generate_strong_password():
    """
    Generates a strong random password:
    - Length: 6, 7, or 8 characters
    - Includes: uppercase, lowercase, numbers, symbols
    """

    length = random.choice([6, 7, 8])

    characters = (
        string.ascii_lowercase +
        string.ascii_uppercase +
        string.digits +
        "!@#$%&*"
    )

    password = ''.join(random.choice(characters) for _ in range(length))
    return password
