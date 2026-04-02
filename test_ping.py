import monitoring.network
import logging
logging.basicConfig(level=logging.DEBUG)

print("Testing 8.8.8.8:")
ping_ms, jitter_ms, loss = monitoring.network.collecter_ping_jitter("8.8.8.8", count=4)
print(f"Ping: {ping_ms}ms, Jitter: {jitter_ms}ms, Loss: {loss}%")
