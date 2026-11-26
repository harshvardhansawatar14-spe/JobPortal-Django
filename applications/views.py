
import logging
from os.path import splitext

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from jobs.models import Job
from .models import Application, ApplicationStatusHistory


logger = logging.getLogger(__name__)


# =========================================================
# CONSTANTS
# =========================================================

ALLOWED_RESUME_EXTENSIONS = {".pdf", ".doc", ".docx"}

ALLOWED_APPLICATION_STATUSES = {
    value for value, label in Application.STATUS_CHOICES
}

MAX_RESUME_SIZE = 5 * 1024 * 1024
MIN_COVER_LETTER_LENGTH = 20


# =========================================================
# APPLY FOR JOB
# =========================================================

@login_required
def apply_job(request, job_id):

    job = get_object_or_404(
        Job,
        id=job_id,
        is_active=True
    )

    if request.user.role != "candidate":
        messages.error(
            request,
            "Only candidates can apply for jobs."
        )
        return redirect("job_detail", job_id=job.id)

    if job.application_deadline:
        if timezone.localdate() > job.application_deadline:
            messages.error(
                request,
                "Application deadline has expired."
            )
            return redirect("job_detail", job_id=job.id)

    already_applied = Application.objects.filter(
        candidate=request.user,
        job=job
    ).exists()

    if already_applied:
        messages.warning(
            request,
            "You have already applied for this job."
        )
        return redirect("job_detail", job_id=job.id)

    if request.method == "GET":
        return render(
            request,
            "applications/apply_job.html",
            {"job": job}
        )

    if request.method != "POST":
        messages.error(request, "Invalid request method.")
        return redirect("job_detail", job_id=job.id)

    cover_letter = request.POST.get(
        "cover_letter", ""
    ).strip()

    resume = request.FILES.get("resume")

    # Validate cover letter
    if len(cover_letter) < MIN_COVER_LETTER_LENGTH:
        messages.error(
            request,
            "Cover letter must contain at least 20 characters."
        )
        return render(request, "applications/apply_job.html", {
            "job": job,
            "cover_letter": cover_letter,
        })

    # Validate resume
    if not resume:
        messages.error(
            request,
            "Please upload your resume."
        )
        return render(request, "applications/apply_job.html", {
            "job": job,
            "cover_letter": cover_letter,
        })

    extension = splitext(resume.name)[1].lower()

    if extension not in ALLOWED_RESUME_EXTENSIONS:
        messages.error(
            request,
            "Upload PDF, DOC, or DOCX resume."
        )
        return render(request, "applications/apply_job.html", {
            "job": job,
            "cover_letter": cover_letter,
        })

    if resume.size > MAX_RESUME_SIZE:
        messages.error(
            request,
            "Resume size must not exceed 5 MB."
        )
        return render(request, "applications/apply_job.html", {
            "job": job,
            "cover_letter": cover_letter,
        })

    # Save application and initial history together
    try:
        with transaction.atomic():

            application = Application.objects.create(
                job=job,
                candidate=request.user,
                cover_letter=cover_letter,
                resume=resume,
            )

            ApplicationStatusHistory.objects.create(
                application=application,
                old_status="",
                new_status="applied",
                changed_by=request.user,
                remarks="Application submitted"
            )

    except IntegrityError:
        messages.warning(
            request,
            "You have already applied for this job."
        )
        return redirect("job_detail", job_id=job.id)

    messages.success(
        request,
        "Application submitted successfully!"
    )

    return redirect("my_applications")


# =========================================================
# MY APPLICATIONS
# =========================================================

@login_required
def my_applications(request):

    applications = (
        Application.objects
        .filter(candidate=request.user)
        .select_related("job")
        .order_by("-applied_at")
    )

    return render(
        request,
        "applications/my_applications.html",
        {
            "applications": applications,
        }
    )


# =========================================================
# JOB APPLICANTS
# =========================================================

@login_required
def job_applicants(request, job_id):

    if request.user.role != "recruiter":
        messages.error(
            request,
            "Only recruiters can view applicants."
        )
        return redirect("candidate_dashboard")

    job = get_object_or_404(
        Job,
        id=job_id,
        recruiter=request.user
    )

    applications = (
        Application.objects
        .filter(job=job)
        .select_related("candidate")
        .order_by("-applied_at")
    )

    return render(
        request,
        "applications/job_applicants.html",
        {
            "job": job,
            "applications": applications,
        }
    )


# =========================================================
# UPDATE APPLICATION STATUS
# =========================================================

@login_required
def update_application_status(request, application_id):

    if request.user.role != "recruiter":
        messages.error(
            request,
            "Only recruiters can update status."
        )
        return redirect("candidate_dashboard")

    if request.method != "POST":
        messages.error(
            request,
            "Invalid request method."
        )
        return redirect("recruiter_dashboard")

    application = get_object_or_404(
        Application.objects.select_related(
            "job",
            "candidate"
        ),
        id=application_id,
        job__recruiter=request.user
    )

    status_value = request.POST.get(
        "status", ""
    ).strip()

    if status_value not in ALLOWED_APPLICATION_STATUSES:
        messages.error(
            request,
            "Invalid application status."
        )
        return redirect(
            "job_applicants",
            job_id=application.job.id
        )

    old_status = application.status

    if old_status == status_value:
        messages.info(
            request,
            "Application already has this status."
        )
        return redirect(
            "job_applicants",
            job_id=application.job.id
        )

    remarks = request.POST.get("remarks", "").strip()

    # Save status and history together
    with transaction.atomic():

        application.status = status_value

        application.save(
            update_fields=["status", "updated_at"]
        )

        ApplicationStatusHistory.objects.create(
            application=application,
            old_status=old_status,
            new_status=status_value,
            changed_by=request.user,
            remarks=remarks
        )

    # Send notification after database transaction
    candidate_email = application.candidate.email

    if not candidate_email:
        messages.warning(
            request,
            "Status updated and history saved, "
            "but candidate has no email address."
        )

        return redirect(
            "job_applicants",
            job_id=application.job.id
        )

    try:
        email_sent = send_mail(
            subject=(
                f"Application Status Updated - "
                f"{application.job.title}"
            ),
            message=(
                f"Hello {application.candidate.username},\n\n"
                f"Your application status has been updated.\n\n"
                f"Job: {application.job.title}\n"
                f"Company: {application.job.company_name}\n"
                f"Previous Status: {old_status}\n"
                f"New Status: {status_value}\n\n"
                f"Please log in to JobPortal "
                f"for more details.\n\n"
                f"Thank you."
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[candidate_email],
            fail_silently=False,
        )

        if email_sent:
            messages.success(
                request,
                "Status updated, history saved "
                "and email sent successfully!"
            )
        else:
            messages.warning(
                request,
                "Status updated and history saved, "
                "but email was not sent."
            )

    except Exception:
        logger.exception(
            "Application status email failed. "
            "Application ID: %s",
            application.id
        )

        messages.warning(
            request,
            "Status updated and history saved, "
            "but email could not be sent."
        )

    return redirect(
        "job_applicants",
        job_id=application.job.id
    )


# =========================================================
# CANDIDATE APPLICATION STATUS HISTORY
# =========================================================

@login_required
def application_status_history(request, application_id):

    if request.user.role != "candidate":
        messages.error(
            request,
            "Only candidates can view application history."
        )
        return redirect("candidate_dashboard")

    application = get_object_or_404(
        Application.objects.select_related(
            "job",
            "candidate"
        ),
        id=application_id,
        candidate=request.user
    )

    history = (
        ApplicationStatusHistory.objects
        .filter(application=application)
        .select_related("changed_by")
        .order_by("-changed_at")
    )

    return render(
        request,
        "applications/application_status_history.html",
        {
            "application": application,
            "history": history,
        }
    )
