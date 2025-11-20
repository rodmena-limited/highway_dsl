"""
Gunicorn configuration for Highway DSL Generator API

This configuration includes:
- Worker management with memory leak prevention
- Proper timeout settings for LLM calls
- Logging configuration
- Graceful worker restarts
"""

# Server socket
bind = "127.0.0.1:7291"
backlog = 2048

# Worker processes
workers = 2
worker_class = "sync"
worker_connections = 1000
timeout = 180  # 3 minutes for LLM calls
keepalive = 5

# Worker restart strategy (memory leak prevention)
max_requests = 100  # Restart worker after 100 requests
max_requests_jitter = 20  # Add randomness to prevent all workers restarting at once
graceful_timeout = 30  # Time to finish requests before force kill

# Logging
accesslog = "-"  # Log to stdout
errorlog = "-"  # Log to stderr
loglevel = "info"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Process naming
proc_name = "dsl-generator"

# Server mechanics
daemon = False
pidfile = "/var/run/highway_dsl/gunicorn.pid"
umask = 0o007
user = None  # Will be set by systemd
group = None  # Will be set by systemd
tmp_upload_dir = None

# SSL (not used, nginx handles it)
keyfile = None
certfile = None


# Worker lifecycle hooks
def on_starting(server):
    """Called just before the master process is initialized."""
    server.log.info("Starting DSL Generator API")


def on_reload(server):
    """Called to recycle workers during a reload via SIGHUP."""
    server.log.info("Reloading DSL Generator API")


def when_ready(server):
    """Called just after the server is started."""
    server.log.info("DSL Generator API is ready. Listening on %s", bind)


def worker_int(worker):
    """Called when a worker receives the SIGINT or SIGQUIT signal."""
    worker.log.info("Worker received INT or QUIT signal")


def worker_abort(worker):
    """Called when a worker receives the SIGABRT signal."""
    worker.log.info("Worker received ABORT signal")


def pre_fork(server, worker):
    """Called just before a worker is forked."""
    pass


def post_fork(server, worker):
    """Called just after a worker has been forked."""
    server.log.info("Worker spawned (pid: %s)", worker.pid)


def post_worker_init(worker):
    """Called just after a worker has initialized the application."""
    worker.log.info("Worker initialized successfully")


def worker_exit(server, worker):
    """Called just after a worker has been exited."""
    server.log.info("Worker exiting (pid: %s)", worker.pid)


def child_exit(server, worker):
    """Called just after a worker has been exited, in the master process."""
    pass


def nworkers_changed(server, new_value, old_value):
    """Called just after num_workers has been changed."""
    server.log.info("Number of workers changed from %s to %s", old_value, new_value)


def on_exit(server):
    """Called just before exiting gunicorn."""
    server.log.info("Shutting down DSL Generator API")


# Preload application for better memory usage
preload_app = True

# Recycle workers to prevent memory leaks
# Workers will be gracefully restarted after handling max_requests
# This prevents long-running processes from accumulating memory
