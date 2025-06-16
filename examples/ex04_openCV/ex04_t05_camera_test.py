import cv2

wCam, hCam = 800, 600
cap = cv2.VideoCapture(0)
cap.set(3, wCam)
cap.set(4, hCam)

if not cap.isOpened():
    print("Camera error")
else:
    while True:
        _, img = cap.read()
        cv2.imshow("Image", img)
        if cv2.waitKey(0) & 0xFF == ord('q'):
            break

cap.release()
cv2.destroyAllWindows()