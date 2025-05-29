#
# Copyright (c) 2025 MechaTracks Co., Ltd.
#
# SPDX-License-Identifier: MIT
#

from machine import Pin, Timer, UART
from micropython import const
from network import PPP
import time

__DEFAULT_BAUDRATE = const(115200)
__DEFAULT_BUFFER_SIZE = const(2048)
__GPIO_POWER_PIN = const(30)
__GPIO_RESET_PIN = const(31)
__GPIO_STATUS_PIN = const(32)
__GPIO_LED_PIN = const(29)
__POWERON_TIMEOUT = const(20000)
__POWEROFF_TIMEOUT = const(10000)
__RESET_TIMEOUT = const(__POWERON_TIMEOUT + __POWEROFF_TIMEOUT)
__TIMEOUT_POLLING_INTERVAL = const(100)


SEC_NONE = PPP.SEC_NONE
SEC_PAP = PPP.SEC_PAP
SEC_CHAP = PPP.SEC_CHAP

PDP_IP = 'IP'
PDP_IPV6 = 'IPV6'
PDP_IPV4V6 = 'IPV4V6'
PDP_NONIP = 'Non-IP'


class modem:
    def __init__(self, uart=UART(1), baudrate=__DEFAULT_BAUDRATE, handshake=True, led=Pin(__GPIO_LED_PIN), debug=False):
        self.__enable_debug = debug
        self.__params = {
            'apn': None,
            'user': None,
            'key': None,
            'security': None,
            'pdp': None,
        }
        self.__power_pin = Pin(__GPIO_POWER_PIN, Pin.OUT)
        self.__reset_pin = Pin(__GPIO_RESET_PIN, Pin.OUT)
        self.__status_pin = Pin(__GPIO_STATUS_PIN, Pin.IN)
        self.__uart = uart
        self.__uart.init(
            __DEFAULT_BAUDRATE,
            bits=8,
            parity=None,
            stop=1,
            txbuf=__DEFAULT_BUFFER_SIZE,
            rxbuf=__DEFAULT_BUFFER_SIZE,
            flow=0
        )
        self.__baudrate = baudrate
        self.__handshake = handshake
        self.__dialup_retries = 60
        self.__dialup_delay = 500
        self.__ppp = PPP(self.__uart)
        self.led = led
        if not self.led:
            return
        self.led.init(Pin.OUT)
        self.timer = Timer()
        self.timer.init(freq=2, callback=self.__create_timer_handler())

    def __create_timer_handler(self):
        def timer_handler(t):
            if self.__ppp.isconnected():
                self.led.toggle()
            else:
                if self.__status_pin.value() == 1:
                    self.led.on()
                else:
                    self.led.off()
        return timer_handler


    def __receive(self, timeout=1000):
        if self.__uart.any() == 0 and timeout > 0:
            while self.__uart.any() == 0:
                timeout -= 1
                time.sleep_ms(1)
                if timeout == 0:
                    return None
        line = bytearray()
        for _ in range(timeout):
            data = self.__uart.readline(__DEFAULT_BUFFER_SIZE)
            if data is None:
                time.sleep_ms(1)
                continue
            line += data
            if self.__enable_debug:
                print(data)
            if data[-1] != ord('\n'):
                continue
            try:
                s = line.decode().rstrip()
            except UnicodeError:
                return None
            return s
        return None

    def __expect(self, exp, aborts=['ERROR'], timeout=10000):
        deadline = time.ticks_add(time.ticks_ms(), timeout)
        while time.ticks_diff(deadline, time.ticks_ms()) > 0:
            rcv = self.__receive(timeout)
            if rcv == exp:
                return True
            if aborts and rcv:
                for abort in aborts:
                    if abort in rcv:
                        return False
        return False

    def __send(self, cmd, timeout=1000):
        if isinstance(cmd, str):
            cmd = cmd.encode()
        self.__uart.write(cmd)
        while timeout > 0:
            if self.__uart.txdone():
                return True
            time.sleep_ms(1)
            timeout -= 1
        return False

    def __command(self, cmd, aborts=[], timeout=1000):
        if self.__uart.any():
            self.__uart.read()
        self.__send(cmd + '\r\n')
        if self.__enable_debug:
            print(cmd + '\r\n')
        if not self.__expect(cmd, aborts, timeout):
            return False
        return True

    def __command_and_expect(self, cmd, exp=None, aborts=['ERROR'], timeout=10000):
        if self.__uart.any():
            self.__uart.read()
        if not self.__command(cmd):
            return False
        if exp is None:
            return True
        return self.__expect(exp, aborts, timeout)

    def __wait_pin(self, retries=20, delay=500):
        cpin_stat = None
        for _ in range(retries):
            if self.__command('AT+CPIN?', timeout=5000):
                result = self.__receive()
                if 'ERROR' not in result:
                    try:
                        cpin_stat = result.split(' ')[-1]
                    except (IndexError, ValueError):
                        return False
                    finally:
                        self.__expect('OK')
                if cpin_stat == 'READY':
                    return True
            time.sleep_ms(delay)
        return False

    def __wait_reg(self, retries, delay):
        cereg_stat = None
        for _ in range(retries):
            if self.__command('AT+CEREG?'):
                result = self.__receive()
                if 'ERROR' not in result:
                    try:
                        cereg_stat = int(result.split(',')[-1])
                    except (IndexError, ValueError):
                        return False
                    finally:
                        self.__expect('OK')
                if cereg_stat == 1 or cereg_stat == 5:
                    return True
            time.sleep_ms(delay)
        return False

    def __dial_ppp(self, detach=False):
        params = self.__params.copy()
        if self.__params['security'] & PPP.SEC_CHAP:
            params['security'] = PPP.SEC_CHAP
        elif self.__params['security'] & PPP.SEC_PAP:
            params['security'] = PPP.SEC_PAP
        else:
            params['security'] = PPP.SEC_NONE
        if not self.__setup_modem():
            return False
        self.__wait_pin()
        if not self.__config_network(params, detach):
            return False
        if not self.__wait_reg(self.__dialup_retries, self.__dialup_delay):
            return False
        if not self.__command_and_expect('ATD*99***1#', 'CONNECT'):
            return False
        self.__ppp.connect(security=params['security'], user=params['user'], key=params['key'])
        return True

    def __hang_ppp(self, timeout=5000):
        self.__ppp.disconnect()
        for _ in range((timeout - 1) // 1000 + 1):
            if not self.__ppp.isconnected():
                return True
            time.sleep_ms(1000)
        time.sleep(1)
        self.__send('+++')
        time.sleep(1)
        for _ in range((timeout - 1) // 1000 + 1):
            if self.__command_and_expect('ATH', 'OK'):
                return True
        return False

    def active(self, activate=None, reset=True):
        if activate is True:
            if reset and self.__status_pin.value() == 1:
                self.reset()
            else:
                self.poweron()
            return
        if activate is False:
            self.poweroff()
            return
        return self.__status_pin.value() == 1

    def poweron(self):
        if self.__status_pin.value() == 1:
            return True
        self.__reset_pin.off()
        if self.__power_pin.value() == 1:
            self.__power_pin.off()
            time.sleep(1)
        self.__power_pin.on()
        time.sleep(1)
        self.__power_pin.off()
        for _ in range(__POWERON_TIMEOUT // __TIMEOUT_POLLING_INTERVAL):
            time.sleep_ms(__TIMEOUT_POLLING_INTERVAL)
            if self.__status_pin.value() == 1:
                return True
        return False

    def poweroff(self):
        self.__uart.init(baudrate=__DEFAULT_BAUDRATE, flow=0)
        if self.__status_pin.value() == 0:
            return True
        self.__reset_pin.off()
        if self.__power_pin.value() == 1:
            self.__power_pin.off()
            time.sleep(1)
        self.__power_pin.on()
        time.sleep(3)
        self.__power_pin.off()
        for _ in range(__POWEROFF_TIMEOUT // __TIMEOUT_POLLING_INTERVAL):
            time.sleep_ms(__TIMEOUT_POLLING_INTERVAL)
            if self.__status_pin.value() == 0:
                return True
        return False

    def reset(self):
        self.__uart.init(baudrate=__DEFAULT_BAUDRATE, flow=0)
        self.__power_pin.off()
        if self.__reset_pin.value() == 1:
            self.__reset_pin.off()
            time.sleep(1)
        self.__reset_pin.on()
        time.sleep(1)
        self.__reset_pin.off()
        for _ in range(__RESET_TIMEOUT // __TIMEOUT_POLLING_INTERVAL):
            time.sleep_ms(__TIMEOUT_POLLING_INTERVAL)
            if self.__status_pin.value() == 1:
                return True
        return False

    def __clear_buffers(self):
        if self.__uart.any():
            self.__uart.read()

    def __setup_modem(self):
        if not (self.__command('AT', timeout=5000) and self.__expect('OK')):
            self.__command_and_expect('ATH', 'OK')
            if not self.__command_and_expect('AT', 'OK'):
                for _ in range(3):
                    time.sleep(1)
                    self.__send('+++')
                    time.sleep(1)
                    if self.__command_and_expect('ATH', 'OK'):
                        break
                for _ in range(5):
                    if self.__command_and_expect('AT', 'OK'):
                        break
                    self.__command_and_expect('ATE1', 'OK')
                    time.sleep(1)
                if not self.__command_and_expect('AT', 'OK'):
                    return False
        self.__command('AT+CEREG?')
        result = self.__receive()

        if 'ERROR' in result:
            return False
        try:
            cereg_mode = int(result.split(',')[0][-1])
        except (IndexError, ValueError):
            return False
        finally:
            self.__expect('OK')
        if cereg_mode != 0:
            if not self.__command_and_expect('AT+CREG=0', 'OK'):
                return False
        self.__command('AT+IFC?')
        result = self.__receive()
        if 'ERROR' in result:
            return False
        try:
            current_flowcontrol = result.split(' ')[-1]
        except (IndexError, ValueError):
            return False
        finally:
            self.__expect('OK')
        if self.__handshake:
            if current_flowcontrol != '2,2':
                if not self.__command_and_expect('AT+IFC=2,2', 'OK'):
                    return False
                self.__uart.init(flow=(UART.CTS | UART.RTS))
                self.__clear_buffers()
        else:
            if current_flowcontrol != '0,0':
                if not self.__command_and_expect('AT+IFC=0,0', 'OK'):
                    return False
                self.__uart.init(flow=0)
                self.__clear_buffers()
        self.__command('AT+IPR?')
        result = self.__receive()
        if 'ERROR' in result:
            return False
        try:
            current_baudrate = int(result.split(' ')[-1])
        except (IndexError, ValueError):
            return False
        finally:
            self.__expect('OK')
        if self.__baudrate != current_baudrate:
            if not self.__command_and_expect(f'AT+IPR={self.__baudrate}', 'OK'):
                return False
            self.__uart.init(baudrate=self.__baudrate)
            self.__clear_buffers()
        return True

    def config(self, param=None, apn=None, user=None, key=None, pdp=None, security=None):
        if param:
            return self.__params[param]
        if apn is not None:
            if isinstance(apn, str):
                self.__params['apn'] = apn
            else:
                raise TypeError("'apn' must be a string not {type(apn).__name__}")
        if user is not None:
            if isinstance(user, str):
                self.__params['user'] = user
            else:
                raise TypeError("'user' must be a string not {type(user).__name__}")
        if key is not None:
            if isinstance(key, str):
                self.__params['key'] = key
            else:
                raise TypeError("'key' must be a string not {type(key).__name__}")
        if pdp is not None:
            if isinstance(pdp, str):
                self.__params['pdp'] = pdp
            else:
                raise TypeError("'pdp' must be a string not {type(pdp).__name__}")
        if security is not None:
            if isinstance(security, int):
                self.__params['security'] = security
            else:
                raise TypeError("'security' must be a integer not {type(security).__name__}")
        return

    def __config_network(self, params, detach=False, timeout=30000):
        apn = None
        user = None
        key = None
        pdp = None
        sec = None
        cont_is_updated = False
        auth_is_updated = False
        self.__command('AT+CGDCONT?')
        result = self.__receive()
        if 'ERROR' in result:
            return False
        try:
            ans = result.split(',')
            pdp, apn = ans[1:3]
        except (IndexError, ValueError):
            pass
        self.__expect('OK')
        if pdp != f"\"{params['pdp']}\"" or apn != f"\"{params['apn']}\"":
            cont_is_updated = True
        self.__command('AT+CGAUTH?')
        result = self.__receive()
        if 'ERROR' in result:
            return False
        try:
            ans = result.split(',')
            sec, user, key = ans[1:4]
        except (IndexError, ValueError):
            pass
        self.__expect('OK')
        if sec != f"{params['security']}" or user != f"\"{params['user']}\"" or key != f"\"{params['key']}\"":
            auth_is_updated = True
        if not detach and not cont_is_updated and not auth_is_updated:
            return True
        self.__command_and_expect('AT+CFUN=4', 'OK')
        if cont_is_updated:
            cont_cmd = "AT+CGDCONT=1"
            if params['pdp'] != "":
                cont_cmd += f",{params['pdp']}"
                if params['apn'] != "":
                    cont_cmd += f",{params['apn']}"
            self.__command_and_expect(cont_cmd, 'OK')
        if auth_is_updated:
            auth_cmd = f"AT+CGAUTH=1,{params['security']}"
            if params['user'] != "":
                auth_cmd += f",{params['user']}"
                if params['key'] != "":
                    auth_cmd += f",{params['key']}"
            self.__command_and_expect(auth_cmd, 'OK')
        self.__command_and_expect('AT+CFUN=1', 'OK', timeout=timeout)
        self.__wait_pin()
        return True

    def connect(self, apn=None, user=None, key=None, pdp=None, security=None, detach=True, retries=60, delay=500):
        if pdp is None and self.__params['pdp'] is None:
            pdp = 'IP'
        if security is None and self.__params['security'] is None:
            security = PPP.SEC_CHAP|PPP.SEC_PAP
        self.config(apn=apn, user=user, key=key, pdp=pdp, security=security)
        self.pon(detach, retries, delay)

    def disconnect(self):
        self.poff()

    def pon(self, detach=False, retries=30, delay=1000):
        self.__dialup_retries = retries
        self.__dialup_delay = delay
        return self.__dial_ppp(detach)

    def poff(self, timeout=5000):
        self.__hang_ppp(timeout)

    def ifconfig(self):
        return self.__ppp.ifconfig()

    def isconnected(self):
        return self.__ppp.isconnected()

    def status(self):
        return self.__ppp.status()
