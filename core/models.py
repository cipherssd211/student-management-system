from django.db import models
from django.db.models import Q
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils import timezone



# =========================
# VALIDATOR
# =========================
def validate_full_name(value):
    names = value.strip().split()
    if len(names) < 3 or len(names) > 4:
        raise ValidationError("Full name must contain 3–4 names.")


# =========================
# CHOICES
# =========================
GENDER_CHOICES = [
    ('MALE', 'Male'),
    ('FEMALE', 'Female'),
    ('OTHER', 'Other'),
]

GUARDIAN_RELATIONSHIP_CHOICES = [
    ('FATHER', 'Father'),
    ('MOTHER', 'Mother'),
    ('UNCLE', 'Uncle'),
    ('AUNT', 'Aunt'),
    ('BROTHER', 'Brother'),
    ('SISTER', 'Sister'),
    ('GUARDIAN', 'Guardian'),
]

APPLICATION_STATUS_CHOICES = [
    ('PENDING', 'Pending'),
    ('APPROVED', 'Approved'),
    ('REJECTED', 'Rejected'),
]


# =========================
# ACADEMIC STRUCTURE
# =========================
class AcademicLevel(models.Model):
    name = models.CharField(max_length=20, unique=True)
    has_streams = models.BooleanField(default=False)

    def __str__(self):
        return self.name


class AcademicStream(models.Model):
    name = models.CharField(max_length=20, unique=True)

    def clean(self):
        if self.name not in ['Science', 'Arts']:
            raise ValidationError("Only Science and Arts are allowed.")

    def __str__(self):
        return self.name


class Fee(models.Model):
    student = models.ForeignKey('Student', on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    paid = models.BooleanField(default=False)
    reference_code = models.CharField(max_length=100, blank=True, null=True)  # 👈 ADD HERE
    date_paid = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.student} - {self.amount}"


class Timetable(models.Model):

    DAY_CHOICES = [
        ('Monday','Monday'),
        ('Tuesday','Tuesday'),
        ('Wednesday','Wednesday'),
        ('Thursday','Thursday'),
        ('Friday','Friday'),
    ]

    classroom = models.ForeignKey('ClassRoom', on_delete=models.CASCADE)
    subject = models.ForeignKey('Subject', on_delete=models.CASCADE)
    teacher = models.ForeignKey('Teacher', on_delete=models.CASCADE)

    day = models.CharField(max_length=20, choices=DAY_CHOICES)

    start_time = models.TimeField()
    end_time = models.TimeField()

    def __str__(self):
        return f"{self.subject} - {self.day}"
    

# =========================
# LEAVE APPLICATION
# =========================
class Leave(models.Model):

    ROLE_CHOICES = [
        ('STUDENT', 'Student'),
        ('TEACHER', 'Teacher'),
    ]

    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
        ('CANCELLED', 'Cancelled'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)

    role = models.CharField(max_length=10, choices=ROLE_CHOICES)

    # Common Fields
    full_name = models.CharField(max_length=150)
    enrollment_number = models.CharField(max_length=50)

    # Student specific
    class_level = models.CharField(max_length=20, blank=True)   # Senior 1–4
    section = models.CharField(max_length=5, blank=True)        # A, B, C
    stream = models.CharField(max_length=20, blank=True)        # Science / Arts

    # Teacher specific
    teacher_id = models.CharField(max_length=10, blank=True)
    classes_teaching = models.CharField(max_length=100, blank=True)

    # Leave info
    reason = models.TextField()
    start_date = models.DateField()
    end_date = models.DateField()

    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default='PENDING'
    )
    is_cancelled = models.BooleanField(default=False);

    admin_remark = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.full_name} - {self.role} - {self.status}"


# =========================
# CLASSROOM
# =========================
class ClassRoom(models.Model):
    level = models.ForeignKey(AcademicLevel, on_delete=models.CASCADE)
    stream = models.ForeignKey(
        AcademicStream,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    section = models.CharField(max_length=5)
    capacity = models.PositiveIntegerField(default=45)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['level', 'section'],
                condition=Q(stream__isnull=True),
                name='unique_classroom_no_stream'
            ),
            models.UniqueConstraint(
                fields=['level', 'stream', 'section'],
                condition=Q(stream__isnull=False),
                name='unique_classroom_with_stream'
            ),
        ]

    def clean(self):
        if self.level.has_streams and not self.stream:
            raise ValidationError("Stream is required for this level.")
        if not self.level.has_streams and self.stream:
            raise ValidationError("Stream must NOT be selected for this level.")

    def __str__(self):
        return f"{self.level} {self.stream or ''} ({self.section})"


# =========================
# SUBJECT
# =========================
class Subject(models.Model):
    name = models.CharField(max_length=100)
    level = models.ForeignKey(AcademicLevel, on_delete=models.CASCADE)
    stream = models.ForeignKey(
        AcademicStream,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['name', 'level'],
                condition=Q(stream__isnull=True),
                name='unique_subject_no_stream'
            ),
            models.UniqueConstraint(
                fields=['name', 'level', 'stream'],
                condition=Q(stream__isnull=False),
                name='unique_subject_with_stream'
            ),
        ]

    def clean(self):
        if self.level.has_streams and not self.stream:
            raise ValidationError("Stream is required for this level.")
        if not self.level.has_streams and self.stream:
            raise ValidationError("Stream must NOT be selected for this level.")

    def __str__(self):
        return f"{self.name} - {self.level}{f' {self.stream}' if self.stream else ''}"


# =========================
# STUDENT
# =========================
class Student(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    classroom = models.ForeignKey(ClassRoom, on_delete=models.SET_NULL, null=True)

    student_id = models.CharField(max_length=20, unique=True)
    school_email = models.EmailField(unique=True)

    admission_year = models.PositiveIntegerField()
    sequence_number = models.PositiveIntegerField()

    application = models.OneToOneField(
        'StudentApplication',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    enrolled_date = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['admission_year', 'sequence_number'],
                name='unique_student_sequence'
            )
        ]

    def __str__(self):
        return self.student_id


# =========================
# TEACHER
# =========================
class Teacher(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    school_email = models.EmailField(unique=True)

    application = models.OneToOneField(
        'TeacherApplication',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    subjects = models.ManyToManyField(Subject, blank=True)
    teacher_id = models.CharField(max_length=10, unique=True, blank=True)

    def __str__(self):
        return self.user.username


# =========================
# ATTENDANCE
# =========================
class Attendance(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    date = models.DateField()
    lectures_held = models.PositiveIntegerField(default=1)
    lectures_attended = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['student', 'subject', 'date'],
                name='unique_attendance'
            )
        ]

    def __str__(self):
        return f"{self.student.student_id} - {self.subject.name} - {self.date}"

# =========================
# MARKS
# =========================
class Marks(models.Model):

    TERM_CHOICES = [
        ('TERM1', 'First Term'),
        ('TERM2', 'Second Term'),
        ('FINAL', 'Final Term'),
    ]

    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)

    term = models.CharField(max_length=10, choices=TERM_CHOICES)

    marks = models.IntegerField()

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.student} - {self.subject} - {self.term}"
    

class Result(models.Model):

    TERM_CHOICES = [
        ('TERM1', 'First Term'),
        ('TERM2', 'Second Term'),
        ('FINAL', 'Final Result'),
    ]

    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    term = models.CharField(max_length=10, choices=TERM_CHOICES)
    total_marks = models.IntegerField()
    percentage = models.FloatField()
    grade = models.CharField(max_length=5, blank=True)
    remarks = models.TextField(blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.student} - {self.term}"


# =========================
# STUDENT APPLICATION
# =========================
class StudentApplication(models.Model):
    application_status = models.CharField(
        max_length=10,
        choices=APPLICATION_STATUS_CHOICES,
        default='PENDING'
    )

    full_name = models.CharField(max_length=150, validators=[validate_full_name])
    date_of_birth = models.DateField()
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES)

    passport_photo = models.ImageField(upload_to='students/photos/')
    personal_email = models.EmailField(unique=True)
    phone_number = models.CharField(max_length=20)

    guardian_name = models.CharField(max_length=150)
    guardian_relationship = models.CharField(
        max_length=20,
        choices=GUARDIAN_RELATIONSHIP_CHOICES
    )
    guardian_phone = models.CharField(max_length=20)

    applied_level = models.ForeignKey(AcademicLevel, on_delete=models.SET_NULL, null=True)
    applied_stream = models.ForeignKey(
        AcademicStream,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    applied_date = models.DateTimeField(auto_now_add=True)
    enrolled_date = models.DateTimeField(null=True, blank=True)

    def clean(self):
        if self.applied_level and self.applied_level.has_streams and not self.applied_stream:
            raise ValidationError("Stream is required for this level.")
        if self.applied_level and not self.applied_level.has_streams and self.applied_stream:
            raise ValidationError("Stream must NOT be selected for this level.")

    def __str__(self):
        return self.full_name


# =========================
# TEACHER APPLICATION
# =========================
class TeacherApplication(models.Model):
    application_status = models.CharField(
        max_length=10,
        choices=APPLICATION_STATUS_CHOICES,
        default='PENDING'
    )

    full_name = models.CharField(max_length=150, validators=[validate_full_name])
    date_of_birth = models.DateField()
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES)

    personal_email = models.EmailField(unique=True)
    phone_number = models.CharField(max_length=20)

    passport_photo = models.ImageField(upload_to='teachers/photos/')
    cv_document = models.FileField(upload_to='teachers/cv/')

    highest_qualification = models.CharField(max_length=100)
    years_of_experience = models.PositiveIntegerField()

    academic_levels = models.ManyToManyField(AcademicLevel)
    academic_streams = models.ManyToManyField(AcademicStream, blank=True)
    subjects_applied = models.ManyToManyField(Subject)

    applied_date = models.DateTimeField(auto_now_add=True)
    enrolled_date = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.full_name


# =========================
# AUDIT LOG
# =========================
class AuditLog(models.Model):
    ACTION_CHOICES = [
        ('APPROVE_STUDENT', 'Approve Student'),
        ('REJECT_STUDENT', 'Reject Student'),
        ('APPROVE_TEACHER', 'Approve Teacher'),
        ('REJECT_TEACHER', 'Reject Teacher'),
        ('ENROLL', 'Enroll'),
        ('ACCOUNT_DEACTIVATED', 'Account Deactivated'),
    ]

    performed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    action = models.CharField(max_length=30, choices=ACTION_CHOICES)

    # ✅ THIS FIELD WAS MISSING
    target_type = models.CharField(max_length=50, help_text="Student, Teacher, User, ClassRoom, Subject, etc.")
    target_identifier = models.CharField( max_length=100, help_text="ID, username, or unique reference")
    description = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.action} - {self.target_type} - {self.target_identifier}"


# =========================
# NOTICES
# =========================
class Notice(models.Model):
    title = models.CharField(max_length=200)
    message = models.TextField()
    target_role = models.CharField(
        max_length=20,
        choices=[
            ('ALL', 'All'),
            ('STUDENT', 'Student'),
            ('TEACHER', 'Teacher'),
        ],
        default='ALL'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return self.title

# =============================
# EXTRA CURRICULAR ACTIVITIES
# =============================
class Activity(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title


# =========================
# STUDY MATERIALS
# =========================
class StudyMaterial(models.Model):

    MATERIAL_TYPES = [
        ('PDF', 'PDF'),
        ('PPT', 'PPT'),
        ('VIDEO', 'Video'),
        ('NOTES', 'Notes'),
    ]

    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)

    title = models.CharField(max_length=200)
    material_type = models.CharField(max_length=10, choices=MATERIAL_TYPES)

    file = models.FileField(upload_to='materials/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title
    

class NoticeRead(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    notice = models.ForeignKey(Notice, on_delete=models.CASCADE)
    is_read = models.BooleanField(default=False)

    class Meta:
        unique_together = ('user', 'notice')


class Notification(models.Model):
    title = models.CharField(max_length=255)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    # who should see it
    for_admin = models.BooleanField(default=False)
    for_teacher = models.BooleanField(default=False)
    for_student = models.BooleanField(default=True)

    is_read = models.BooleanField(default=False)

    def __str__(self):
        return self.title