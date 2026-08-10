import time
from time import sleep
import gpiozero
from gpiozero import PWMLED
from gpiozero import PWMOutputDevice, DigitalOutputDevice

def pumpsWork(number, pin1=int(), pin2=(), timework=float()):
    pwm = PWMLED(pin1)
    en  = DigitalOutputDevice(pin2, initial_value=False)
    try:
        en.on()
        print(f"Pump{number}_ON")
        
        pwm.value = 1.0
        sleep(timework)
        pwm.value = 0.0
        en.off()
        
        print(f"Pump{number}_OFF")
        sleep(1)

    finally:
        pwm.close()
        en.close()

def pumpsWorkTC(number, pin1=int(), pin2=int(), timewait=float(), timework=float()):
    pwm = PWMLED(pin1)
    en  = DigitalOutputDevice(pin2, initial_value=False)

    try:
        en.off()
        pwm.value = 0.0
        print(f"Pump{number}_OFF")
        sleep(timewait)

        pwm.value = 1.0
        en.on()
        print(f"Pump{number}_ON")
        sleep(timework)

        pwm.value = 0.0
        en.off()
        print(f"Pump{number}_OFF")
        sleep(1)

    finally:
        pwm.close()
        en.close()
        
def stirring(pin1=int(), pin2=int(), timework=int()):
    pwm = PWMLED(pin1)
    en  = DigitalOutputDevice(pin2, initial_value=False)

    try:
        print("Starting stirring...")
        en.on()
        print("stirring ON")

        pwm.value = 0.65
        sleep(0.5)

        pwm.value = 0.55
        sleep(0.5)

        pwm.value = 0.35
        sleep(0.5)

        pwm.value = 0.25
        sleep(0.5)

        pwm.value = 0.15
        sleep(timework)

        pwm.value = 0.0

        print("stirring OFF")
        en.off()
        sleep(1)

    finally:
        pwm.close()
        en.close()
        
def cleanUp(ans, array, flows):
    vol = 4
    if not ans:
        return

    for kei in array:
        pin_pwm, pin_en = array[kei][0], array[kei][1]

        pwm = PWMLED(pin_pwm)
        en  = DigitalOutputDevice(pin_en, initial_value=False)

        try:
            en.off()
            sleep(1)

            pwm.value = 0.90
            print("Start cleaning...")
            en.on()
            sleep(1)

            pwm.value = 0.0
            en.off()

            pwm.value = 0.90
            print("Solvent removing the residues...")
            en.on()

            sleep(vol / flows[pin_pwm])
            sleep(1)

            print("Purging...")
            for _ in range(3):
                en.off()
                sleep(0.5)
                pwm.value = 0.90
                en.on()
                sleep(0.5)
                pwm.value = 0.0

            pwm.value = 0.0
            en.off()

        finally:
            pwm.close()
            en.close()
