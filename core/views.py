import stripe
import hashlib
import qrcode
from io import BytesIO
from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.utils import timezone
from django.db.models import Q, Count, Sum, Avg
from datetime import datetime
from django.utils.timezone import now
from django.http import HttpResponse
from .models import Leave
from .models import Notification
from .models import Timetable, Student, Attendance, Marks
from .models import Student, Teacher, ClassRoom, Activity, Notice, StudyMaterial, NoticeRead, Result
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from .models import (
    Student,
    Teacher,
    Subject,
    ClassRoom,
    Marks,
    Attendance,
    Notice,
    Fee, 
    Timetable,
)

# =================================================
# ROLE HELPERS
# =================================================
def is_admin(user):
    return user.is_authenticated and user.is_superuser


def is_teacher(user):
    return user.is_authenticated and Teacher.objects.filter(user=user).exists()


def is_student(user):
    return user.is_authenticated and Student.objects.filter(user=user).exists()


# =================================================
# AUTH
# =================================================
def user_login(request):

    # If already logged in
    if request.user.is_authenticated:
        if is_admin(request.user):
            return redirect('admin_dashboard')
        elif is_teacher(request.user):
            return redirect('teacher_dashboard')
        elif is_student(request.user):
            return redirect('student_dashboard')

    if request.method == "POST":

        identifier = request.POST.get("identifier")
        password = request.POST.get("password")
        role = request.POST.get("role")

        try:
            user_obj = User.objects.get(
                Q(username=identifier) | Q(email=identifier)
            )
        except User.DoesNotExist:
            messages.error(request, "Invalid username or password.")
            return redirect("login")

        user = authenticate(
            request,
            username=user_obj.username,
            password=password
        )

        if user is None:
            messages.error(request, "Invalid username or password.")
            return redirect("login")

        if not user.is_active:
            messages.error(request, "This account is inactive.")
            return redirect("login")

        # ADMIN LOGIN (bypass role)
        if is_admin(user):
            login(request, user)
            return redirect("admin_dashboard")

        # ROLE VALIDATION
        if role == "teacher" and not is_teacher(user):
            messages.error(request, "This account is not a staff account.")
            return redirect("login")

        if role == "student" and not is_student(user):
            messages.error(request, "This account is not a student account.")
            return redirect("login")

        # LOGIN USER
        login(request, user)

        if role == "teacher":
            return redirect("teacher_dashboard")

        if role == "student":
            return redirect("student_dashboard")

        messages.error(request, "Invalid role selected.")
        return redirect("login")

    # VERY IMPORTANT (this fixes your error)
    return render(request, "login.html")


@login_required
def user_logout(request):
    logout(request)
    return redirect('login')


def forgot_password(request):
    return render(request,"forgot_password.html")

def help_page(request):
    return render(request,"help_page.html")

# =================================================
# STUDENT PERFORMANCE
# ================================================
def student_performance(request, student_id):
    student = get_object_or_404(Student, id=student_id)
    # MARKS
    marks = Marks.objects.filter(student=student)
    # ATTENDANCE
    attendance = Attendance.objects.filter(student=student)

    total_held = 0
    total_attended = 0

    for record in attendance:
        total_held += record.lectures_held
        total_attended += record.lectures_attended

    if total_held > 0:
        attendance_percentage = round((total_attended / total_held) * 100, 2)
    else:
        attendance_percentage = 0

    # AVERAGE MARKS
    avg_marks = marks.aggregate(avg=Avg("marks"))["avg"] or 0

    # CHART DATA
    subject_names = []
    subject_marks = []

    for m in marks:
        subject_names.append(m.subject.name)
        subject_marks.append(m.marks)

    context = {
        "student": student,
        "marks": marks,
        "attendance_percentage": attendance_percentage,
        "average_marks": round(avg_marks, 2),
        "subject_names": subject_names,
        "subject_marks": subject_marks,
    }

    return render(request, "student_performance.html", context)

# =================================================
# ADMIN DASHBOARD 
# =================================================
@login_required
@user_passes_test(is_admin)
def admin_dashboard(request):

    # ===============================
    # BASIC COUNTS
    # ===============================
    students_count = Student.objects.count()
    teachers_count = Teacher.objects.count()
    classes_count = ClassRoom.objects.count()
    users_count = User.objects.count()

    # ===============================
    # RECENT ACTIVITY
    # ===============================
    recent_activities = Activity.objects.order_by('-created_at')[:5]    

    # ===============================
    # FINANCE
    # ===============================
    total_collected = Fee.objects.filter(paid=True).aggregate(
        total=Sum('amount')
    )['total'] or 0

    total_pending = Fee.objects.filter(paid=False).aggregate(
        total=Sum('amount')
    )['total'] or 0

    # ===============================
    # MONTHLY REVENUE
    # ===============================
    monthly_labels = []
    monthly_data = []

    current_month = now().month
    current_year = now().year

    for i in range(5, -1, -1):
        month = current_month - i
        year = current_year

        if month <= 0:
            month += 12
            year -= 1

        total = Fee.objects.filter(
            paid=True,
            date_paid__month=month,
            date_paid__year=year
        ).aggregate(total=Sum('amount'))['total'] or 0

        monthly_labels.append(datetime(year, month, 1).strftime('%b'))
        monthly_data.append(float(total))

    # ===============================
    # STUDENTS PER CLASS
    # ===============================
    classes_qs = ClassRoom.objects.annotate(
        total_students=Count('student')
    )

    class_labels = [str(c) for c in classes_qs]
    class_data = [c.total_students for c in classes_qs]

    # ===============================
    # TEACHERS PER SUBJECT
    # ===============================
    subjects_qs = Subject.objects.annotate(
        total_teachers=Count('teacher')
    )

    subject_labels = [s.name for s in subjects_qs]
    subject_data = [s.total_teachers for s in subjects_qs]

    # ===============================
    # LEAVE ANALYTICS ✅ (FIXED POSITION)
    # ===============================
    total_leaves = Leave.objects.count()

    approved_leaves = Leave.objects.filter(status='APPROVED').count()
    rejected_leaves = Leave.objects.filter(status='REJECTED').count()
    pending_leaves = Leave.objects.filter(status='PENDING').count()
    cancelled_leaves = Leave.objects.filter(status='CANCELLED').count()

    leave_labels = ['Approved', 'Rejected', 'Pending', 'Cancelled']
    leave_data = [
        approved_leaves,
        rejected_leaves,
        pending_leaves,
        cancelled_leaves
    ]

    # ===============================
    # RENDER
    # ===============================
    return render(request, 'admin/dashboard.html', {
        'students': students_count,
        'teachers': teachers_count,
        'classes': classes_count,
        'users': users_count,

        'recent_activities': recent_activities,

        # Finance
        'total_collected': total_collected,
        'total_pending': total_pending,
        'monthly_labels': monthly_labels,
        'monthly_data': monthly_data,

        # Charts
        'class_labels': class_labels,
        'class_data': class_data,
        'subject_labels': subject_labels,
        'subject_data': subject_data,

        # Leave Analytics
        'leave_total': total_leaves,
        'leave_labels': leave_labels,
        'leave_data': leave_data,
    })


@login_required
@user_passes_test(is_admin)
def leave_calendar(request):
    return render(request, "admin/leave_calendar.html")


# API to send leave data
@login_required
@user_passes_test(is_admin)
def leave_events(request):

    leaves = Leave.objects.all()

    events = []

    for leave in leaves:
        color = "#ffc107"  # pending

        if leave.status == "APPROVED":
            color = "#198754"
        elif leave.status == "REJECTED":
            color = "#dc3545"
        elif leave.status == "CANCELLED":
            color = "#6c757d"

        events.append({
            "title": f"{leave.full_name} ({leave.role})",
            "start": str(leave.start_date),
            "end": str(leave.end_date),
            "color": color,
        })

    return JsonResponse(events, safe=False)


@login_required
@user_passes_test(is_admin)
def admin_fees(request):
    fees = Fee.objects.select_related('student').order_by('-created_at')
    total_collected = Fee.objects.filter(paid=True).aggregate(
        total=Sum('amount')
    )['total'] or 0

    total_pending = Fee.objects.filter(paid=False).aggregate(
        total=Sum('amount')
    )['total'] or 0

    return render(request, 'admin/fees.html', {
        'fees': fees,
        'total_collected': total_collected,
        'total_pending': total_pending
    })


@login_required
@user_passes_test(is_admin)
def admin_reports(request):

    students = Student.objects.count()
    teachers = Teacher.objects.count()

    avg_marks = Marks.objects.aggregate(avg=Avg('marks'))['avg'] or 0

    attendance = Attendance.objects.aggregate(
        total=Sum('lectures_held'),
        attended=Sum('lectures_attended')
    )

    attendance_percentage = 0
    if attendance['total']:
        attendance_percentage = round(
            (attendance['attended'] / attendance['total']) * 100, 2
        )

    return render(request, 'admin/reports.html', {
        'students': students,
        'teachers': teachers,
        'avg_marks': round(avg_marks, 2),
        'attendance_percentage': attendance_percentage
    })


@login_required
@user_passes_test(is_student)
def create_payment_session(request):

    stripe.api_key = settings.STRIPE_SECRET_KEY

    student = Student.objects.get(user=request.user)

    fee = Fee.objects.filter(student=student, paid=False).first()

    if not fee:
        return JsonResponse({"error": "No pending fees"})

    session = stripe.checkout.Session.create(
        payment_method_types=['card'],
        line_items=[{
            'price_data': {
                'currency': 'usd',
                'product_data': {
                    'name': 'School Fee Payment',
                },
                'unit_amount': int(fee.amount * 100),
            },
            'quantity': 1,
        }],
        mode='payment',
        success_url=request.build_absolute_uri('/payment-success/'),
        cancel_url=request.build_absolute_uri('/payment-cancel/'),
    )

    return JsonResponse({'id': session.id})

# ==============================
# PAYMENT SUCCESS
# ==============================
@login_required
def payment_success(request):

    student = Student.objects.get(user=request.user)

    fee = Fee.objects.filter(student=student, paid=False).first()

    if fee:
        fee.paid = True
        fee.date_paid = timezone.now().date()
        fee.save()

    Activity.objects.create(
    title="Fee Payment",
    description=f"{student.application.full_name} paid school fees"
)

    return render(request, "student/payment_success.html")


@login_required
def payment_cancel(request):
    return render(request, "student/payment_cancel.html")


# =================================================
# EVERYTHING BELOW IS EXACTLY YOUR ORIGINAL CODE
# (NOT MODIFIED)
# =================================================

@login_required
@user_passes_test(is_admin)
def admin_students(request):
    return render(request, 'admin/add_students.html', {
        'students': Student.objects.select_related(
            'classroom',
            'classroom__level',
            'classroom__stream'
        )
    })


@login_required
@user_passes_test(is_admin)
def admin_delete_student(request, student_id):
    student = get_object_or_404(Student, id=student_id)
    student.user.delete()
    return redirect('admin_students')


@login_required
@user_passes_test(is_admin)
def admin_teachers(request):
    return render(request, 'admin/teachers.html', {
        'teachers': Teacher.objects.all()
    })


@login_required
@user_passes_test(is_admin)
def admin_delete_teacher(request, teacher_id):
    teacher = get_object_or_404(Teacher, id=teacher_id)
    teacher.user.delete()
    return redirect('admin_teachers')


@login_required
@user_passes_test(is_admin)
def admin_subjects(request):
    return render(request, 'admin/subjects.html', {
        'subjects': Subject.objects.select_related('level', 'stream')
    })


@login_required
@user_passes_test(is_admin)
def admin_classes(request):
    return render(request, 'admin/classes.html', {
        'classes': ClassRoom.objects.select_related('level', 'stream')
    })
    

# =================================================
# STUDENT DASHBOARD
# =================================================
@login_required
@user_passes_test(is_student)
def student_dashboard(request):

    student = Student.objects.get(user=request.user)
    classroom = student.classroom

    # -------------------------------
    # SUBJECTS
    # -------------------------------
    if classroom and classroom.stream:
        subjects = Subject.objects.filter(
            level=classroom.level,
            stream=classroom.stream
        )
    else:
        subjects = Subject.objects.filter(level=classroom.level)

    # -------------------------------
    # MARKS
    # -------------------------------
    marks = Marks.objects.filter(
        student=student,
        subject__in=subjects
    ).select_related('subject')

    subject_names = [m.subject.name for m in marks]
    subject_marks = [m.marks for m in marks]

    # -------------------------------
    # ATTENDANCE RECORDS
    # -------------------------------
    attendance_records = Attendance.objects.filter(student=student)

    total_lectures = sum(a.lectures_held for a in attendance_records)
    attended_lectures = sum(a.lectures_attended for a in attendance_records)

    missed_lectures = total_lectures - attended_lectures

    # -------------------------------
    # OVERALL ATTENDANCE SYSTEM
    # -------------------------------

    attendance_percentage = 100

    if total_lectures > 0:
        penalty = missed_lectures * 1.5

        # if student misses many lectures in a day
        if missed_lectures >= 6:
            penalty = 5

        attendance_percentage -= penalty

        # recovery system
        if attendance_percentage < 60:
            reward_rate = 1
        else:
            reward_rate = 0.25

        attendance_percentage += attended_lectures * reward_rate

    if attendance_percentage > 100:
        attendance_percentage = 100

    if attendance_percentage < 0:
        attendance_percentage = 0

    attendance_percentage = round(attendance_percentage, 2)

    # -------------------------------
    # SUBJECT ATTENDANCE
    # -------------------------------
    subject_attendance = []

    for subject in subjects:

        records = Attendance.objects.filter(
            student=student,
            subject=subject
        )

        total = sum(r.lectures_held for r in records)
        attended = sum(r.lectures_attended for r in records)

        missed = total - attended

        percentage = 100

        if total > 0:

            penalty = missed * 1.5

            if missed >= 6:
                penalty = 5

            percentage -= penalty

            if percentage < 60:
                reward_rate = 1
            else:
                reward_rate = 0.25

            percentage += attended * reward_rate

        if percentage > 100:
            percentage = 100

        if percentage < 0:
            percentage = 0

        subject_attendance.append({
            "subject": subject,
            "total": total,
            "attended": attended,
            "percentage": round(percentage, 2)
        })

    # -------------------------------
    # ATTENDANCE CHART DATA
    # -------------------------------
    attendance_labels = [a["subject"].name for a in subject_attendance]
    attendance_data = [a["percentage"] for a in subject_attendance]

    # -------------------------------
    # NOTICES
    # -------------------------------
    notices = Notice.objects.filter(Q(target_role='ALL') | Q(target_role='STUDENT'))

    # -------------------------------
    # TIMETABLE
    # -------------------------------
    timetable = Timetable.objects.filter(
        classroom=student.classroom
    ).order_by('day', 'start_time')

    # -------------------------------
    # STUDY MATERIALS (ADD THIS)
    # -------------------------------
    materials = StudyMaterial.objects.filter(
    subject__in=subjects)

    # -------------------------------
    # RENDER DASHBOARD
    # -------------------------------
    return render(request, 'student/dashboard.html', {

        'student': student,
        'subjects': subjects,
        'marks': marks,

        'attendance_percentage': attendance_percentage,

        'subject_names': subject_names,
        'subject_marks': subject_marks,

        'subject_attendance': subject_attendance,

        'attendance_labels': attendance_labels,
        'attendance_data': attendance_data,

        'notices': notices,
        'timetable': timetable,
        'materials': materials,

        'stripe_public_key': settings.STRIPE_PUBLIC_KEY
    })

# =================================================
# STUDENT PROFILE
# =================================================
@login_required
@user_passes_test(is_student)
def student_profile(request):
    student = Student.objects.get(user=request.user)
    return render(request, 'student/profile.html', {'student': student})


# =================================================
# TEACHER DASHBOARD
# =================================================
@login_required
@user_passes_test(is_teacher)
def teacher_dashboard(request):

    teacher = Teacher.objects.get(user=request.user)
    subjects = teacher.subjects.select_related('level', 'stream')

    # -------------------------------
    # GROUP SUBJECTS
    # -------------------------------
    grouped = {}
    for subject in subjects:
        key = f"{subject.level}"
        if subject.stream:
            key = f"{subject.level} - {subject.stream}"
        grouped.setdefault(key, []).append(subject)

    # -------------------------------
    # FIX NOTICE (IMPORTANT)
    # -------------------------------
    teacher_notices = Notice.objects.filter(Q(target_role='ALL') | Q(target_role='TEACHER'))

    # -------------------------------
    # STUDY MATERIAL UPLOAD
    # -------------------------------
    if request.method == "POST":
      file = request.FILES.get('material')
      subject_id = request.POST.get('subject_id')
      title = request.POST.get('title')
      material_type = request.POST.get('material_type')

      if file and subject_id and title and material_type:
        subject = Subject.objects.get(id=subject_id)

        StudyMaterial.objects.create(
            teacher=teacher,
            subject=subject,
            title=title,
            material_type=material_type,
            file=file
        )

        Notification.objects.create(
            title="New Notice",
            message=title,
            for_student=True,
            for_admin=True
        )

        messages.success(request, "Material uploaded successfully!")
        return redirect('teacher_dashboard')
    
    materials = StudyMaterial.objects.filter(teacher=teacher)

    # -------------------------------
    # TIMETABLE
    # -------------------------------
    teacher_timetable = Timetable.objects.filter(
        teacher=teacher
    ).order_by('day', 'start_time')

    # -------------------------------
    # WEEKLY SCHEDULE
    # -------------------------------
    from collections import defaultdict

    slots = defaultdict(lambda: {
        'mon': None, 'tue': None, 'wed': None, 'thu': None, 'fri': None
    })

    for t in teacher_timetable:
        key = f"{t.start_time}-{t.end_time}"

        if t.day == "Monday":
            slots[key]['mon'] = t
        elif t.day == "Tuesday":
            slots[key]['tue'] = t
        elif t.day == "Wednesday":
            slots[key]['wed'] = t
        elif t.day == "Thursday":
            slots[key]['thu'] = t
        elif t.day == "Friday":
            slots[key]['fri'] = t

    timetable_slots = [
        {'time': k, **v} for k, v in slots.items()
    ]

    return render(request, 'teacher/dashboard.html', {
        'teacher': teacher,
        'subjects_by_group': grouped,
        'teacher_notices': teacher_notices,
        'teacher_timetable': teacher_timetable,
        'timetable_slots': timetable_slots,
        'materials': materials
    })


@login_required
@user_passes_test(is_teacher)
def teacher_create_result(request):
    students = Student.objects.all()
    if request.method == "POST":
        student_id = request.POST.get("student")
        term = request.POST.get("term")
        student = Student.objects.get(id=student_id)

        # ✅ FINAL LOGIC
        if term == "FINAL":
            marks = Marks.objects.filter(student=student)
        else:
            marks = Marks.objects.filter(student=student, term=term)

        total = sum(m.marks for m in marks)
        count = marks.count()

        percentage = (total / (count * 100)) * 100 if count > 0 else 0

        # PASS MARK = 50%
        if percentage >= 85:
            grade = "A"
        elif percentage >= 70:
            grade = "B"
        elif percentage >= 60:
            grade = "C"
        elif percentage >= 50:
            grade = "D"
        else:
            grade = "F (Fail)"

        Result.objects.update_or_create(
            student=student,
            term=term,
            defaults={
                'total_marks': total,
                'percentage': round(percentage, 2),
                'grade': grade,
                'created_by': request.user
            }
        )

        messages.success(request, f"{term} result generated successfully")
        return redirect('teacher_dashboard')

    return render(request, 'teacher/create_result.html', {
        'students': students
    })


# =================================================
# TEACHER CREATE NOTICE
# =================================================
@login_required
@user_passes_test(is_teacher)
def teacher_create_notice(request):

    if request.method == 'POST':

        title = request.POST.get('title')
        message = request.POST.get('message')

        if title and message:

            # ✅ Create Notice
            Notice.objects.create(
                title=title,
                message=message,
                target_role='STUDENT',
                created_by=request.user
            )

            # ✅ Create Notification (FIXED)
            Notification.objects.create(
                title="New Notice",
                message=title,  # now title is defined ✅
                for_student=True,
                for_admin=True
            )

            messages.success(request, "Notice posted successfully.")
            return redirect('teacher_dashboard')

        messages.error(request, "All fields are required.")

    return render(request, 'teacher/create_notice.html')


@login_required
@user_passes_test(is_teacher)
def teacher_notice_detail(request, id):
    notice = get_object_or_404(Notice, id=id)
    return render(request, 'teacher/notice_detail.html', {'notice': notice})


# =============================
# CHECK NEW NOTICE (AJAX)
# =============================
def check_new_notice(request):

    if not request.user.is_authenticated:
        return JsonResponse({})

    # 👇 FILTER BASED ON ROLE
    if request.user.is_superuser:
        notices = Notice.objects.all()

    elif Teacher.objects.filter(user=request.user).exists():
        notices = Notice.objects.filter(
            Q(target_role='ALL') | Q(target_role='TEACHER')
        )

    elif Student.objects.filter(user=request.user).exists():
        notices = Notice.objects.filter(
            Q(target_role='ALL') | Q(target_role='STUDENT')
        )

    else:
        notices = Notice.objects.none()

    latest_notice = notices.order_by('-created_at').first()

    if latest_notice:
        return JsonResponse({
            "id": latest_notice.id,
            "title": latest_notice.title
        })

    return JsonResponse({})


def post_notice(request):
    if request.method == "POST":
        title = request.POST.get("title")
        message = request.POST.get("message")

        # Create notification for all users
        Notification.objects.create(
            title=title,
            message=message,
            for_admin=True,
            for_teacher=True,
            for_student=True
        )

        return redirect('dashboard')
   
    
@login_required
def get_notifications(request):

    user = request.user

    if user.is_superuser:
        qs = Notification.objects.filter(for_admin=True, is_read=False)
    elif Teacher.objects.filter(user=user).exists():
        qs = Notification.objects.filter(for_teacher=True, is_read=False)
    else:
        qs = Notification.objects.filter(for_student=True, is_read=False)

    data = list(qs.values('id', 'title', 'message'))

    # mark as read AFTER sending
    qs.update(is_read=True)

    return JsonResponse({
        "notifications": data
    })



# =================================================
# TEACHER SUBJECT STUDENTS
# =================================================
@login_required
@user_passes_test(is_teacher)
def teacher_subject_students(request, subject_id):

    teacher = Teacher.objects.get(user=request.user)
    subject = get_object_or_404(Subject, id=subject_id)

    if subject not in teacher.subjects.all():
        raise PermissionDenied

    students = Student.objects.filter(
        classroom__level=subject.level,
        classroom__stream=subject.stream
    )

    return render(request, 'teacher/subject_students.html', {
        'subject': subject,
        'students': students
    })


# =================================================
# BULK ATTENDANCE (FINAL FIX)
# =================================================
@login_required
@user_passes_test(is_teacher)
def teacher_bulk_attendance(request, subject_id):

    teacher = Teacher.objects.get(user=request.user)
    subject = get_object_or_404(Subject, id=subject_id)

    if subject not in teacher.subjects.all():
        raise PermissionDenied

    students = Student.objects.filter(
        classroom__level=subject.level,
        classroom__stream=subject.stream
    )

    today = timezone.now().date()

    if request.method == 'POST':

        lectures_held = int(request.POST.get('lectures_held'))

        for student in students:

            attended = request.POST.get(f'attended_{student.id}')

            # If checked → student attended all lectures
            if attended == "yes":
                lectures_attended = lectures_held
            else:
                lectures_attended = 0

            Attendance.objects.update_or_create(
                student=student,
                subject=subject,
                date=today,
                defaults={
                    'lectures_held': lectures_held,
                    'lectures_attended': lectures_attended
                }
            )
        Activity.objects.create(
            title="Attendance Submitted",
            description=f"{request.user.get_full_name()} recorded attendance for {subject.name}"
)
        messages.success(request, "Attendance recorded successfully.")
        return redirect('teacher_dashboard')

    return render(request, 'teacher/bulk_attendance.html', {
        'subject': subject,
        'students': students
    })


@login_required
@user_passes_test(is_teacher)
def teacher_weekly_timetable(request):

    teacher = Teacher.objects.get(user=request.user)

    teacher_timetable = Timetable.objects.filter(
        teacher=teacher
    ).order_by('day', 'start_time')

    from collections import defaultdict

    slots = defaultdict(lambda: {
        'mon': None, 'tue': None, 'wed': None, 'thu': None, 'fri': None
    })

    for t in teacher_timetable:
        key = f"{t.start_time}-{t.end_time}"

        if t.day == "Monday":
            slots[key]['mon'] = t
        elif t.day == "Tuesday":
            slots[key]['tue'] = t
        elif t.day == "Wednesday":
            slots[key]['wed'] = t
        elif t.day == "Thursday":
            slots[key]['thu'] = t
        elif t.day == "Friday":
            slots[key]['fri'] = t

    timetable_slots = [
        {'time': k, **v} for k, v in slots.items()
    ]

    return render(request, 'teacher/weekly_timetable.html', {
        'timetable_slots': timetable_slots
    })


# =================================================
# STUDENT ATTENDANCE HISTORY
# =================================================
@login_required
@user_passes_test(is_student)
def student_attendance_history(request):
    student = Student.objects.get(user=request.user)

    attendance_records = Attendance.objects.filter(
        student=student
    ).order_by('-date')

    return render(
        request,
        'student/attendance_history.html',
        {
            'student': student,
            'attendance_records': attendance_records
        }
    )



# =================================================
# BULK MARKS
# =================================================
@login_required
@user_passes_test(is_teacher)
def teacher_bulk_marks(request, subject_id):

    teacher = Teacher.objects.get(user=request.user)
    subject = get_object_or_404(Subject, id=subject_id)

    if subject not in teacher.subjects.all():
        raise PermissionDenied

    students = Student.objects.filter(
        classroom__level=subject.level,
        classroom__stream=subject.stream
    )

    if request.method == 'POST':

        term = request.POST.get('term')

        for student in students:
            marks_value = request.POST.get(f'marks_{student.id}')

            if marks_value:
                Marks.objects.update_or_create(
                    student=student,
                    subject=subject,
                    term=term,
                    defaults={'marks': marks_value}
                )

        messages.success(request, "Marks saved successfully.")
        return redirect('teacher_dashboard')

    return render(request, 'teacher/bulk_marks.html', {
        'subject': subject,
        'students': students
    })


# =================================================
# REPORTS
# =================================================
@login_required
@user_passes_test(is_student)
def student_marks_report(request):
    student = Student.objects.get(user=request.user)
    marks = Marks.objects.filter(student=student)
    return render(request, 'student/marks_report.html', {'marks': marks})


@login_required
@user_passes_test(is_student)
def student_subjects(request):
    student = Student.objects.get(user=request.user)
    subjects = Subject.objects.filter(
        level=student.classroom.level,
        stream=student.classroom.stream
    )
    return render(request, 'student/subjects.html', {'subjects': subjects})


@login_required
@user_passes_test(is_student)
def student_timetable(request):
    student = Student.objects.get(user=request.user)
    timetable = Timetable.objects.filter(classroom=student.classroom)
    return render(request, 'student/timetable.html', {'timetable': timetable})


@login_required
@user_passes_test(is_student)
def student_notices(request):
    notices = Notice.objects.filter(Q(target_role='ALL') | Q(target_role='STUDENT')).order_by('-created_at')
    return render(request, 'student/notices.html', {'notices': notices})


@login_required
@user_passes_test(is_student)
def student_fees(request):
    student = Student.objects.get(user=request.user)
    fees = Fee.objects.filter(student=student)
    return render(request, 'student/fees.html', {'fees': fees})


@login_required
@user_passes_test(is_student)
def student_attendance_report(request):
    student = Student.objects.get(user=request.user)
    attendance = Attendance.objects.filter(student=student)
    return render(request, 'student/attendance_report.html', {'attendance': attendance})


@login_required
@user_passes_test(is_student)
def student_materials(request):
    student = Student.objects.get(user=request.user)

    classroom = student.classroom

    if classroom and classroom.stream:
        subjects = Subject.objects.filter(
            level=classroom.level,
            stream=classroom.stream
        )
    else:
        subjects = Subject.objects.filter(level=classroom.level)

    materials = StudyMaterial.objects.filter(subject__in=subjects)

    return render(request, 'student/materials.html', {
        'materials': materials
    })


@login_required
@user_passes_test(is_student)
def student_results(request):
    student = Student.objects.get(user=request.user)
    results = Result.objects.filter(student=student)

    return render(request, 'student/results.html', {
        'results': results
    })



@login_required
@user_passes_test(is_student)
def download_result_pdf(request, id):

    result = get_object_or_404(Result, id=id)
    student = result.student

    # =========================
    # SUBJECT MARKS
    # =========================
    if result.term == "FINAL":
        marks = Marks.objects.filter(student=student)
    else:
        marks = Marks.objects.filter(student=student, term=result.term)

    # =========================
    # DIGITAL SIGNATURE (HASH)
    # =========================
    signature_text = f"{student.id}-{result.term}-{result.total_marks}-{result.percentage}"
    digital_signature = hashlib.sha256(signature_text.encode()).hexdigest()[:12]

    # =========================
    # QR CODE GENERATION
    # =========================
    qr_data = f"""
    Student: {student.application.full_name}
    ID: {student.student_id}
    Term: {result.get_term_display()}
    Percentage: {result.percentage}%
    Verify Code: {digital_signature}
    """

    qr = qrcode.make(qr_data)
    qr_buffer = BytesIO()
    qr.save(qr_buffer)
    qr_buffer.seek(0)

    # =========================
    # PDF RESPONSE
    # =========================
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="result_{student.id}.pdf"'

    doc = SimpleDocTemplate(response, pagesize=A4)
    styles = getSampleStyleSheet()
    elements = []

    # =========================
    # LOGO
    # =========================
    try:
        logo = Image("static/images/school_logo.png", width=60, height=60)
        elements.append(logo)
    except:
        pass

    # =========================
    # HEADER
    # =========================
    elements.append(Paragraph("<b>Schoolname Secondary School</b>", styles['Title']))
    elements.append(Paragraph("Official Academic Result Report", styles['Normal']))
    elements.append(Spacer(1, 20))

    # =========================
    # STUDENT INFO
    # =========================
    student_info = [
        ["Student Name", student.application.full_name],
        ["Student ID", student.student_id],
        ["Class", str(student.classroom)],
        ["Term", result.get_term_display()],
    ]

    table = Table(student_info, colWidths=[150, 300])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (0,-1), colors.lightgrey),
        ('GRID', (0,0), (-1,-1), 0.5, colors.black),
    ]))

    elements.append(table)
    elements.append(Spacer(1, 20))

    # =========================
    # SUBJECT TABLE
    # =========================
    data = [["Subject", "Marks"]]

    for m in marks:
        data.append([m.subject.name, m.marks])

    subject_table = Table(data, colWidths=[300, 150])
    subject_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.darkblue),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('GRID', (0,0), (-1,-1), 0.5, colors.black),
        ('ALIGN', (1,1), (-1,-1), 'CENTER'),
    ]))

    elements.append(subject_table)
    elements.append(Spacer(1, 20))

    # =========================
    # SUMMARY
    # =========================
    summary = [
        ["Total Marks", result.total_marks],
        ["Percentage", f"{result.percentage}%"],
        ["Grade", result.grade],
    ]

    summary_table = Table(summary, colWidths=[200, 200])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (0,-1), colors.lightgrey),
        ('GRID', (0,0), (-1,-1), 0.5, colors.black),
    ]))

    elements.append(summary_table)
    elements.append(Spacer(1, 20))

    # =========================
    # QR CODE
    # =========================
    qr_image = Image(qr_buffer, width=100, height=100)
    elements.append(qr_image)

    elements.append(Paragraph(
        f"Verification Code: <b>{digital_signature}</b>",
        styles['Normal']
    ))

    elements.append(Spacer(1, 20))

    # =========================
    # MESSAGE
    # =========================
    elements.append(Paragraph(
        "This academic report is issued as an official record of performance. "
        "Any alteration invalidates this document.",
        styles['Normal']
    ))

    elements.append(Spacer(1, 30))

    # =========================
    # SIGNATURE + STAMP
    # =========================
    try:
        stamp = Image("static/images/school_stamp.png", width=80, height=80)
    except:
        stamp = ""

    sign_table = Table([
        ["Class Teacher", "Principal"],
        ["______________", "______________"],
        ["", stamp]
    ], colWidths=[250, 250])

    elements.append(sign_table)

    # =========================
    # WATERMARK FUNCTION
    # =========================
    def add_watermark(canvas_obj, doc):
        canvas_obj.saveState()
        canvas_obj.setFont("Helvetica-Bold", 50)
        canvas_obj.setFillColorRGB(0.9, 0.9, 0.9)

        canvas_obj.rotate(45)
        canvas_obj.drawCentredString(300, 200, "OFFICIAL")

        canvas_obj.restoreState()

    # =========================
    # BUILD PDF
    # =========================
    doc.build(elements, onFirstPage=add_watermark, onLaterPages=add_watermark)

    return response



@login_required
@user_passes_test(is_teacher)
def delete_mark(request, id):

    mark = get_object_or_404(Marks, id=id)

    if mark.subject not in Teacher.objects.get(user=request.user).subjects.all():
        raise PermissionDenied

    mark.delete()

    messages.success(request, "Mark deleted")

    return redirect('teacher_dashboard')


@login_required
@user_passes_test(is_teacher)
def edit_mark(request, id):

    mark = get_object_or_404(Marks, id=id)

    if request.method == "POST":
        mark.marks = request.POST.get('marks')
        mark.save()

        messages.success(request, "Mark updated")
        return redirect('teacher_dashboard')

    return render(request, 'teacher/edit_mark.html', {'mark': mark})


@login_required
@user_passes_test(is_teacher)
def teacher_marks_report(request, subject_id):

    teacher = Teacher.objects.get(user=request.user)
    subject = get_object_or_404(Subject, id=subject_id)

    if subject not in teacher.subjects.all():
        raise PermissionDenied

    marks = Marks.objects.filter(subject=subject).select_related('student')

    return render(request, 'teacher/marks_report.html', {
        'subject': subject,
        'marks': marks
    })


@login_required
@user_passes_test(is_teacher)
def teacher_attendance_report(request, subject_id):

    teacher = Teacher.objects.get(user=request.user)
    subject = get_object_or_404(Subject, id=subject_id)

    if subject not in teacher.subjects.all():
        raise PermissionDenied

    attendance = Attendance.objects.filter(
        student__classroom__level=subject.level,
        student__classroom__stream=subject.stream
    )

    return render(request, 'teacher/attendance_report.html', {
        'subject': subject,
        'attendance': attendance
    })


@login_required
@user_passes_test(is_teacher)
def teacher_subjects(request):
    teacher = Teacher.objects.get(user=request.user)
    return render(request, 'teacher/teacher_subjects.html', {
        'subjects': teacher.subjects.all()
    })


@login_required
@user_passes_test(is_teacher)
def teacher_students(request):

    teacher = Teacher.objects.get(user=request.user)

    query = request.GET.get('q', '').strip()

    students = Student.objects.filter(
        classroom__level__in=teacher.subjects.values_list('level', flat=True)
    )

    # 🔍 APPLY SEARCH FILTER
    if query:
        students = students.filter(
            Q(student_id__icontains=query) |
            Q(user__username__icontains=query) |
            Q(user__first_name__icontains=query) |
            Q(user__last_name__icontains=query) |
            Q(application__full_name__icontains=query)   # ✅ VERY IMPORTANT
        )

    return render(request, 'teacher/teacher_students.html', {
        'students': students,
        'query': query
    })


@login_required
@user_passes_test(is_teacher)
def teacher_materials(request):
    teacher = Teacher.objects.get(user=request.user)

    materials = StudyMaterial.objects.filter(teacher=teacher)

    return render(request, 'teacher/teacher_materials.html', {
        'materials': materials
    })


@login_required
@user_passes_test(is_teacher)
def teacher_performance(request):
    teacher = Teacher.objects.get(user=request.user)

    subjects = teacher.subjects.all()

    subject_labels = []
    subject_averages = []

    for subject in subjects:
        avg = Marks.objects.filter(subject=subject).aggregate(avg=Avg('marks'))['avg'] or 0
        subject_labels.append(subject.name)
        subject_averages.append(avg)

    return render(request, 'teacher/teacher_performance.html', {
        'subject_labels': subject_labels,
        'subject_averages': subject_averages
    })


@login_required
@user_passes_test(is_teacher)
def teacher_notices(request):

    notices = Notice.objects.filter(
        Q(target_role='ALL') | Q(target_role='TEACHER')
    ).order_by('-created_at')

    return render(request, 'teacher/notices.html', {
        'notices': notices
    })


# =================================================
# NOTICE DETAIL
# =================================================
@login_required
def notice_detail(request, id):
    notice = get_object_or_404(Notice, id=id)

    NoticeRead.objects.update_or_create(
        user=request.user,
        notice=notice,
        defaults={'is_read': True}
    )

    return render(request, 'notice_detail.html', {'notice': notice})


@login_required
@user_passes_test(is_teacher)
def teacher_delete_material(request, id):
    material = get_object_or_404(StudyMaterial, id=id, teacher__user=request.user)
    material.delete()
    messages.success(request, "Material deleted successfully")
    return redirect('teacher_dashboard')


@login_required
@user_passes_test(is_teacher)
def teacher_edit_material(request, id):

    material = get_object_or_404(StudyMaterial, id=id, teacher__user=request.user)

    if request.method == "POST":
        material.title = request.POST.get('title')
        material.save()
        messages.success(request, "Material updated")
        return redirect('teacher_dashboard')

    return render(request, 'teacher/edit_material.html', {'material': material})


# =================================================
# LEAVE APPLICATIONS
# =================================================
@login_required
@user_passes_test(is_student)
def student_apply_leave(request):

    student = Student.objects.get(user=request.user)

    if request.method == "POST":

        Leave.objects.create(
            user=request.user,
            role='STUDENT',
            full_name=student.application.full_name,
            enrollment_number=student.student_id,
            class_level=str(student.classroom.level),
            section=student.classroom.section,
            stream=str(student.classroom.stream) if student.classroom.stream else "",
            reason=request.POST.get("reason"),
            start_date=request.POST.get("start_date"),
            end_date=request.POST.get("end_date"),
        )

        Notification.objects.create(
          title="New Leave Request",
          message=f"{request.user.username} applied for leave",
          for_admin=True
        )

        messages.success(request, "Leave applied successfully!")
        return redirect('student_leave')

    return render(request, "student/apply_leave.html")


@login_required
@user_passes_test(is_student)
def student_leave(request):

    leaves = Leave.objects.filter(user=request.user, is_cancelled=False).order_by('-created_at')

    return render(request, "student/leave.html", {
        "leaves": leaves
    })


@login_required
@user_passes_test(is_student)
def student_edit_leave(request, id):

    leave = get_object_or_404(Leave, id=id, user=request.user)

    # ❌ Block editing if approved/rejected
    if leave.status != "PENDING":
        messages.error(request, "You cannot edit this leave anymore.")
        return redirect('student_leave')

    if request.method == "POST":
        leave.full_name = request.POST.get("full_name")
        leave.enrollment_number = request.POST.get("enrollment_number")
        leave.class_level = request.POST.get("class_level")
        leave.section = request.POST.get("section")
        leave.stream = request.POST.get("stream")
        leave.reason = request.POST.get("reason")
        leave.start_date = request.POST.get("start_date")
        leave.end_date = request.POST.get("end_date")
        leave.save()

        messages.success(request, "Leave updated successfully!")
        return redirect('student_leave')

    return render(request, "student/edit_leave.html", {
        "leave": leave
    })


def student_cancel_leave(request, id):
    leave = get_object_or_404(Leave, id=id, user=request.user)

    if leave.status != "PENDING":
        messages.error(request, "You can only cancel pending leave.")
        return redirect('student_leave')

    leave.is_cancelled = True
    leave.save()

    messages.success(request, "Leave cancelled successfully.")
    return redirect('student_leave')


@login_required
@user_passes_test(is_teacher)
def teacher_leave(request):

    leaves = Leave.objects.filter(user=request.user, is_cancelled=False).order_by('-created_at')

    return render(request, "teacher/leave.html", {
        "leaves": leaves
    })

@login_required
@user_passes_test(is_teacher)
def teacher_apply_leave(request):

    teacher = Teacher.objects.get(user=request.user)

    if request.method == "POST":

        Leave.objects.create(
            user=request.user,
            role='TEACHER',

            full_name=teacher.user.get_full_name(),
            enrollment_number=teacher.teacher_id,

            teacher_id=teacher.teacher_id,
            classes_teaching=", ".join(
                [str(s.level) for s in teacher.subjects.all()]
            ),

            reason=request.POST.get("reason"),
            start_date=request.POST.get("start_date"),
            end_date=request.POST.get("end_date"),
        )

        Notification.objects.create(
           title="New Leave Request",
           message=f"{request.user.username} applied for leave",
           for_admin=True
        )

        messages.success(request, "Leave applied successfully!")
        return redirect('teacher_leave')

    return render(request, "teacher/apply_leave.html")


@login_required
@user_passes_test(is_teacher)
def teacher_edit_leave(request, id):

    leave = get_object_or_404(Leave, id=id, user=request.user)

    if leave.status != "PENDING":
        messages.error(request, "You cannot edit this leave anymore.")
        return redirect('teacher_leave')

    if request.method == "POST":

        classes = request.POST.getlist("classes_teaching")
        sections = request.POST.getlist("sections")
        streams = request.POST.getlist("streams")

        leave.full_name = request.POST.get("full_name")
        leave.teacher_id = request.POST.get("teacher_id")
        leave.enrollment_number = request.POST.get("teacher_id")

        leave.classes_teaching = ", ".join(classes)
        leave.class_level = ", ".join(classes)
        leave.section = ", ".join(sections)
        leave.stream = ", ".join(streams)

        leave.reason = request.POST.get("reason")
        leave.start_date = request.POST.get("start_date")
        leave.end_date = request.POST.get("end_date")

        leave.save()

        messages.success(request, "Leave updated successfully!")
        return redirect('teacher_leave')

    return render(request, "teacher/edit_leave.html", {
        "leave": leave
    })

def teacher_cancel_leave(request, id):
    leave = get_object_or_404(Leave, id=id, user=request.user)

    if leave.status != "PENDING":
        messages.error(request, "You can only cancel pending leave.")
        return redirect('teacher_leave')

    leave.is_cancelled = True
    leave.save()

    messages.success(request, "Leave cancelled successfully.")
    return redirect('teacher_leave')



# =================================================
# CUSTOM 403
# =================================================
def custom_403_view(request, exception=None):
    return render(request, '403.html', status=403)
