import pycom
import time

pycom.heartbeat(False)
for cycles in range(10):
    pycom.rgbled(0x007f00)
    time.sleep(5)
    pycom.rgbled(0x7f7f00)
    time.sleep(5)
    pycom.rgbled(0x7f0000)
    time.sleep(4)
