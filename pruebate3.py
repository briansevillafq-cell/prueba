import asyncio
import time

import cv2
from ika.driver import Shaker

# Variables globales compartidas
texto_overlay = ""
color_overlay = (0, 255, 0)  # Verde BGR por defecto
camara_activa_global = False
preguntando_cierre = False
ultima_temp_placa = None
INTERVALO_PARPADEO = 0.5

# Coordenadas y dimensiones para la caja de diálogo táctil en la ventana OpenCV
BOX_W, BOX_H = 440, 90
BTN_YES_RECT = None
BTN_NO_RECT = None


def callback_raton_camara(event, x, y, flags, param):
    """Procesa los clics en la ventana OpenCV para responder la pregunta post-reacción."""
    global camara_activa_global, preguntando_cierre, BTN_YES_RECT, BTN_NO_RECT

    if event == cv2.EVENT_LBUTTONDOWN and preguntando_cierre:
        # Clic en "Sí"
        if BTN_YES_RECT:
            x1, y1, x2, y2 = BTN_YES_RECT
            if x1 <= x <= x2 and y1 <= y <= y2:
                camara_activa_global = False
                preguntando_cierre = False
                return

        # Clic en "No" -> La pregunta y la cámara PERMANECEN en pantalla
        if BTN_NO_RECT:
            x1, y1, x2, y2 = BTN_NO_RECT
            if x1 <= x <= x2 and y1 <= y <= y2:
                print(
                    "Seleccionado 'No'. La cámara y la pregunta permanecen activas."
                )


def bucle_camara_hilo(app_screen=None):
    """Hilo exclusivo de captura OpenCV sin bloquear el hilo principal de Kivy."""
    global texto_overlay, color_overlay, camara_activa_global, preguntando_cierre
    global BTN_YES_RECT, BTN_NO_RECT

    cap = cv2.VideoCapture(0, cv2.CAP_V4L2)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
    cap.set(cv2.CAP_PROP_FPS, 30)

    if not cap.isOpened():
        print("Error: No se pudo abrir la cámara /dev/video0")
        camara_activa_global = False
        if app_screen:
            from kivy.clock import Clock

            Clock.schedule_once(
                lambda dt: setattr(app_screen, "camara_activa", False)
            )
        return

    cv2.namedWindow("Monitoreo de Reaccion IKA")
    cv2.setMouseCallback("Monitoreo de Reaccion IKA", callback_raton_camara)

    while camara_activa_global:
        ret, frame = cap.read()
        if not ret:
            time.sleep(0.01)
            continue

        h, w, _ = frame.shape

        # Overlay Superior (Progreso / Cronómetro)
        if texto_overlay:
            mostrar_texto = True
            if color_overlay == (0, 0, 255):  # Rojo parpadeante
                if int(time.time() / INTERVALO_PARPADEO) % 2 == 0:
                    mostrar_texto = False

            if mostrar_texto:
                cv2.rectangle(frame, (20, 20), (820, 75), (0, 0, 0), -1)
                cv2.putText(
                    frame,
                    texto_overlay,
                    (30, 58),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    color_overlay,
                    2,
                    cv2.LINE_AA,
                )

        # Overlay Inferior Derecho (Pregunta interactiva con botones Sí / No)
        if preguntando_cierre:
            box_x1 = w - BOX_W - 20
            box_y1 = h - BOX_H - 20
            box_x2 = w - 20
            box_y2 = h - 20

            cv2.rectangle(
                frame, (box_x1, box_y1), (box_x2, box_y2), (0, 0, 0), -1
            )
            cv2.rectangle(
                frame, (box_x1, box_y1), (box_x2, box_y2), (0, 255, 255), 2
            )

            cv2.putText(
                frame,
                "Deseas cerrar la camara?",
                (box_x1 + 20, box_y1 + 32),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.65,
                (255, 255, 255),
                1,
                cv2.LINE_AA,
            )

            # Botón "Sí"
            btn_yes_x1, btn_yes_y1 = box_x1 + 140, box_y1 + 45
            btn_yes_x2, btn_yes_y2 = box_x1 + 250, box_y1 + 80
            BTN_YES_RECT = (btn_yes_x1, btn_yes_y1, btn_yes_x2, btn_yes_y2)

            cv2.rectangle(
                frame,
                (btn_yes_x1, btn_yes_y1),
                (btn_yes_x2, btn_yes_y2),
                (0, 180, 0),
                -1,
            )
            cv2.rectangle(
                frame,
                (btn_yes_x1, btn_yes_y1),
                (btn_yes_x2, btn_yes_y2),
                (255, 255, 255),
                1,
            )
            cv2.putText(
                frame,
                "Si",
                (btn_yes_x1 + 40, btn_yes_y1 + 25),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (255, 255, 255),
                2,
                cv2.LINE_AA,
            )

            # Botón "No"
            btn_no_x1, btn_no_y1 = box_x1 + 270, box_y1 + 45
            btn_no_x2, btn_no_y2 = box_x1 + 380, box_y1 + 80
            BTN_NO_RECT = (btn_no_x1, btn_no_y1, btn_no_x2, btn_no_y2)

            cv2.rectangle(
                frame,
                (btn_no_x1, btn_no_y1),
                (btn_no_x2, btn_no_y2),
                (0, 0, 180),
                -1,
            )
            cv2.rectangle(
                frame,
                (btn_no_x1, btn_no_y1),
                (btn_no_x2, btn_no_y2),
                (255, 255, 255),
                1,
            )
            cv2.putText(
                frame,
                "No",
                (btn_no_x1 + 38, btn_no_y1 + 25),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (255, 255, 255),
                2,
                cv2.LINE_AA,
            )

        cv2.imshow("Monitoreo de Reaccion IKA", frame)

        if cv2.waitKey(1) & 0xFF == ord("q"):
            camara_activa_global = False
            break

        time.sleep(0.005)

    cap.release()
    cv2.destroyAllWindows()
    preguntando_cierre = False
    camara_activa_global = False

    if app_screen:
        from kivy.clock import Clock

        Clock.schedule_once(
            lambda dt: setattr(app_screen, "camara_activa", False)
        )


async def leer_temperatura_placa(parrilla):
    global ultima_temp_placa
    try:
        res_placa = await parrilla.query("IN_PV_1")
        if res_placa is not None:
            val_placa = float(res_placa)
            if val_placa >= 0:
                if ultima_temp_placa is not None:
                    if abs(val_placa - ultima_temp_placa) > 20.0:
                        val_placa = ultima_temp_placa
                ultima_temp_placa = val_placa
                return val_placa
    except Exception:
        pass
    return None


async def esperar_hasta_rango(parrilla, temperatura_final):
    global texto_overlay, color_overlay
    color_overlay = (0, 255, 0)

    while True:
        temp_placa = await leer_temperatura_placa(parrilla)
        txt_placa = f"{temp_placa:.1f} C" if temp_placa is not None else "N/A"
        texto_overlay = (
            f"Calentando... Temp Placa: {txt_placa} | Goal: {temperatura_final:.1f} C"
        )

        if temp_placa is not None and temp_placa >= temperatura_final:
            return temp_placa

        await asyncio.sleep(1.0)


async def mantener_temperatura(parrilla, temperatura, tiempo_minutos):
    global texto_overlay, color_overlay
    color_overlay = (0, 255, 0)

    tiempo_total_segundos = tiempo_minutos * 60
    tiempo_restante = tiempo_total_segundos
    loop = asyncio.get_running_loop()
    ultima_medicion = loop.time()

    while tiempo_restante > 0:
        temp_placa = await leer_temperatura_placa(parrilla)
        momento_actual = loop.time()
        tiempo_restante -= momento_actual - ultima_medicion
        ultima_medicion = momento_actual

        if tiempo_restante < 0:
            tiempo_restante = 0

        segundos_totales = int(tiempo_restante)
        minutos_restantes = segundos_totales // 60
        segundos_restantes = segundos_totales % 60

        txt_placa = f"{temp_placa:.1f} C" if temp_placa is not None else "N/A"
        texto_overlay = f"Tiempo restante: {minutos_restantes:02d}:{segundos_restantes:02d} | Temp Placa: {txt_placa}"

        if tiempo_restante > 0:
            await asyncio.sleep(min(1.0, tiempo_restante))


async def apagar_equipo(parrilla):
    try:
        await parrilla.set(equipment="heater", setpoint=1.0)
        await parrilla.control(equipment="heater", on=False)
    except Exception as e:
        print(f"Error al apagar calentador: {e}")

    try:
        await parrilla.control(equipment="shaker", on=False)
    except Exception as e:
        print(f"Error al apagar agitador: {e}")


async def cronometro_post_reaccion(parrilla):
    global texto_overlay, color_overlay, camara_activa_global, preguntando_cierre
    color_overlay = (0, 0, 255)  # Rojo BGR
    preguntando_cierre = True
    inicio_post = time.time()

    while camara_activa_global:
        tiempo_inactivo = int(time.time() - inicio_post)
        horas = tiempo_inactivo // 3600
        minutos = (tiempo_inactivo % 3600) // 60
        segundos = tiempo_inactivo % 60

        str_tiempo = (
            f"{horas:02d}:{minutos:02d}:{segundos:02d}"
            if horas > 0
            else f"{minutos:02d}:{segundos:02d}"
        )
        texto_overlay = f"[OFF] Tiempo sin calentar y agitar: +{str_tiempo}"
        await asyncio.sleep(1.0)


async def ejecutar_parrilla(puerto, temperatura, rpm, tiempo_minutos):
    parrilla = Shaker(address=puerto)
    try:
        try:
            await parrilla.set(equipment="heater", setpoint=1.0)
            await parrilla.control(equipment="heater", on=False)
            await parrilla.control(equipment="shaker", on=False)
            await asyncio.sleep(0.3)
        except Exception:
            pass

        await parrilla.set(equipment="shaker", setpoint=rpm)
        await asyncio.sleep(0.3)
        await parrilla.control(equipment="shaker", on=True)
        await asyncio.sleep(0.3)

        await parrilla.set(equipment="heater", setpoint=temperatura)
        await asyncio.sleep(0.3)
        await parrilla.control(equipment="heater", on=True)

        await esperar_hasta_rango(parrilla, temperatura)
        await mantener_temperatura(parrilla, temperatura, tiempo_minutos)

    finally:
        await apagar_equipo(parrilla)
        if camara_activa_global:
            await cronometro_post_reaccion(parrilla)
