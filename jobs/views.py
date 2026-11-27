
@login_required
def job_list(request):

    # -----------------------------------------------------
    # BASE QUERYSET
    # -----------------------------------------------------

    jobs = Job.objects.filter(
        is_active=True
    ).order_by("-created_at")

    # -----------------------------------------------------
    # GET FILTER VALUES
    # -----------------------------------------------------

    search = request.GET.get("search", "").strip()
    location = request.GET.get("location", "").strip()
    job_type = request.GET.get("job_type", "").strip()
    experience = request.GET.get("experience", "").strip()
    min_salary = request.GET.get("min_salary", "").strip()
    max_salary = request.GET.get("max_salary", "").strip()

    # -----------------------------------------------------
    # SEARCH
    # -----------------------------------------------------

    if search:
        search_words = search.split()

        for word in search_words:
            jobs = jobs.filter(
                Q(title__icontains=word)
                | Q(company_name__icontains=word)
                | Q(skills__icontains=word)
                | Q(description__icontains=word)
                | Q(location__icontains=word)
                | Q(experience__icontains=word)
            )

    # -----------------------------------------------------
    # LOCATION FILTER
    # -----------------------------------------------------

    if location:
        jobs = jobs.filter(
            location__icontains=location
        )

    # -----------------------------------------------------
    # JOB TYPE FILTER
    # -----------------------------------------------------

    valid_job_types = get_valid_job_types()

    if job_type in valid_job_types:
        jobs = jobs.filter(
            job_type=job_type
        )

    # -----------------------------------------------------
    # EXPERIENCE FILTER
    # -----------------------------------------------------

    if experience:
        jobs = jobs.filter(
            experience__icontains=experience
        )

    # -----------------------------------------------------
    # SALARY INPUT VALIDATION
    # -----------------------------------------------------

    min_salary_value = None
    max_salary_value = None

    if min_salary:
        try:
            min_salary_value = parse_salary(min_salary)
        except ValueError:
            messages.warning(
                request,
                "Invalid minimum salary filter."
            )

    if max_salary:
        try:
            max_salary_value = parse_salary(max_salary)
        except ValueError:
            messages.warning(
                request,
                "Invalid maximum salary filter."
            )

    # -----------------------------------------------------
    # SALARY RANGE VALIDATION
    # -----------------------------------------------------

    if (
        min_salary_value is not None
        and max_salary_value is not None
        and min_salary_value > max_salary_value
    ):
        messages.warning(
            request,
            "Minimum salary cannot be greater than maximum salary."
        )

        min_salary_value = None
        max_salary_value = None

    # -----------------------------------------------------
    # SALARY FILTER
    # -----------------------------------------------------

    if min_salary_value is not None:
        jobs = jobs.filter(
            salary_max__gte=min_salary_value
        )

    if max_salary_value is not None:
        jobs = jobs.filter(
            salary_min__lte=max_salary_value
        )

    # -----------------------------------------------------
    # JOB SORTING
    # -----------------------------------------------------

    sort_by = request.GET.get("sort", "newest").strip()

    if sort_by == "salary_low":
        jobs = jobs.order_by(
            "salary_min",
            "-created_at"
        )

    elif sort_by == "salary_high":
        jobs = jobs.order_by(
            "-salary_max",
            "-created_at"
        )

    else:
        sort_by = "newest"
        jobs = jobs.order_by("-created_at")

    # -----------------------------------------------------
    # PAGINATION
    # -----------------------------------------------------

    paginator = Paginator(jobs, 10)

    page_number = request.GET.get("page")

    page_obj = paginator.get_page(page_number)

    # -----------------------------------------------------
    # SAVED JOB IDS
    # -----------------------------------------------------

    saved_job_ids = set()

    if request.user.role == "candidate":
        saved_job_ids = set(
            SavedJob.objects.filter(
                candidate=request.user
            ).values_list(
                "job_id",
                flat=True
            )
        )

    # -----------------------------------------------------
    # RENDER
    # -----------------------------------------------------

    return render(
        request,
        "jobs/job_list.html",
        {
            "jobs": page_obj,
            "page_obj": page_obj,
            "paginator": paginator,
            "search": search,
            "location": location,
            "job_type": job_type,
            "experience": experience,
            "min_salary": min_salary,
            "max_salary": max_salary,
            "sort_by": sort_by,
            "saved_job_ids": saved_job_ids,
        },
    )
