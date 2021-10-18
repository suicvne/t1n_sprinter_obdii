from enum import Enum
class SourceAddressByte(Enum):
    UNKNOWN = 0x00 # Unknown; TODO: Is this value actually used for anything though?
    ECM = 0x12 # Modules
    TCM = 0x20
    DAD = 0xF3 # Scan Tools

class KnownServiceIDs(Enum):
    UNKNOWN = 0x00
    GUESS_REQUEST_INFO_ON_CODE = 0x17 # From DAD
    GUESS_RESPONSE_INFO_ON_CODE = 0x57 # From ECM, Parameters: FirstByte = Code Count(?), then code, then a series of unknown fields?

    GUESS_UNKNOWN_TERMINATOR_TO_ECU = 0x31 # To ECU from DAD; followed by unknown 4 bytes 
    GUESS_UNKNOWN_TERMINATOR_TO_DAD = 0x71 # To DAD from ECU; followed by 13(?) unknown bytes.

    GUESS_REQUEST_CODES = 0x18 # From DAD, 3 unknown parameters (Last Run: 02 FF 00)
    GUESS_CODES_RESPONSE = 0x58 # From ECM, Parameters: FirstByte = Code Count(?), each code is stored as a 2 byte combo afterward strangely terminating with byte 0x20
    KEEPALIVE_PING = 0x3E # From DAD
    KEEPALIVE_PONG = 0x7E # From ECM

def ConvertByteToKnownServiceIDs(bbyte):
    try:
        return KnownServiceIDs(bbyte)
    except:
        return KnownServiceIDs.UNKNOWN

def ConvertByteToTargetAddressByte(bbyte):
    try:
        return SourceAddressByte(bbyte)
    except:
        return SourceAddressByte.UNKNOWN

def ConvertByteToSourceAddressByte(bbyte):
    try:
        return SourceAddressByte(bbyte)
    except:
        return SourceAddressByte.UNKNOWN
