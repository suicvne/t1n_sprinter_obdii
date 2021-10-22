# About

A small Python project dedicated to using an ELM327 to reverse engineer the ECU K-line on a T1N (2002-2006) Sprinter Van.
The following application looks for a usb-serial device, attempts to configure it like an ELM327. Upon success,
it will put the ELM327 into monitor mode showing all headers and dump any and all messages it reads over OBDII. 

At the same time, Python classes attempt to parse and make a somewhat-sane object-oriented interface for the KWP2000/T1N Sprinter
OBDII protocol.

# Running

```
pip3 install pyserial
python3 sprinter_obdii_monitor.py
```