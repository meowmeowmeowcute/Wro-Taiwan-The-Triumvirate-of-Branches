from pybricks.hubs import ThisHub
from pybricks.pupdevices import Motor
from pybricks.parameters import Port, Stop, Button
from pybricks.tools import wait, StopWatch
import ujson
from usys import stdout, stdin 
import ustruct    
import uselect   

PACKET_TYPE_STORAGE = b'\x01'
PACKET_TYPE_COMMAND = b'\x02'
PACKET_TYPE_LOG = b'\x03'

CAR_ID = 198
MAIN_ID = 179 
STORAGE_ID = 147
DEBUG = True

hub = ThisHub(broadcast_channel=MAIN_ID, observe_channels=[CAR_ID, STORAGE_ID])
hub.ble.broadcast(None)
hub.speaker.volume(70)
watch = StopWatch()


def reconstruct_and_cleanup(hub, chunks):
    if not chunks:
        debug("Error: No data chunks to reconstruct.")
        hub.speaker.beep(262, 500)
        return None
    try:
        total = max(chunks.keys())
        full_str = "".join(chunks.get(i, "") for i in range(1, total + 1))
        parsed = ujson.loads(full_str)
        
        hub.speaker.beep(1047, 200)
        return parsed
    except Exception as e:
        debug(f"Error: Failed to reconstruct data. Details: {e}")
        hub.speaker.beep(262, 500)
        return None
def send_packet_to_pc(packet_type, payload):
    try:
        if not isinstance(payload, bytes):
            payload = payload.encode('utf-8')

        length = len(payload)
        full_packet = b'>' + packet_type + bytes([length]) + payload + b'<'
        stdout.buffer.write(full_packet)
    except Exception as e:
        pass
def debug(string):
    if DEBUG:
        send_packet_to_pc(PACKET_TYPE_LOG, string)
def wait_for_ai_result(timeout=10000):
    poller = uselect.poll()
    poller.register(stdin, uselect.POLLIN)

    send_packet_to_pc(PACKET_TYPE_COMMAND, b'INSPECT')
    send_command_sound()
    
    watch.reset()
    debug("已發送辨識請求，開始輪詢結果...")

    while watch.time() < timeout:
        send_packet_to_pc(PACKET_TYPE_COMMAND, b'RDY_FOR_RESULT')
        
        poll_watch = StopWatch()
        while poll_watch.time() < 250:
            if poller.poll(10): 
                result = stdin.readline().strip()
                if result:
                    receive_command_sound()
                    debug(f"成功收到結果-> {result}")
                    return result 
            wait(10)
        

    debug("等待 AI 結果超時。")
    return "TIMEOUT"
def call_storage_data(hub, watch, request_command="STORAGE_DATA", timeout=5000):
    hub.ble.broadcast(request_command)
    chunks = {}
    expected_total_chunks = None
    watch.reset()

    while watch.time() < timeout:
        data = hub.ble.observe(STORAGE_ID)
        if not data:
            wait(10)
            continue

        if isinstance(data, str) and data.startswith('D:'):
            try:
                _, header, payload = data.split(':', 2)
                current, total = map(int, header.split('/'))
                
                if expected_total_chunks is None:
                    expected_total_chunks = total
                
                if current not in chunks:
                    chunks[current] = payload

                if len(chunks) == expected_total_chunks:
                    return reconstruct_and_cleanup(hub, chunks)

            except (ValueError, IndexError):
                pass 

    debug("Timeout: Did not receive a complete response.")
    hub.speaker.beep(349, 700)
    hub.ble.broadcast(None)
    return None
def send_storage_to_pc(storage_dict):
    if not storage_dict:
        return

    color_order = ["BLUE", "RED", "GREEN"]
    data_to_pack = []
    for color in color_order:
        has_battery, charge = storage_dict.get(color, [0, 0])
        data_to_pack.append(has_battery)
        data_to_pack.append(charge)
    
    payload = ustruct.pack('>BBBBBB', *data_to_pack)
    send_packet_to_pc(PACKET_TYPE_STORAGE, payload)
def rst(motor, base, speed=-720, duty_limit=50):
    motor.run_until_stalled(speed, then=Stop.HOLD, duty_limit=duty_limit)
    motor.reset_angle(0)
    if base != 0:
        motor.run_target(speed, base)
    return base
def rst_switch(motor, time = 500, speed=720, duty_limit=50):
    motor.run_until_stalled(speed, then=Stop.HOLD, duty_limit=duty_limit)
    a = motor.angle()
    wait(time)
    motor.run_until_stalled(-speed, then=Stop.HOLD, duty_limit=duty_limit)
    b = motor.angle()
    wait(time)
    if (a<b):
        return a, b;
    else:
        return b, a;
def switch(motor, open_p, close_p, status, speed = 720, duty_limit = 100):
    if status:
        motor.run_until_stalled(status*speed, then=Stop.HOLD, duty_limit=duty_limit)
    else:
        motor.run_until_stalled(-speed*status, then=Stop.HOLD, duty_limit=duty_limit)
    return (-status)
def go_hold(motor, time, mid, speed = 720):
    wait(time)
    motor.run_target(speed, mid)
def turn_switch(motor, open_p, mid_p, close_p, time, nxt, status, speed = 720):
    n = switch(motor, open_p, close_p, status, speed = speed)
    go_hold(motor, time, mid_p, speed = speed)
    wait(nxt)
    return n
def get_base_speed(goal, cur):
    return ((goal-cur)/30)
def work_motor(motor, goal, speed = 360):
    motor.run_target(speed, goal, wait = False)
    while(not motor.done()):
        wait(10)
def work_motor_double(motor_a, goal_a, motor_b, goal_b):
    dist_b = abs(motor_b.angle()-goal_b)
    dist_a = abs(motor_a.angle()-goal_a)
    if(dist_b > 0):
        motor_a.run_target(360/dist_b*dist_a, goal_a, wait = False)
    else:
        motor_a.run_target(360, goal_a, wait = False)
    motor_b.run_target(360, goal_b, wait = False)
    while not motor_a.done() or not motor_b.done():
        wait(10)
def reset_sound():
    for i in range(3):
        hub.speaker.beep(frequency=614, duration=230)
        wait(350)
def storage_sound():
    hub.speaker.beep(frequency=523, duration=80)
    wait(80)
    hub.speaker.beep(frequency=659, duration=80)
    wait(80)
    hub.speaker.beep(frequency=784, duration=150)
def drop_sound():
    hub.speaker.beep(frequency=131, duration=500)
def send_command_sound():
    hub.speaker.beep(frequency=523, duration=200)
def receive_command_sound():
    hub.speaker.beep(frequency=784, duration=250)
def check_receive_sound():
    hub.speaker.beep(frequency=1047, duration=150)
def main():

    motor_A = Motor(Port.A)
    motor_B = Motor(Port.B)
    motor_C = Motor(Port.C)
    motor_D = Motor(Port.D)
    motor_E = Motor(Port.E)
    motor_F = Motor(Port.F)
    
    pos_A = 0; pos_C = 0; pos_E = 0
    base_A = 80+422; statu_B = 1; base_C = -624; power_D = 100; base_E = 10; statu_F = -1
    B_open, B_close, B_mid, F_open, F_close, F_mid = None, None, None, None, None, None
    storage_status = None
    reset_A = False; reset_B = False; reset_C = False; reset_E = False; reset_F = False

    motor_D.dc(power_D)
    
    def rst_A():
        nonlocal pos_A, reset_A
        pos_A = rst(motor_A, base_A, duty_limit=100)
        reset_A = True
    def rst_B():
        nonlocal B_open, B_close, B_mid, reset_B
        B_open, B_close = rst_switch(motor_B, time=100, speed=900, duty_limit=200)
        B_mid = (B_open+B_close)/2
        go_hold(motor_B, 0, B_mid)
        reset_B = True
    def rst_C():
        nonlocal pos_C, reset_C
        offset = 30
        pos_C = rst(motor_C, base_C-offset, speed=330, duty_limit=50)
        work_motor(motor_C, base_C+offset, speed=180)
        motor_C.reset_angle(base_C)
        reset_C = True
    def rst_E():
        nonlocal pos_E, reset_E
        pos_E = rst(motor_E, base_E, speed = -720, duty_limit=100)
        reset_E = True
    def rst_F():
        nonlocal F_open, F_close, F_mid, reset_F
        F_open, F_close = rst_switch(motor_F, time = 50, speed=-720, duty_limit=200)
        F_mid = (F_open+F_close)/2
        go_hold(motor_F, 0, F_mid)
        reset_F = True
    def go_base_position_arm(ka = 1, kc = 1):
        if not reset_A or not reset_C: raise SystemExit()
        work_motor_double(motor_A, base_A*ka, motor_C, base_C*kc)
        motor_A.reset_angle(base_A)
        motor_C.reset_angle(base_C)
    def go_temp_position_arm(offset_A = 320, offset_C = -270):
        if not reset_A or not reset_C: raise SystemExit()
        work_motor_double(motor_A, (base_A+offset_A), motor_C, (base_C-offset_C))
    def go_move_position_arm(offset_A = 250, offset_C = 90):
        if not reset_A or not reset_C: raise SystemExit()
        work_motor_double(motor_A, (base_A+offset_A), motor_C, (base_C-offset_C))
    def go_storage_position_arm(offset_A = 250, offset_C = 170):
        if not reset_A or not reset_C: raise SystemExit()
        work_motor_double(motor_A, base_A+offset_A, motor_C, base_C-offset_C)
    def go_check_position_arm(offset_A = -330, offset_C = -280):
        if not reset_A or not reset_C: raise SystemExit()
        work_motor(motor_A, base_A+offset_A, speed=360)
        work_motor(motor_C, base_C-offset_C, speed=360)
    def go_drop_position_arm():
        if not reset_A or not reset_C: raise SystemExit()
        work_motor_double(motor_A, base_A+410, motor_C, base_C-480)
    def go_storage_position_bed():
        if not reset_E: raise SystemExit()
        work_motor(motor_E, 1650, speed = 720)
    def go_drop_position_bed():
        if not reset_E: raise SystemExit()
        work_motor(motor_E, 0, speed=720)
    def go_car_position_bed(goal = 640):
        if not reset_E: raise SystemExit()
        work_motor(motor_E, goal, speed=720)    
    def turn_B():
        nonlocal statu_B
        if not reset_B: raise SystemExit()
        statu_B = turn_switch(motor_B, B_open, B_mid, B_close, 500, 1000, statu_B)
    def turn_F():   
        nonlocal statu_F
        if not reset_F: raise SystemExit()
        statu_F = turn_switch(motor_F, F_open, F_mid, F_close, 1000, 1000, statu_F)
    def reset_all(time = 0):
        rst_E()
        go_car_position_bed()
        rst_A()
        rst_C()
        rst_B()
        rst_F()
        wait(time)
        reset_sound()
    def base_position(ka, kc):
        go_move_position_arm()
        go_car_position_bed()
        go_base_position_arm(ka, kc)
    def call_grab(command = "CAR_GRAB", check = "CAR_GRABED"):
        hub.ble.broadcast(command)
        while True:
            if hub.ble.observe(CAR_ID) == check:
                hub.ble.broadcast(None)
                check_receive_sound()
                break
            wait(100)
    def call_drop(command = "CAR_DROP", check = "CAR_DROPPED"):
        hub.ble.broadcast(command)
        while True:
            if hub.ble.observe(CAR_ID) == check:
                hub.ble.broadcast(None)
                check_receive_sound()
                break
            wait(100)
    def call_storage(command = "BATTERY_STORAGE", check = "BATTERY_STORAGED"):
        hub.ble.broadcast(command)
        while True:
            if hub.ble.observe(STORAGE_ID) == check:
                hub.ble.broadcast(None)
                check_receive_sound()
                break
            wait(100)
    def call_replace(command = "BATTERY_REPLACE", check = "BATTERY_REPLACED"):
        hub.ble.broadcast(command)
        while True:
            if hub.ble.observe(STORAGE_ID) == check:
                hub.ble.broadcast(None)
                check_receive_sound()
                break
            wait(100)
    def call_battery_convert_reset(command = "BATTERY_CONVERT_RESET", check = "BATTERY_CONVERT_RESETED"):
        hub.ble.broadcast(command)
        while True:
            if hub.ble.observe(STORAGE_ID) == check:
                hub.ble.broadcast(None)
                check_receive_sound()
                break
            wait(100)
    def call_stop_track(command = "STOP_BATTERY_TRACK", check = "STOPED_BATTERY_TRACK"):
        hub.ble.broadcast(command)
        while True:
            if hub.ble.observe(STORAGE_ID) == check:
                hub.ble.broadcast(None)
                check_receive_sound()
                break
            wait(100)
    def call_start_track(command = "START_BATTERY_TRACK", check = "STARTED_BATTERY_TRACK"):
        hub.ble.broadcast(command)
        while True:
            if hub.ble.observe(STORAGE_ID) == check:
                hub.ble.broadcast(None)
                check_receive_sound()
                break
            wait(100)
    def check():
        go_temp_position_arm()
        go_check_position_arm()
        go_drop_position_bed()

        battery_state = True

        ai_result = wait_for_ai_result()

        if ai_result == "DIRTY":
            battery_state = False
            debug("AI 辨識-> 髒污，執行回收。")
        elif ai_result == "CLEAN":
            battery_state = True
            debug("AI 辨識-> 乾淨")
        else:
            debug("AI 辨識-> 超時")
        go_car_position_bed()
        go_temp_position_arm()
        go_move_position_arm()

        return battery_state
    def recycle():
        go_drop_position_bed()
        call_stop_track()
        go_drop_position_arm()
        turn_B()
        go_move_position_arm()
        call_start_track()
    def grab():
        turn_F()
        call_drop()
        turn_B()
        wait(1000)
        turn_F()
        call_grab()
    def storage():
        call_storage()
        go_storage_position_bed()
        turn_F()
        go_storage_position_arm()
        turn_B()
        turn_F()

        storage_status = call_storage_data(hub, watch)
        if storage_status:
            send_storage_to_pc(storage_status)
            debug(f"Status after storage: {str(storage_status)}")

    def replace(ka, kc, k):
        nonlocal storage_status
        go_move_position_arm()
        call_replace()
        go_storage_position_bed()
        go_storage_position_arm(offset_C=(170+k))
        wait(1000)
        turn_F()
        turn_B()
        go_move_position_arm()
        
        storage_status = call_storage_data(hub, watch)
        if storage_status:
            send_storage_to_pc(storage_status)
            debug(f"Storage status updated: {str(storage_status)}")

        turn_F()
        go_car_position_bed()
        go_temp_position_arm()
        go_base_position_arm(ka, kc)
        call_drop()
        turn_F()
        call_grab()
        turn_B()
        turn_F()
    def process():

        nonlocal storage_status
        reset_all(3000)
        
        call_battery_convert_reset()
        storage_status = call_storage_data(hub, watch)
        if storage_status:
            send_storage_to_pc(storage_status)
            debug(f"Initial storage status: {str(storage_status)}")
        
        grab()
        go_temp_position_arm()
        go_move_position_arm()
        battery_state = check()  

        if battery_state:
            storage()
            base_position(0.98, 0.98)
        else:
            recycle()
            base_position(0.98, 0.98)

        replace(1.01, 1.07, 25)

    process()
    debug("___________________")

if __name__ == "__main__":
    main()
