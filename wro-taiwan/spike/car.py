#!/usr/bin/env pybricks-micropython
from pybricks.hubs import ThisHub
from pybricks.pupdevices import Motor
from pybricks.parameters import Port, Stop
from pybricks.tools import wait

CAR_ID = 198
MAIN_ID = 179

hub = ThisHub(broadcast_channel=CAR_ID, observe_channels=[MAIN_ID])
hub.speaker.volume(50)

motor_b = Motor(Port.B)

MOTOR_SPEED = 500
DUTY_LIMIT = 75

def reset():
    motor_b.run_until_stalled(speed=MOTOR_SPEED, then=Stop.HOLD, duty_limit=DUTY_LIMIT)

def drop():
    motor_b.run_until_stalled(speed=-MOTOR_SPEED, then=Stop.HOLD, duty_limit=DUTY_LIMIT)

def grab():
    motor_b.run_until_stalled(speed=MOTOR_SPEED, then=Stop.HOLD, duty_limit=DUTY_LIMIT)

def receive_command_sound():
    hub.speaker.beep(frequency=784, duration=250)

def main():
    reset()
    last_command_processed = None

    while True:
        command = hub.ble.observe(MAIN_ID)

        if command and command != last_command_processed:
            last_command_processed = command

            if command == "CAR_GRAB":
                receive_command_sound()
                grab()
                hub.ble.broadcast("CAR_GRABED")
                
            elif command == "CAR_DROP":
                receive_command_sound()
                drop()
                hub.ble.broadcast("CAR_DROPPED")
        
        wait(100)

if __name__ == "__main__":
    main()