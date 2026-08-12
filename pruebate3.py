import asyncio
import threading
import time

import cv2
from ika.driver import Shaker

texto_overlay = "EN ESPERA"
color_overlay = (0, 255, 0)
camara_activa_global = False
ultima_temp_placa = None

hilo_camara_global = None
lock_camara = threading.Lock()


def _worker_camara(app_screen=None):

    global hilo_camara_global, camara_activa_global

    try:
        bucle_camara_hilo(app_screen)
    finally:
        with lock_camara:
            camara_activa_global = False

            if hilo_camara_global is threading.current_thread():
                hilo_camara_global = None

        print("[CAM] Hilo terminado completamente")


def iniciar_camara(app_screen=None):

    global hilo_camara_global, camara_activa_global

    with lock_camara:
        if (
            hilo_camara_global is not None
            and hilo_camara_global.is_alive()
        ):
            print("[CAM] Ya existe un hilo de cámara activo")
            return False

        print("Iniciando cámara")

        camara_activa_global = True

        hilo_camara_global = threading.Thread(
            target=_worker_camara,
            args=(app_screen,),
            daemon=True,
        )

        hilo_camara_global.start()

        return True


def detener_camara():
    """
    Solicita al hilo activo que cierre la cámara.
    La liberación real del dispositivo ocurre dentro
    del finally de bucle_camara_hilo().
    """
    global camara_activa_global

    print("[CAM] Solicitando cierre")
    camara_activa_global = False


def bucle_camara_hilo(app_screen=None):
    # hilo camara
    global texto_overlay, color_overlay, camara_activa_global

    cap = None
    nombre_ventana = "Monitoreo de Reaccion IKA"

    try:
        # Intentar abrir /dev/video0
        cap = cv2.VideoCapture(0, cv2.CAP_V4L2)
        ret = False

        if cap.isOpened():
            # Dar varios intentos para obtener el primer frame
            for _ in range(10):
                ret, _ = cap.read()
                if ret:
                    break
                time.sleep(0.05)

        # Si video0 falla, liberar e intentar video1
        if not cap.isOpened() or not ret:
            if cap is not None:
                cap.release()

            cap = cv2.VideoCapture(1, cv2.CAP_V4L2)
            ret = False

            if cap.isOpened():
                for _ in range(10):
                    ret, _ = cap.read()
                    if ret:
                        break
                    time.sleep(0.05)

        # Si tampoco video1 funciona
        if not cap.isOpened() or not ret:
            print("Error camara")
            return

        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

        time.sleep(0.5)

        cv2.namedWindow(nombre_ventana, cv2.WINDOW_GUI_NORMAL)
        cv2.resizeWindow(nombre_ventana, 600, 300)
        cv2.moveWindow(nombre_ventana, 0, 0)

        while camara_activa_global:
            ret, frame = cap.read()

            if not ret:
                time.sleep(0.01)
                continue

            try:
                if (
                    cv2.getWindowProperty(
                        nombre_ventana,
                        cv2.WND_PROP_VISIBLE
                    )
                    < 1
                ):
                    print("[CAM] Ventana cerrada con X")
                    break

            except Exception:
                print("[CAM] Ventana OpenCV cerrada")
                break

            frame = cv2.resize(
                frame,
                (600, 300),
                interpolation=cv2.INTER_AREA
            )

            if texto_overlay:
                font_scale = 0.45
                thickness = 1
                font = cv2.FONT_HERSHEY_SIMPLEX

                (text_w, text_h), baseline = cv2.getTextSize(
                    texto_overlay,
                    font,
                    font_scale,
                    thickness
                )

                margin = 8

                cv2.rectangle(
                    frame,
                    (10, 8),
                    (
                        10 + text_w + (margin * 2),
                        10 + text_h + margin + 4
                    ),
                    (0, 0, 0),
                    -1,
                )

                cv2.putText(
                    frame,
                    texto_overlay,
                    (10 + margin, 10 + text_h + 2),
                    font,
                    font_scale,
                    color_overlay,
                    thickness,
                    cv2.LINE_AA,
                )

            cv2.imshow(nombre_ventana, frame)

            if cv2.waitKey(1) & 0xFF == ord("q"):
                print("[CAM] Ventana cerrada con Q")
                break

            time.sleep(0.005)

    finally:
        # Marcar primero que la cámara ya no debe seguir ejecutándose
        camara_activa_global = False

        # Liberar físicamente el dispositivo V4L2
        if cap is not None:
            try:
                if cap.isOpened():
                    cap.release()
            except Exception as e:
                print(f"[CAM] Error liberando cámara: {e}")

        # Destruir solamente la ventana de la cámara
        try:
            cv2.destroyWindow(nombre_ventana)
            cv2.waitKey(1)
        except Exception:
            pass

        # Cambiar el estado del botón Cam a gris en la interfaz Kivy
        if app_screen:
            try:
                from kivy.clock import Clock

                Clock.schedule_once(
                    lambda dt: setattr(
                        app_screen,
                        "camara_activa",
                        False
                    ),
                    0,
                )

            except Exception as e:
                print(f"[CAM] Error actualizando Kivy: {e}")

        print("[CAM] Cámara liberada")


async def leer_temperatura_placa(parrilla):
    # lectura sensor placa
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
    # calentamiento inicial
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
    # tiempo de reaccion
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
    # apagado seguro
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
    # post reaccion
    global texto_overlay, color_overlay, camara_activa_global
    color_overlay = (0, 0, 255)
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
    # inicio proceso
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
