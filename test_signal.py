from network import Sigfox
import socket
import binascii
import time


def zfill(string, width):
    if len(string) < width:
        return ('0' * (width - len(string))) + string
    else:
        return string


# Initialize Sigfox for RCZ4 (Chile)
sigfox = Sigfox(mode=Sigfox.SIGFOX, rcz=Sigfox.RCZ4)
s = socket.socket(socket.AF_SIGFOX, socket.SOCK_RAW)
s.setblocking(False)
s.setsockopt(socket.SOL_SIGFOX, socket.SO_RX, False)
s.settimeout(10)

c = 10
n = 10

# Send 10 messages to the Sigfox network to test connectivity
for i in range(n):
    string = zfill(str(c), 3) + zfill(str(i), 3)
    payload = bytes(string.encode())
    print("Sending...")
    s.send(payload)
    print("Sent " + payload.decode() + ".")
    time.sleep(20)

print("Done.")
