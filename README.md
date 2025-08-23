# Wro-Taiwan-The-Triumvirate-of-Branches

```
wro-taiwan/
├── spike/
│   ├── car.py             # Spike Hub: 控制電池釋放以及鎖定
│   ├── robot_arm.py       # Spike Hub: 控制機械手臂替換電池與通訊的主程式
│   └── battery_storage.py # Spike Hub: 管理電池倉
└── main/
    ├── main.py            # 主控電腦: 後端伺服器兼模型辨識以及與 Spike 通訊
    ├── index.html         # 主控電腦: 前端網頁儀表板 
    └── best.pt            # 主控電腦: YOLOv8 影像辨識模型
```
