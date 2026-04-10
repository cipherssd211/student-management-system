from django.urls import path 
from . import views
from django.contrib.auth import views as auth_views

urlpatterns = [

    # =====================
    # AUTH
    # =====================
    path('', views.user_login, name='login'),
    path('login/', views.user_login, name='login'),
    path('logout/', views.user_logout, name='logout'),

    # =====================
    # ADMIN
    # =====================
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),

    path('admin-panel/students/', views.admin_students, name='admin_students'),
    path('admin-panel/teachers/', views.admin_teachers, name='admin_teachers'),
    path('admin-panel/classes/', views.admin_classes, name='admin_classes'),
    path('admin-panel/subjects/', views.admin_subjects, name='admin_subjects'),
    path('admin-panel/fees/', views.admin_fees, name='admin_fees'),
    path('admin-panel/reports/', views.admin_reports, name='admin_reports'),
    path('leave-calendar/', views.leave_calendar, name='leave_calendar'),
    path('leave-events/', views.leave_events, name='leave_events'),
    path('teacher/material/delete/<int:id>/', views.teacher_delete_material, name='teacher_delete_material'),
    path('admin-panel/student/delete/<int:student_id>/', views.admin_delete_student, name='admin_delete_student'),
    path('admin-panel/teacher/delete/<int:teacher_id>/', views.admin_delete_teacher, name='admin_delete_teacher'),

    # =====================
    # STUDENT
    # =====================
    path('student/dashboard/', views.student_dashboard, name='student_dashboard'),
    path('student/profile/', views.student_profile, name='student_profile'),
    path('student/marks/', views.student_marks_report, name='student_marks'),
    path('student/attendance/', views.student_attendance_report, name='student_attendance'),
    path('student/attendance/history/', views.student_attendance_history, name='student_attendance_history'),
    path('student/marks-report/', views.student_marks_report, name='student_marks_report'),
    path('student/subjects/', views.student_subjects, name='student_subjects'),
    path('student/timetable/', views.student_timetable, name='student_timetable'),
    path('student/fees/', views.student_fees, name='student_fees'),
    path('student/notices/', views.student_notices, name='student_notices'),
    path('student/materials/', views.student_materials, name='student_materials'),
    path('student/results/', views.student_results, name='student_results'),
    path('student/result/pdf/<int:id>/', views.download_result_pdf, name='download_result_pdf'),

    # =====================
    # STRIPE PAYMENTS
    # =====================
    path('create-payment-session/', views.create_payment_session, name='create_payment_session'),
    path('payment-success/', views.payment_success, name='payment_success'),

    # Optional cancel page
    path('payment-cancel/', views.payment_cancel, name='payment_cancel'),

    # =====================
    # TEACHER
    # =====================
    path('teacher/dashboard/', views.teacher_dashboard, name='teacher_dashboard'),
    path('teacher/notices/', views.teacher_notices, name='teacher_notices'),
    path('teacher/notices/create/', views.teacher_create_notice, name='teacher_create_notice'),
    path('teacher/subject/<int:subject_id>/', views.teacher_subject_students, name='teacher_subject_students'),
    path('teacher/subject/<int:subject_id>/marks/bulk/', views.teacher_bulk_marks, name='teacher_bulk_marks'),
    path('teacher/attendance/bulk/<int:subject_id>/', views.teacher_bulk_attendance, name='teacher_bulk_attendance'),
    path('teacher/subject/<int:subject_id>/marks-report/', views.teacher_marks_report, name='teacher_marks_report'),
    path('teacher/weekly-timetable/', views.teacher_weekly_timetable, name='teacher_weekly_timetable'),
    path('teacher/subject/<int:subject_id>/attendance-report/', views.teacher_attendance_report, name='teacher_attendance_report'),
    path('teacher/subjects/', views.teacher_subjects, name='teacher_subjects'),
    path('teacher/students/', views.teacher_students, name='teacher_students'),
    path('teacher/materials/', views.teacher_materials, name='teacher_materials'),
    path('teacher/performance/', views.teacher_performance, name='teacher_performance'),
    path('teacher/result/create/', views.teacher_create_result, name='teacher_create_result'),


    path('forgot-password/',views.forgot_password,name='forgot_password'),
    path('help/',views.help_page,name='help_page'),


     path('password-reset/',
        auth_views.PasswordResetView.as_view(
            template_name='password_reset.html'
        ),
        name='password_reset'),

    path('password-reset/done/',
        auth_views.PasswordResetDoneView.as_view(
            template_name='password_reset_done.html'
        ),
        name='password_reset_done'),

    path('password-reset-confirm/<uidb64>/<token>/',
        auth_views.PasswordResetConfirmView.as_view(
            template_name='password_reset_confirm.html'
        ),
        name='password_reset_confirm'),

    path('password-reset-complete/',
        auth_views.PasswordResetCompleteView.as_view(
            template_name='password_reset_complete.html'
        ),
        name='password_reset_complete'),


    path('notifications/', views.get_notifications, name='get_notifications'),
    path("check-notice/", views.check_new_notice, name="check_notice"),
    path('notice/<int:id>/', views.notice_detail, name='notice_detail'),

    path("student-performance/<int:student_id>/", views.student_performance, name="student_performance"),

    
    # STUDENT LEAVE
    path('student/leave/', views.student_leave, name='student_leave'),
    path('student/leave/apply/', views.student_apply_leave, name='student_apply_leave'),
    path('student/leave/edit/<int:id>/', views.student_edit_leave, name='student_edit_leave'),
    path('student/leave/cancel/<int:id>/', views.student_cancel_leave, name='student_cancel_leave'),

    # TEACHER LEAVE
    path('teacher/leave/', views.teacher_leave, name='teacher_leave'),
    path('teacher/leave/apply/', views.teacher_apply_leave, name='teacher_apply_leave'),
    path('teacher/leave/edit/<int:id>/', views.teacher_edit_leave, name='teacher_edit_leave'),
    path('teacher/leave/cancel/<int:id>/', views.teacher_cancel_leave, name='teacher_cancel_leave'),

    
]