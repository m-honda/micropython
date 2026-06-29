from network import PPP
import SIM7672

SEC_NONE = PPP.SEC_NONE
SEC_PAP  = PPP.SEC_PAP
SEC_CHAP = PPP.SEC_CHAP

STATE_INACTIVE = const(0)
STATE_ACTIVE = const(1)
STATE_ERROR = const(2)
STATE_CONNECTING = const(3)
STATE_CONNECTED = const(4)

def modem(cls=SIM7672.modem, *args, **kwargs):
    return cls(*args, **kwargs)

