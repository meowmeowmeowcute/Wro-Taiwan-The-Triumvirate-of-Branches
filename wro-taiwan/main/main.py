import asyncio
import struct
import json
import threading
import cv2
import torch
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from bleak import BleakScanner, BleakClient
from contextlib import asynccontextmanager
from ultralytics import YOLO

PACKET_TYPE_STORAGE = 0x01
PACKET_TYPE_COMMAND = 0x02
PACKET_TYPE_LOG = 0x03
data_buffer = b''
MODEL_PATH = "best_wro.pt"
CLASS_NAMES = ['CLEAN', 'DIRTY']
model = None
latest_frame = None
frame_lock = threading.Lock()
ai_result_to_send = None
ai_result_lock = threading.Lock()
HUB_NAME = "handsome"
PYBRICKS_UNIVERSAL_CHAR_UUID = "c5f50002-8280-46da-89f4-6d8051e4aeef"
hub_client = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global model
    print("--- 應用程式啟動中 ---")
    try:
        model = YOLO(MODEL_PATH)
        print(f"成功透過 Ultralytics 從 '{MODEL_PATH}' 載入模型。")
    except Exception as e:
        print(f"使用 Ultralytics 載入模型失敗: {e}")
        model = None
    bluetooth_task_instance = asyncio.create_task(bluetooth_task())
    cam_thread = threading.Thread(target=camera_thread_func, daemon=True)
    cam_thread.start()
    yield
    print("--- 應用程式關閉中 ---")
    bluetooth_task_instance.cancel()

app = FastAPI(lifespan=lifespan)

class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
    async def broadcast_data(self, data: dict):
        message = json.dumps(data)
        for connection in self.active_connections:
            await connection.send_text(message)

manager = ConnectionManager()

latest_storage_status = {
    "BLUE":  {"has_battery": 1, "charge": 60, "id": "blue-slot"},
    "RED":   {"has_battery": 1, "charge": 95, "id": "red-slot"},
    "GREEN": {"has_battery": 0, "charge": 0,  "id": "green-slot"}
}

@app.get("/{full_path:path}")
async def serve_spa(full_path: str):
    return HTMLResponse(open("index.html", "r", encoding="utf-8").read())
    
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    await websocket.send_text(json.dumps(latest_storage_status))
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

def camera_thread_func():
    global latest_frame
    cap = cv2.VideoCapture(2)
    if not cap.isOpened():
        print("錯誤：無法開啟鏡頭。")
        return
        
    print("鏡頭已啟動，按 'q' 鍵關閉視窗。")
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
            
        with frame_lock:
            latest_frame = frame.copy()
        
        if model is not None:
            annotated_frame = frame.copy()
            results = model(frame, verbose=False)
            
            for box in results[0].boxes:
                confidence = box.conf[0].item()
                
                if confidence > 0.7:
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    class_id = int(box.cls[0].item())
                    class_name = model.names[class_id]
                    label = f"{class_name} {confidence:.2f}"
                    
                    cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                    cv2.putText(annotated_frame, label, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

            cv2.imshow('Spike Hub Battery Check', annotated_frame)
        else:
            cv2.imshow('Spike Hub Battery Check', frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
            
    cap.release()
    cv2.destroyAllWindows()
    print("鏡頭視窗已關閉。")

async def send_response_to_hub(message: str):
    if hub_client and hub_client.is_connected:
        try:
            payload = b'\x06' + (message + '\n').encode('utf-8')
            await hub_client.write_gatt_char(PYBRICKS_UNIVERSAL_CHAR_UUID, payload)
            print(f"成功發送回應 '{message}' 至 Spike Hub。")
            return True
        except Exception as e:
            print(f"嘗試發送回應 '{message}' 時發生錯誤: {e}")
            return False
    else:
        print("Hub 未連接，無法發送回應。")
        return False

async def analyze_battery_status():
    global ai_result_to_send, latest_frame, model
    if model is None or latest_frame is None:
        print("模型或鏡頭畫面尚未準備好。")
        return
        
    with frame_lock:
        frame_to_process = latest_frame.copy()
        
    try:
        results = model(frame_to_process, verbose=False)
        prediction = "CLEAN"
        
        for box in results[0].boxes:
            if box.conf[0] > 0.7:
                prediction = "DIRTY"
                class_name = model.names[int(box.cls[0])]
                confidence = box.conf[0]
                print(f"偵測到高信心度物件! Class: {class_name}, Confidence: {confidence:.2f}. 最終結果設為 DIRTY。")
                break
        
        if prediction == "CLEAN":
            print("未偵測到任何信心度 > 0.7 的物體。最終結果設為 CLEAN。")

    except Exception as e:
        print(f"解析 YOLO 結果時出錯: {e}")
        prediction = "ERROR"
        
    print(f"辨識完成，結果為: {prediction}。等待 Spike Hub 請求...")
    with ai_result_lock:
        ai_result_to_send = prediction

def handle_rx(_, data: bytearray):
    global data_buffer
    data_buffer += data
    while True:
        start_index = data_buffer.find(b'>')
        if start_index == -1:
            if len(data_buffer) > 1024:
                data_buffer = b''
            break
        
        data_buffer = data_buffer[start_index:]
        if len(data_buffer) < 3:
            break
            
        packet_type = data_buffer[1]
        payload_len = data_buffer[2]
        full_packet_len = 3 + payload_len + 1
        
        if len(data_buffer) < full_packet_len:
            break
            
        if data_buffer[full_packet_len - 1] != ord('<'):
            data_buffer = data_buffer[1:]
            continue
            
        payload = data_buffer[3 : 3 + payload_len]
        process_packet(packet_type, payload)
        data_buffer = data_buffer[full_packet_len:]

def process_packet(packet_type, payload):
    if packet_type == PACKET_TYPE_STORAGE:
        handle_storage_packet(payload)
    elif packet_type == PACKET_TYPE_COMMAND:
        handle_command_packet(payload)
    elif packet_type == PACKET_TYPE_LOG:
        print(f"[Hub Log]: {payload.decode('utf-8', errors='ignore')}")
    else:
        print(f"收到未知的封包類型: {packet_type}")

def handle_storage_packet(payload):
    global latest_storage_status
    try:
        unpacked_data = struct.unpack('>BBBBBB', payload)
        latest_storage_status["BLUE"]["has_battery"] = unpacked_data[0]
        latest_storage_status["BLUE"]["charge"] = unpacked_data[1]
        latest_storage_status["RED"]["has_battery"] = unpacked_data[2]
        latest_storage_status["RED"]["charge"] = unpacked_data[3]
        latest_storage_status["GREEN"]["has_battery"] = unpacked_data[4]
        latest_storage_status["GREEN"]["charge"] = unpacked_data[5]
        asyncio.create_task(manager.broadcast_data(latest_storage_status))
    except Exception as e:
        print(f"解包 storage 數據時出錯: {e}")

def handle_command_packet(payload):
    global ai_result_to_send
    try:
        command = payload.decode('utf-8')
        if command == 'INSPECT':
            print("收到來自 Hub 的影像辨識請求！")
            with ai_result_lock:
                ai_result_to_send = None
            asyncio.create_task(analyze_battery_status())
        elif command == 'RDY_FOR_RESULT':
            with ai_result_lock:
                if ai_result_to_send is not None:
                    print(f"收到 Hub 的結果請求，正在發送: {ai_result_to_send}")
                    asyncio.create_task(send_response_to_hub(ai_result_to_send))
                    ai_result_to_send = None
    except Exception as e:
        print(f"解碼指令時出錯: {e}")

async def bluetooth_task():
    global hub_client
    print("藍牙任務已啟動...")
    while True:
        try:
            print(f"正在掃描 '{HUB_NAME}'...")
            device = await BleakScanner.find_device_by_name(HUB_NAME, timeout=5.0)
            if not device:
                print(f"找不到 '{HUB_NAME}'，5 秒後重試...")
                await asyncio.sleep(5)
                continue
            
            print(f"找到 Hub: {device.address}")
            async with BleakClient(device) as client:
                hub_client = client
                print("成功連接到 Hub。正在訂閱通知...")
                await client.start_notify(PYBRICKS_UNIVERSAL_CHAR_UUID, handle_rx)
                print("訂閱成功。正在監聽數據...")
                while client.is_connected:
                    await asyncio.sleep(1)
            
            print("Hub 已斷線。準備重新連接...")
            hub_client = None
        except asyncio.CancelledError:
            print("藍牙任務被取消。")
            break
        except Exception as e:
            print(f"藍牙任務發生錯誤: {e}。準備重試...")
            hub_client = None
            await asyncio.sleep(5)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(__name__ + ":app", host="0.0.0.0", port=8000, reload=True)