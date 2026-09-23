import cv2, time

for cam in ['cam1', 'cam2', 'cam3']:
    url = f'rtsp://127.0.0.1:8554/{cam}'
    print(f'Testing {url}...')
    cap = cv2.VideoCapture(url)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    time.sleep(3)
    if cap.isOpened():
        ret, frame = cap.read()
        if ret:
            print(f'  [OK] {cam}: frame shape {frame.shape}')
        else:
            print(f'  [FAIL] {cam}: opened but cannot read frame')
    else:
        print(f'  [FAIL] {cam}: cannot open RTSP stream')
    cap.release()
