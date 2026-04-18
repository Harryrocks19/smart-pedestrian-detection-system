import cv2
import os

# Run this script to register a known face
# Press SPACE to capture, Q to quit

name = input("Enter person's name: ").strip()
if not name:
    print("Name cannot be empty.")
    exit()

cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")

print("Look at the camera. Press SPACE to capture face. Press Q to quit.")

while True:
    ret, frame = cap.read()
    if not ret:
        break

    gray  = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    faces = face_cascade.detectMultiScale(gray, 1.1, 5, minSize=(80, 80))

    for (x, y, w, h) in faces:
        cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 2)
        cv2.putText(frame, "Press SPACE to capture", (x, y-10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

    cv2.imshow("Register Face - " + name, frame)
    key = cv2.waitKey(1) & 0xFF

    if key == ord(' ') and len(faces) > 0:
        x, y, w, h = faces[0]
        face_img = frame[y:y+h, x:x+w]
        path = f"known_faces/{name}.jpg"
        cv2.imwrite(path, face_img)
        print(f"Face saved: {path}")
        break
    elif key == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
