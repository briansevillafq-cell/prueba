import cv2
import numpy as np

# Configuración de cámara USB en alta velocidad
cap = cv2.VideoCapture(0, cv2.CAP_V4L2)
cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

if not cap.isOpened():
    print("Error: No se pudo acceder a /dev/video0")
    exit()

print("Programa iniciado. Presiona 'q' sobre la ventana de video para salir.")

while True:
    ret, frame = cap.read()
    if not ret:
        break

    alto, ancho, _ = frame.shape

    # Definir la Región de Interés (ROI) al centro de la toma
    x, y, w, h = int(ancho * 0.35), int(alto * 0.25), int(ancho * 0.3), int(alto * 0.5)
    roi = frame[y:y+h, x:x+w]

    if roi.size > 0:
        # 1. Determinación de Color (HSV)
        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        h_prom = np.median(hsv[:, :, 0])
        s_prom = np.median(hsv[:, :, 1])

        if s_prom < 30:
            color = "Incoloro / Blanco"
        elif 0 <= h_prom < 10 or 170 <= h_prom <= 179:
            color = "Rojo"
        elif 11 <= h_prom <= 25:
            color = "Naranja"
        elif 26 <= h_prom <= 35:
            color = "Amarillo"
        elif 36 <= h_prom <= 85:
            color = "Verde"
        elif 86 <= h_prom <= 125:
            color = "Azul"
        else:
            color = "Violeta"

        # 2. Determinación de Estado (Varianza del Laplaciano)
        gris = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        textura_score = cv2.Laplacian(gris, cv2.CV_64F).var()
        
        # Umbral: Cristales/polvos elevan la varianza de textura
        estado = "Solido / Precipitado" if textura_score > 120.0 else "Liquido / Solucion"

        # Graficar ROI y texto informativo
        cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
        cv2.putText(frame, f"Color: {color}", (x, y - 35),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        cv2.putText(frame, f"Estado: {estado}", (x, y - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

    # Mostrar ventana nativa en el escritorio de VNC
    cv2.imshow("Monitoreo de Reaccion", frame)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
