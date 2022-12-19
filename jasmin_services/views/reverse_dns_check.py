import socket

from django import http
from django.views.decorators.http import require_safe


@require_safe
def reverse_dns_check(request):
    """Handle /reverse_dns_check/.

    Just returns some plain-text information about the reverse DNS status of the
    client.
    """
    response = http.HttpResponse(content_type="text/plain")
    # Use the X-Real-Ip header if present (for reverse proxy), otherwise use 'REMOTE_ADDR'
    remote_ip = request.META.get("HTTP_X_REAL_IP", request.META["REMOTE_ADDR"])
    response.write(f"External IP address: {remote_ip}\r\n")
    # Attempt a reverse DNS lookup
    try:
        host = socket.gethostbyaddr(remote_ip)[0]
    except Exception:
        response.write("Reverse DNS lookup failed\r\n")
    else:
        response.write(f"Resolved to host: {host}")
    return response
