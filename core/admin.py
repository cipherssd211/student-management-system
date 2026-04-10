from django.contrib import admin, messages
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import path
from django import forms
from .models import Timetable
from .models import Activity,StudyMaterial, Result, Leave, Notification
from django.utils.html import format_html
from django.core.mail import send_mail

from .models import (
    AcademicLevel,
    AcademicStream,
    ClassRoom,
    Subject,
    Student,
    Teacher,
    Attendance,
    Marks,
    StudentApplication,
    TeacherApplication,
    AuditLog,
    Notice,
    Timetable,
)

from .services import enroll_student, enroll_teacher


# =====================================================
# ACADEMIC STRUCTURE
# =====================================================
@admin.register(AcademicLevel)
class AcademicLevelAdmin(admin.ModelAdmin):
    list_display = ('name', 'has_streams')
    search_fields = ('name',)


@admin.register(AcademicStream)
class AcademicStreamAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)


# =====================================================
# CLASSROOM
# =====================================================
@admin.register(ClassRoom)
class ClassRoomAdmin(admin.ModelAdmin):
    list_display = ('level', 'stream', 'section', 'capacity')
    list_filter = ('level', 'stream')
    search_fields = ('section',)

# =====================================================
# STUDENT ADMIN (WITH SEARCH 🔍)
# =====================================================
@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):

    list_display = ('student_id', 'user', 'classroom', 'school_email')

    search_fields = (
        'student_id',
        'user__username',
        'user__first_name',
        'user__last_name',
        'school_email',
    )

    list_filter = ('classroom',)

# =====================================================
# TEACHER ADMIN (WITH SEARCH 🔍)
# =====================================================
@admin.register(Teacher)
class TeacherAdmin(admin.ModelAdmin):

    list_display = ('teacher_id', 'user', 'school_email')

    search_fields = (
        'teacher_id',
        'user__username',
        'user__first_name',
        'user__last_name',
        'school_email',
    )

# =====================================================
# SUBJECT
# =====================================================
@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ('name', 'level', 'stream')
    list_filter = ('level', 'stream')
    search_fields = ('name',)


# =====================================================
# BASIC REGISTRATION
# =====================================================
#admin.site.register(Student)
#admin.site.register(Teacher)
admin.site.register(Attendance)
admin.site.register(Marks)
#admin.site.register(Notice)
admin.site.register(Timetable)
admin.site.register(Activity)


# =====================================================
# STUDENT ENROLLMENT FORM
# =====================================================
class StudentEnrollmentForm(forms.Form):
    classroom = forms.ModelChoiceField(
        queryset=ClassRoom.objects.none(),
        label="Assign Class",
        required=True
    )

    def __init__(self, *args, **kwargs):
        application = kwargs.pop('application', None)
        super().__init__(*args, **kwargs)

        if application:
            qs = ClassRoom.objects.filter(level=application.applied_level)
            if application.applied_stream:
                qs = qs.filter(stream=application.applied_stream)
            self.fields['classroom'].queryset = qs


# =====================================================
# STUDENT APPLICATION ADMIN
# =====================================================
@admin.register(StudentApplication)
class StudentApplicationAdmin(admin.ModelAdmin):

    list_display = (
        'full_name',
        'gender',
        'personal_email',
        'applied_date',
        'enrolled_date',
    )

    search_fields = ('full_name', 'personal_email')
    readonly_fields = ('applied_date', 'enrolled_date')

    actions = ('confirm_enrollment',)

    # -------------------------
    def confirm_enrollment(self, request, queryset):
        if queryset.count() != 1:
            self.message_user(request, "Select ONE student only.", messages.ERROR)
            return

        application = queryset.first()

        if application.enrolled_date:
            self.message_user(
                request,
                "This student is already enrolled.",
                messages.WARNING
            )
            return

        return redirect(f'./enroll/{application.id}/')

    confirm_enrollment.short_description = "Confirm Enrollment (Assign Class)"

    # -------------------------
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                'enroll/<int:application_id>/',
                self.admin_site.admin_view(self.enroll_student_view),
            ),
        ]
        return custom_urls + urls

    # -------------------------
    def enroll_student_view(self, request, application_id):
        application = get_object_or_404(StudentApplication, id=application_id)

        if application.enrolled_date:
            self.message_user(
                request,
                "This student is already enrolled.",
                messages.ERROR
            )
            return redirect('../../')

        if request.method == 'POST':
            form = StudentEnrollmentForm(request.POST, application=application)
            if form.is_valid():
                classroom = form.cleaned_data['classroom']
                try:
                    student, password = enroll_student(application, classroom)
                except Exception as e:
                    self.message_user(request, str(e), messages.ERROR)
                    return redirect('../../')

                self.message_user(
                    request,
                    f"""
Student Successfully Enrolled

Username: {student.user.username}
Email: {student.school_email}
Password: {password}
""",
                    messages.SUCCESS
                )
                return redirect('../../')
        else:
            form = StudentEnrollmentForm(application=application)

        return render(
            request,
            'admin/enroll_student.html',
            {
                'application': application,
                'form': form,
            }
        )


# =====================================================
# TEACHER APPLICATION ADMIN
# =====================================================
@admin.register(TeacherApplication)
class TeacherApplicationAdmin(admin.ModelAdmin):

    list_display = (
        'full_name',
        'personal_email',
        'enrolled_date',
    )

    search_fields = ('full_name', 'personal_email')

    filter_horizontal = (
        'academic_levels',
        'academic_streams',
        'subjects_applied',
    )

    actions = ('confirm_teacher_enrollment',)

    # -------------------------
    def confirm_teacher_enrollment(self, request, queryset):
        if queryset.count() != 1:
            self.message_user(request, "Select ONE teacher only.", messages.ERROR)
            return

        application = queryset.first()

        if application.enrolled_date:
            self.message_user(
                request,
                "This teacher is already enrolled.",
                messages.WARNING
            )
            return

        try:
            teacher, password = enroll_teacher(application)
        except Exception as e:
            self.message_user(request, str(e), messages.ERROR)
            return

        self.message_user(
            request,
            f"""
Teacher Successfully Enrolled

Username: {teacher.user.username}
Email: {teacher.school_email}
Password: {password}
""",
            messages.SUCCESS
        )




# =====================================================
# AUDIT LOG (READ ONLY)
# =====================================================
@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = (
        'timestamp',
        'performed_by',
        'action',
        'target_type',
        'target_identifier',
    )
    readonly_fields = list_display


@admin.register(Notice)
class NoticeAdmin(admin.ModelAdmin):
    list_display = ('title', 'target_role', 'created_by', 'created_at')
    list_filter = ('target_role', 'created_at')
    search_fields = ('title', 'message')



@admin.register(StudyMaterial)
class StudyMaterialAdmin(admin.ModelAdmin):

    list_display = ('title', 'teacher', 'subject', 'material_type', 'uploaded_at')
    list_filter = ('material_type', 'subject')
    search_fields = ('title',)


@admin.register(Result)
class ResultAdmin(admin.ModelAdmin):
    list_display = ('student', 'term', 'percentage', 'grade')


# ========================================
# LEAVE MANAGEMENT
# ========================================
@admin.register(Leave)
class LeaveAdmin(admin.ModelAdmin):

    # =========================
    # DISPLAY STATUS COLOR
    # =========================
    def colored_status(self, obj):

        if obj.status == "APPROVED":
           return format_html(
            '<span style="color:{};"><b>{}</b></span>',
            "green",
            "Approved"
        )

        elif obj.status == "REJECTED":
           return format_html(
            '<span style="color:{};"><b>{}</b></span>',
            "red",
            "Rejected"
        )

        elif obj.status == "CANCELLED":
          return format_html(
            '<span style="color:{};"><b>{}</b></span>',
            "gray",
            "Cancelled"
        )

        return format_html(
        '<span style="color:{};"><b>{}</b></span>',
        "orange",
        "Pending"
    )

    # =========================
    # ADMIN UI SETTINGS
    # =========================
    list_display = (
        'id',
        'full_name',
        'role',
        'status',
        'colored_status',
        'start_date',
        'end_date'
    )

    list_filter = ('role', 'status')

    search_fields = ('full_name', 'enrollment_number')

    readonly_fields = (
        'user',
        'full_name',
        'enrollment_number',
        'class_level',
        'section',
        'stream',
        'teacher_id',
        'classes_teaching',
        'reason',
        'start_date',
        'end_date',
        'created_at'
    )

    fieldsets = (

        ("👤 User Information", {
            'fields': (
                'user',
                'role',
                'full_name',
                'enrollment_number',
            )
        }),

        ("🏫 Academic Details", {
            'fields': (
                'class_level',
                'section',
                'stream',
                'classes_teaching',
                'teacher_id',
            )
        }),

        ("📝 Leave Details", {
            'fields': (
                'reason',
                'admin_remark',
                'start_date',
                'end_date',
                'status',
            )
        }),

        ("⏱ System Info", {
            'fields': (
                'created_at',
            )
        }),

    )

    # 👇 IMPORTANT (allow admin to change status)
    list_editable = ('status',)

    # =========================
    # 🔔 NOTIFICATION SYSTEM
    # =========================
    def save_model(self, request, obj, form, change):

        if change:
            old_obj = Leave.objects.get(pk=obj.pk)

            # ✅ Check if status changed
            if old_obj.status != obj.status:

                if obj.status == "APPROVED":
                    message = f"Your leave from {obj.start_date} to {obj.end_date} has been approved ✅"

                elif obj.status == "REJECTED":
                    message = f"Your leave from {obj.start_date} to {obj.end_date} has been rejected ❌"

                elif obj.status == "CANCELLED":
                    message = f"Your leave from {obj.start_date} to {obj.end_date} has been cancelled 🚫"

                else:
                    message = ""

                if message:
                    Notification.objects.create(
                        title="Leave Status Update",
                        message=message,
                        for_student=(obj.role == "STUDENT"),
                        for_teacher=(obj.role == "TEACHER")
                    )

        super().save_model(request, obj, form, change)


# ========================================
# APPROVE LEAVE
# ========================================
def approve_leave(self, request, queryset):
    for leave in queryset:

        leave.status = "APPROVED"
        leave.save()

        # ✅ GET PERSONAL EMAIL
        if leave.role == "STUDENT":
            email = leave.user.student.application.personal_email
        else:
            email = leave.user.teacher.application.personal_email

        send_mail(
            subject="Leave Approved",
            message=f"""
Hello {leave.full_name},
Your leave has been APPROVED.
From: {leave.start_date}
To: {leave.end_date}
""",
            from_email=None,
            recipient_list=[email],
            fail_silently=True,
        )

    self.message_user(request, "Leave approved + email sent.")


# ========================================
# REJECT LEAVE
# ========================================
def reject_leave(self, request, queryset):
    for leave in queryset:

        leave.status = "REJECTED"
        leave.save()

        if leave.role == "STUDENT":
            email = leave.user.student.application.personal_email
        else:
            email = leave.user.teacher.application.personal_email

        send_mail(
            subject="Leave Rejected",
            message=f"""
Hello {leave.full_name},
Your leave has been REJECTED.
""",
            from_email=None,
            recipient_list=[email],
            fail_silently=True,
        )

    self.message_user(request, "Leave rejected + email sent.")


# ========================================
# CANCEL LEAVE
# ========================================
def cancel_leave(self, request, queryset):
    for leave in queryset:

        leave.status = "CANCELLED"
        leave.save()

        if leave.role == "STUDENT":
            email = leave.user.student.application.personal_email
        else:
            email = leave.user.teacher.application.personal_email

        send_mail(
            subject="Leave Cancelled",
            message=f"""
Hello {leave.full_name},
Your leave has been CANCELLED by admin.
""",
            from_email=None,
            recipient_list=[email],
            fail_silently=True,
        )

    self.message_user(request, "Leave cancelled + email sent.")



#def get_queryset(self, request):
 #   qs = super().get_queryset(request)
  #  return qs.filter(is_cancelled=False)