import socket
import sys

def test_smtp_connection(host, port, timeout=10):
    print(f"Testing connection to {host}:{port}...")
    try:
        with socket.create_connection((host, port), timeout=timeout) as sock:
            print("Successfully connected!")
            return True
    except socket.timeout:
        print("Connection timed out.")
    except Exception as e:
        print(f"Connection failed: {e}")
    return False

hosts_to_test = [
    ("smtp-relay.brevo.com", 2525),
    ("smtp-relay.brevo.com", 587),
    ("smtp-relay.brevo.com", 465),
    ("8.8.8.8", 53), # DNS test to check internet
]

for host, port in hosts_to_test:
    test_smtp_connection(host, port)
