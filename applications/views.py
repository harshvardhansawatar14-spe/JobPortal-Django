
from django.conf import settings
from django.core.mail import send_mail
from os.path import splitext

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from jobs.models import Job
from .models import Application


# =========================================================
# CONSTANTS
# =========================================================

ALLOWED_RESUME_EXTENSIONS = {".pdf", ".doc", ".docx"}

ALLOWED_APPLICATION_STATUSES = {
    "applied",
    "shortlisted",
    "rejected",
    "selected",
}

MAX_RESUME_SIZE = 5 * 1024 * 1024


# =========================================================
# APPLY FOR JOB
# =========================================================

@login_required
def apply_job(request, job_id):

    job = get_object_or_404(Job, id=job_id, is_active=True)

    # Only candidates can apply
    if request.user.role != "candidate":
        messages.error(request, "Only candidates can apply for jobs.")
        return redirect("job_detail", job_id=job.id)

    # Check application deadline
    if job.application_deadline:
        if timezone.localdate() > job.application_deadline:
            messages.error(request, "Application deadline has expired.")
            return redirect("job_detail", job_id=job.id)

    # Check duplicate application for the SAME job
    already_applied = Application.objects.filter(
        candidate=request.user,
        job=job
    ).exists()

    if already_applied:
        messages.warning(request, "You have already applied for this job.")
        return redirect("job_detail", job_id=job.id)

    # GET - Show application form
    if request.method == "GET":
        return render(
            request,
            "applications/apply_job.html",
            {"job": job}
        )

    # =====================================================
    # POST REQUEST
    # =====================================================

    cover_letter = request.POST.get("cover_letter", "").strip()
    resume = request.FILES.get("resume")

    # Validate cover letter
    if not cover_letter:
        messages.error(request, "Please enter a cover letter.")
        return render(request, "applications/apply_job.html", {
            "job": job,
            "cover_letter": cover_letter,
        })

    if len(cover_letter) < 20:
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
        messages.error(request, "Please upload your resume.")
        return render(request, "applications/apply_job.html", {
            "job": job,
            "cover_letter": cover_letter,
        })

    # Validate extension
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

    # Validate file size
    if resume.size > MAX_RESUME_SIZE:
        messages.error(
            request,
            "Resume size must not exceed 5 MB."
        )
        return render(request, "applications/apply_job.html", {
            "job": job,
            "cover_letter": cover_letter,
        })

    # Save application
    try:
        Application.objects.create(
            job=job,
            candidate=request.user,
            cover_letter=cover_letter,
            resume=resume,
        )

    except IntegrityError:
        messages.warning(
            request,
            "You have already applied for this job."
        )
        return redirect("job_detail", job_id=job.id)

    messages.success(request, "Application submitted successfully!")
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

    return render(request, "applications/my_applications.html", {
        "applications": applications,
    })


# =========================================================
# JOB APPLICANTS
# =========================================================

@login_required
def job_applicants(request, job_id):

    if request.user.role != "recruiter":
        messages.error(request, "Only recruiters can view applicants.")
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

    return render(request, "applications/job_applicants.html", {
        "job": job,
        "applications": applications,
    })


# =========================================================
# UPDATE APPLICATION STATUS
# =========================================================

@login_required
def update_application_status(request, application_id):

    if request.user.role != "recruiter":
        messages.error(request, "Only recruiters can update status.")
        return redirect("candidate_dashboard")

    if request.method != "POST":
        messages.error(request, "Invalid request method.")
        return redirect("recruiter_dashboard")

    application = get_object_or_404(
        Application,
        id=application_id,
        job__recruiter=request.user
    )

    status_value = request.POST.get("status", "").strip()

    if status_value not in ALLOWED_APPLICATION_STATUSES:
        messages.error(request, "Invalid application status.")
        return redirect(
            "job_applicants",
            job_id=application.job.id
        )

    old_status = application.status

    application.status = status_value
    application.save(update_fields=["status", "updated_at"])

    # Send email only when status changes
    if old_status != status_value:

        try:
            send_mail(
                subject=f"Application Status Updated - {application.job.title}",
                message=(
                    f"Hello {application.candidate.username},\n\n"
                    f"Your application status has been updated.\n\n"
                    f"Job: {application.job.title}\n"
                    f"Company: {application.job.company_name}\n"
                    f"Previous Status: {old_status}\n"
                    f"New Status: {status_value}\n\n"
                    f"Please log in to JobPortal for more details.\n\n"
                    f"Thank you."
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[application.candidate.email],
                fail_silently=False,
            )

            messages.success(
                request,
                "Status updated and email sent successfully!"
            )

        except Exception:
            messages.warning(
                request,
                "Status updated, but email could not be sent."
            )

    else:
        messages.success(
            request,
            "Application status updated successfully!"
        )

    return redirect(
        "job_applicants",
        job_id=application.job.id
    )

from django.conf import settings
from django.core.mail import send_mail
from os.path import splitext

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from jobs.models import Job
from .models import Application


# =========================================================
# CONSTANTS
# =========================================================

ALLOWED_RESUME_EXTENSIONS = {".pdf", ".doc", ".docx"}

ALLOWED_APPLICATION_STATUSES = {
    "applied",
    "shortlisted",
    "rejected",
    "selected",
}

MAX_RESUME_SIZE = 5 * 1024 * 1024


# =========================================================
# APPLY FOR JOB
# =========================================================

@login_required
def apply_job(request, job_id):

    job = get_object_or_404(Job, id=job_id, is_active=True)

    # Only candidates can apply
    if request.user.role != "candidate":
        messages.error(request, "Only candidates can apply for jobs.")
        return redirect("job_detail", job_id=job.id)

    # Check application deadline
    if job.application_deadline:
        if timezone.localdate() > job.application_deadline:
            messages.error(request, "Application deadline has expired.")
            return redirect("job_detail", job_id=job.id)

    # Check duplicate application for the SAME job
    already_applied = Application.objects.filter(
        candidate=request.user,
        job=job
    ).exists()

    if already_applied:
        messages.warning(request, "You have already applied for this job.")
        return redirect("job_detail", job_id=job.id)

    # GET - Show application form
    if request.method == "GET":
        return render(
            request,
            "applications/apply_job.html",
            {"job": job}
        )

    # =====================================================
    # POST REQUEST
    # =====================================================

    cover_letter = request.POST.get("cover_letter", "").strip()
    resume = request.FILES.get("resume")

    # Validate cover letter
    if not cover_letter:
        messages.error(request, "Please enter a cover letter.")
        return render(request, "applications/apply_job.html", {
            "job": job,
            "cover_letter": cover_letter,
        })

    if len(cover_letter) < 20:
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
        messages.error(request, "Please upload your resume.")
        return render(request, "applications/apply_job.html", {
            "job": job,
            "cover_letter": cover_letter,
        })

    # Validate extension
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

    # Validate file size
    if resume.size > MAX_RESUME_SIZE:
        messages.error(
            request,
            "Resume size must not exceed 5 MB."
        )
        return render(request, "applications/apply_job.html", {
            "job": job,
            "cover_letter": cover_letter,
        })

    # Save application
    try:
        Application.objects.create(
            job=job,
            candidate=request.user,
            cover_letter=cover_letter,
            resume=resume,
        )

    except IntegrityError:
        messages.warning(
            request,
            "You have already applied for this job."
        )
        return redirect("job_detail", job_id=job.id)

    messages.success(request, "Application submitted successfully!")
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

    return render(request, "applications/my_applications.html", {
        "applications": applications,
    })


# =========================================================
# JOB APPLICANTS
# =========================================================

@login_required
def job_applicants(request, job_id):

    if request.user.role != "recruiter":
        messages.error(request, "Only recruiters can view applicants.")
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

    return render(request, "applications/job_applicants.html", {
        "job": job,
        "applications": applications,
    })


# =========================================================
# UPDATE APPLICATION STATUS
# =========================================================

@login_required
def update_application_status(request, application_id):

    if request.user.role != "recruiter":
        messages.error(request, "Only recruiters can update status.")
        return redirect("candidate_dashboard")

    if request.method != "POST":
        messages.error(request, "Invalid request method.")
        return redirect("recruiter_dashboard")

    application = get_object_or_404(
        Application,
        id=application_id,
        job__recruiter=request.user
    )

    status_value = request.POST.get("status", "").strip()

    if status_value not in ALLOWED_APPLICATION_STATUSES:
        messages.error(request, "Invalid application status.")
        return redirect(
            "job_applicants",
            job_id=application.job.id
        )

    old_status = application.status

    application.status = status_value
    application.save(update_fields=["status", "updated_at"])

    # Send email only when status changes
    if old_status != status_value:

        try:
            send_mail(
                subject=f"Application Status Updated - {application.job.title}",
                message=(
                    f"Hello {application.candidate.username},\n\n"
                    f"Your application status has been updated.\n\n"
                    f"Job: {application.job.title}\n"
                    f"Company: {application.job.company_name}\n"
                    f"Previous Status: {old_status}\n"
                    f"New Status: {status_value}\n\n"
                    f"Please log in to JobPortal for more details.\n\n"
                    f"Thank you."
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[application.candidate.email],
                fail_silently=False,
            )

            messages.success(
                request,
                "Status updated and email sent successfully!"
            )

        except Exception:
            messages.warning(
                request,
                "Status updated, but email could not be sent."
            )

    else:
        messages.success(
            request,
            "Application status updated successfully!"
        )

    return redirect(
        "job_applicants",
        job_id=application.job.id
    )
