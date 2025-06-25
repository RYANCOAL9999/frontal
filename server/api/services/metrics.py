from prometheus_client import Counter, Histogram

# Counters for crop processing jobs
job_total_counter = Counter(
    "crop_jobs_total", "Total number of crop processing jobs submitted."
)

# Counter for jobs completed successfully
job_completed_counter = Counter(
    "crop_jobs_completed_total",
    "Total number of crop processing jobs completed successfully.",
)

# Counter for jobs that failed
job_failed_counter = Counter(
    "crop_jobs_failed_total", "Total number of crop processing jobs that failed."
)

# Histogram for job processing duration
job_processing_duration_seconds = Histogram(
    "crop_job_processing_duration_seconds",
    "Histogram of crop job processing durations in seconds.",
    buckets=(5, 10, 15, 20, 25, 30, 45, 60, float("inf")),  # Example buckets
)
