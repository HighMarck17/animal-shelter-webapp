"""
Gunicorn configuration for production
"""
import multiprocessing

# Server socket — 0.0.0.0 required in Docker (127.0.0.1 is not reachable outside the container)
bind = "0.0.0.0:8000"
backlog = 2048

# Worker processes
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "sync"
worker_connections = 1000
timeout = 30
keepalive = 2

# Logging to stdout/stderr — Docker captures it automatically with `docker logs`
accesslog = "-"
errorlog = "-"
loglevel = "info"

# Process naming
proc_name = "shelter_webapp"

# Server mechanics — daemon=False is mandatory in a container (PID 1 must stay in the foreground)
daemon = False
user = None
group = None
tmp_upload_dir = None

# Security
# Gunicorn >= 25.1 opens a control socket (for `gunicornc`) in $HOME by default;
# it is not used here, so keep the attack surface minimal
control_socket_disable = True
limit_request_line = 4094
limit_request_fields = 100
limit_request_field_size = 8190
