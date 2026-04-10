import random
import string

from django.contrib.auth.models import User
from django.utils import timezone
from django.db import transaction

from .models import (
    Student,
    Teacher,
    ClassRoom,
)
from .audit import log_action


# =================================================
# CONFIGURATION
# =================================================
SCHOOL_DOMAIN = "schoolname.edu.ss"


# =================================================
# STRONG PASSWORD GENERATOR (6–8 chars ONLY)
# Easy to remember but secure
# =================================================
def generate_password():
    """
    Password rules:
    - Length: 6 to 8
    - Must contain:
        ✔ Uppercase
        ✔ Lowercase
        ✔ Number
        ✔ Symbol
    """

    length = random.choice([6, 7, 8])

    lowercase = random.choice(string.ascii_lowercase)
    uppercase = random.choice(string.ascii_uppercase)
    digit = random.choice(string.digits)
    symbol = random.choice("!@#$%&*")

    # remaining characters
    remaining_length = length - 4
    all_chars = string.ascii_letters + string.digits + "!@#$%&*"
    remaining = random.choices(all_chars, k=remaining_length)

    password_list = [lowercase, uppercase, digit, symbol] + remaining

    random.shuffle(password_list)

    return "".join(password_list)


# =================================================
# STUDENT ID GENERATOR
# Format: 26std001
# =================================================
def generate_student_id():
    year_short = timezone.now().strftime("%y")

    last_student = Student.objects.filter(
        admission_year=year_short
    ).order_by('-sequence_number').first()

    next_seq = 1 if not last_student else last_student.sequence_number + 1
    seq_str = str(next_seq).zfill(3)

    student_id = f"{year_short}std{seq_str}"
    return student_id, year_short, next_seq


# =================================================
# TEACHER ID GENERATOR (001, 002, 003...)
# =================================================
def generate_teacher_id():
    last_teacher = Teacher.objects.exclude(teacher_id__isnull=True).order_by('-teacher_id').first()

    if last_teacher and last_teacher.teacher_id:
        last_id = int(last_teacher.teacher_id)
        next_id = last_id + 1
    else:
        next_id = 1

    return str(next_id).zfill(3)


# =================================================
# STUDENT CREDENTIALS
# =================================================
def generate_student_credentials(student_id):
    username = student_id
    email = f"{student_id}@{SCHOOL_DOMAIN}"
    return username, email


# =================================================
# TEACHER CREDENTIALS
# =================================================
def generate_teacher_credentials(full_name):
    parts = full_name.lower().split()
    first_name = parts[0]
    last_name = parts[1] if len(parts) > 1 else "staff"

    username = f"{first_name}.{last_name}"

    # 🚫 HARD BLOCK: username already exists
    if User.objects.filter(username=username).exists():
        raise ValueError(
            "This teacher has already been approved and enrolled. "
            "Duplicate enrollment is not allowed."
        )

    email = f"{username}@{SCHOOL_DOMAIN}"
    return username, email


# =================================================
# ENROLL STUDENT (ADMIN ASSIGNS CLASS)
# =================================================
@transaction.atomic
def enroll_student(application, classroom: ClassRoom):

    # 🚫 BLOCK: already enrolled
    if application.enrolled_date is not None:
        raise ValueError("This student is already enrolled.")

    # 🚫 BLOCK: student already exists
    if Student.objects.filter(application=application).exists():
        raise ValueError("Student account already exists for this application.")

    # Safety checks
    if classroom.level != application.applied_level:
        raise ValueError("Selected class level does not match application level.")

    if application.applied_level.has_streams:
        if classroom.stream != application.applied_stream:
            raise ValueError("Selected class stream does not match application stream.")

    student_id, year, seq = generate_student_id()
    username, email = generate_student_credentials(student_id)
    password = generate_password()

    # Create auth user
    user = User.objects.create_user(
        username=username,
        email=email,
        password=password,
        first_name=application.full_name.split()[0],
        last_name=" ".join(application.full_name.split()[1:])
    )

    # Create student profile
    student = Student.objects.create(
        user=user,
        student_id=student_id,
        school_email=email,
        classroom=classroom,
        admission_year=year,
        sequence_number=seq,
        application=application
    )

    # Mark application as enrolled
    application.enrolled_date = timezone.now()
    application.save(update_fields=['enrolled_date'])

    # Audit log
    log_action(
        user=None,
        action="ENROLL",
        target_type="Student",
        target_identifier=student_id,
        description=f"Student enrolled in {classroom}"
    )

    return student, password


# =================================================
# ENROLL TEACHER (ADMIN CONFIRMATION)
# =================================================
@transaction.atomic
def enroll_teacher(application):

    # 🚫 BLOCK: already enrolled
    if application.enrolled_date is not None:
        raise ValueError("This teacher is already enrolled.")

    # 🚫 BLOCK: teacher already exists
    if Teacher.objects.filter(application=application).exists():
        raise ValueError("Teacher account already exists for this application.")

    username, email = generate_teacher_credentials(application.full_name)
    password = generate_password()

    # Generate Teacher ID
    teacher_id = generate_teacher_id()
    print("Teacher ID generated:", teacher_id)

    # Create auth user
    user = User.objects.create_user(
        username=username,
        email=email,
        password=password,
        first_name=application.full_name.split()[0],
        last_name=" ".join(application.full_name.split()[1:])
    )

    # Create teacher profile
    teacher = Teacher.objects.create(
        user=user,
        school_email=email,
        application=application,
        teacher_id=teacher_id   # ✅ FIXED
    )

    # Assign subjects
    teacher.subjects.set(application.subjects_applied.all())

    # Mark application as enrolled
    application.enrolled_date = timezone.now()
    application.save(update_fields=['enrolled_date'])

    # Audit log
    log_action(
        user=None,
        action="ENROLL",
        target_type="Teacher",
        target_identifier=teacher_id,
        description="Teacher enrolled successfully"
    )

    return teacher, password


# =================================================
# DEACTIVATE USER
# =================================================
def deactivate_user(user, admin_user, reason=""):
    user.is_active = False
    user.save(update_fields=['is_active'])

    log_action(
        user=admin_user,
        action="ACCOUNT_DEACTIVATED",
        target_type="User",
        target_identifier=user.username,
        description=reason or "User deactivated"
    )