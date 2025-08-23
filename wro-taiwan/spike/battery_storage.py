#!/usr/bin/env pybricks-micropython
from pybricks.hubs import ThisHub
from pybricks.pupdevices import Motor, ColorSensor
from pybricks.parameters import Port, Color, Stop, Icon
from pybricks.tools import wait
import ujson

CAR_ID = 198
MAIN_ID = 179
STORAGE_ID = 147

hub = ThisHub(broadcast_channel=STORAGE_ID, observe_channels=[MAIN_ID])
motor_b = Motor(Port.B) # battery storage
motor_a = Motor(Port.A)
motor_f = Motor(Port.F)
motor_e = Motor(Port.E)
color_sensor_c = ColorSensor(Port.C) # color sensor of battery storage
hub.ble.broadcast(None)
hub.speaker.volume(30)

colors = [Color.BLUE, Color.RED, Color.GREEN]

storage = {
    Color.BLUE : [1, 60],
    Color.RED : [1, 95],
    Color.GREEN : [0, 0]
}

color_convert = {
    Color.RED : "RED",
    Color.BLUE : "BLUE",
    Color.GREEN : 'GREEN',
}

speed_b = -250

def go_color(motor, color_sensor, color, speed, step):

    if not color in colors:
        return

    motor.run(speed)
    while True:
        if (color_sensor.color() == color):
            wait(step)
            motor.stop()
            break
        wait(10)

def find_empty(storage):
    for key, item in storage.items():
        if (item[0] == 0):
            storage[key][0] = 1
            storage[key][1] = 0
            return key

def find_usable(storage):
    for key, item in storage.items():
        if (item[0] == 1 and item[1]>=90):
            storage[key][0] = 0
            storage[key][1] = 0
            return key

def receive_command_sound():
    hub.speaker.beep(frequency=784, duration=250)  # G5 (中高音 Sol)

def broadcast_json(hub, data_dict):
    global color_convert

    data = {color_convert[key]: value for key, value in data_dict.items()}
    
    json_string = ujson.dumps(data)
    max_chunk_size = 18
    chunks = [json_string[i:i + max_chunk_size] for i in range(0, len(json_string), max_chunk_size)]
    total_chunks = len(chunks)

    for i, chunk in enumerate(chunks):
        message = f"D:{i+1}/{total_chunks}:{chunk}"
        hub.ble.broadcast(message)
        wait(250) # 延遲確保每個包都被對方接收到
    
    hub.ble.broadcast(None)

def main():
    global storage
    last_command_processed = None
    step_b = 150 #ms

    F = 40
    # motor_a.dc(50)
    motor_f.dc(F)
    # motor_e.dc(-100)

    while True:
        command = hub.ble.observe(MAIN_ID)

        if command and command != last_command_processed:
            last_command_processed = command

            if command == "BATTERY_STORAGE":
                receive_command_sound()
                empty = find_empty(storage)
                go_color(motor_b, color_sensor_c, empty, speed_b, step_b) # go to empty storage
                hub.ble.broadcast("BATTERY_STORAGED")
                
            elif command == "BATTERY_REPLACE":
                receive_command_sound()
                usable = find_usable(storage)
                go_color(motor_b, color_sensor_c, usable, speed_b, step_b) # go to usable storage
                hub.ble.broadcast("BATTERY_REPLACED")
            
            elif command == "STOP_BATTERY_TRACK":
                motor_f.dc(0)
                hub.ble.broadcast("STOPED_BATTERY_TRACK")
                
            elif command == "START_BATTERY_TRACK":
                motor_f.dc(F)
                hub.ble.broadcast("STARTED_BATTERY_TRACK")

            elif command == "BATTERY_CONVERT_RESET":
                receive_command_sound()
                storage = {
                    Color.BLUE : [1, 60],
                    Color.RED : [1, 95],
                    Color.GREEN : [0, 0]
                }
                wait(step_b)
                hub.ble.broadcast("BATTERY_CONVERT_RESETED")
            elif command == "STORAGE_DATA":
                broadcast_json(hub, storage)
                receive_command_sound()


        wait(100)

if __name__ == "__main__":
    main()
