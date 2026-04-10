from .models import AuditLog


def log_action(
    user,
    action,
    target_type,
    target_identifier,
    description=""
):
    """
    Creates an audit log entry.

    user              : User who performed the action (or None)
    action            : Action type (ENROLL, APPROVE_STUDENT, etc.)
    target_type       : Entity type (Student, Teacher, User, ClassRoom, Subject)
    target_identifier : Unique identifier (student_id, username, etc.)
    description       : Optional human-readable description
    """

    AuditLog.objects.create(
        performed_by=user,
        action=action,
        target_type=target_type,
        target_identifier=target_identifier,
        description=description
    )
