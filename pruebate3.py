import asyncio
import threading
import time

import cv2
from ika.driver import Shaker

texto_overlay = "EN ESPERA"
color_overlay = (0, 255, 0)
camara_activa_global = False
ultima_temp_placa = None


# ============================================================
# CONTROL DE CAMARA
# ============================================================
#
# La camara usa UN SOLO HILO durante toda la ejecucion.
# Ese mismo hilo abre, muestra, cierra y vuelve a abrir
# la ventana de OpenCV. Esto evita recrear ventanas Qt
# desde hilos Python diferentes.
#

hilo_camara_global = None
lock_camara = threading.Lock()

evento_abrir_camara = threading.Event()
evento_salir_hilo_camara = threading.Event()

app_screen_camara = None


def iniciar_camara(app_screen=None):
    """
    Solicita abrir la camara.

    Si el hilo permanente de camara no existe, se crea una sola vez.
    Las siguientes aperturas reutilizan exactamente el mismo hilo.
    """
    global hilo_camara_global
    global camara_activa_global
    global app_screen_camara

    with lock_camara:

        if app_screen is not None:
            app_screen_camara = app_screen

        # Crear el hilo permanente solamente una vez
        if (
            hilo_camara_global is None
            or not hilo_camara_global.is_alive()
        ):
            evento_salir_hilo_camara.clear()

            hilo_camara_global = threading.Thread(
                target=_bucle_camara_persistente,
                daemon=True,
                name="HiloCamaraMIKI",
            )

            hilo_camara_global.start()

        # Si ya estaba activa, no volver a solicitar otra apertura
        if camara_activa_global:
            print("[CAM] La camara ya esta activa")
            return False

        print("Iniciando camara")

        camara_activa_global = True
        evento_abrir_camara.set()

        return True


def detener_camara():
    """
    Solicita cerrar la camara actual.

    El hilo permanente NO se destruye.
    Solamente se cierra VideoCapture y la ventana de OpenCV.
    """
    global camara_activa_global

    print("[CAM] Solicitando cierre")

    camara_activa_global = False
    evento_abrir_camara.clear()


def _actualizar_estado_kivy(valor):
    """
    Actualiza el estado visual del boton CAM de Kivy
    desde el hilo principal de Kivy.
    """
    if app_screen_camara is None:
        return

    try:
        from kivy.clock import Clock

        Clock.schedule_once(
            lambda dt: setattr(
                app_screen_camara,
                "camara_activa",
                valor
            ),
            0,
        )

    except Exception as e:
        print(f"[CAM] Error actualizando Kivy: {e}")


def _abrir_dispositivo_camara():
    """
    Intenta abrir /dev/video0 y despues /dev/video1.

    Se realizan varios intentos de lectura inicial para evitar
    considerar fallida una camara que tarda un poco en entregar
    su primer frame.
    """
    for indice in (0, 1):

        cap = cv2.VideoCapture(
            indice,
            cv2.CAP_V4L2
        )

        if not cap.isOpened():
            try:
                cap.release()
            except Exception:
                pass
            continue

        cap.set(
            cv2.CAP_PROP_FRAME_WIDTH,
            640
        )

        cap.set(
            cv2.CAP_PROP_FRAME_HEIGHT,
            480
        )

        ret = False

        for _ in range(10):

            ret, frame = cap.read()

            if ret and frame is not None:
                return cap

            time.sleep(0.05)

        try:
            cap.release()
        except Exception:
            pass

    return None


def _bucle_camara_persistente():
    """
    Hilo permanente de camara.

    Este hilo permanece vivo durante toda la ejecucion del programa.
    Cada vez que evento_abrir_camara se activa:
        1. abre VideoCapture
        2. crea la ventana
        3. muestra video
        4. espera cierre por X, Q o boton CAM
        5. libera VideoCapture
        6. destruye la ventana
        7. vuelve a esperar una nueva apertura

    Lo importante es que TODAS las ventanas OpenCV se crean y
    destruyen desde este mismo hilo.
    """
    global camara_activa_global

    nombre_ventana = "Monitoreo de Reaccion IKA"

    print("[CAM] Hilo permanente iniciado")

    while not evento_salir_hilo_camara.is_set():

        # Esperar hasta que alguien solicite abrir la camara
        evento_abrir_camara.wait(timeout=0.1)

        if evento_salir_hilo_camara.is_set():
            break

        if not evento_abrir_camara.is_set():
            continue

        cap = None
        ventana_creada = False

        try:
            # ------------------------------------------------
            # ABRIR CAMARA
            # ------------------------------------------------

            cap = _abrir_dispositivo_camara()

            if cap is None:
                print("Error camara")
                camara_activa_global = False
                evento_abrir_camara.clear()
                _actualizar_estado_kivy(False)
                continue

            # Si mientras se estaba abriendo se solicito cerrar,
            # no crear la ventana.
            if not camara_activa_global:
                continue

            # ------------------------------------------------
            # CREAR VENTANA
            # ------------------------------------------------

            cv2.namedWindow(
                nombre_ventana,
                cv2.WINDOW_GUI_NORMAL
            )

            ventana_creada = True

            cv2.resizeWindow(
                nombre_ventana,
                600,
                300
            )

            cv2.moveWindow(
                nombre_ventana,
                0,
                0
            )

            # ------------------------------------------------
            # BUCLE DE VIDEO
            # ------------------------------------------------

            while (
                camara_activa_global
                and evento_abrir_camara.is_set()
                and not evento_salir_hilo_camara.is_set()
            ):

                ret, frame = cap.read()

                if not ret:
                    time.sleep(0.01)
                    continue

                # --------------------------------------------
                # DETECTAR CIERRE CON X
                # --------------------------------------------

                try:
                    visible = cv2.getWindowProperty(
                        nombre_ventana,
                        cv2.WND_PROP_VISIBLE
                    )

                    if visible < 1:
                        print("[CAM] Ventana cerrada con X")
                        camara_activa_global = False
                        evento_abrir_camara.clear()
                        break

                except Exception:
                    print("[CAM] Ventana OpenCV cerrada")
                    camara_activa_global = False
                    evento_abrir_camara.clear()
                    break

                # --------------------------------------------
                # AJUSTAR FRAME
                # --------------------------------------------

                frame = cv2.resize(
                    frame,
                    (600, 300),
                    interpolation=cv2.INTER_AREA
                )

                # --------------------------------------------
                # TEXTO OVERLAY
                # --------------------------------------------

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

                # --------------------------------------------
                # MOSTRAR FRAME
                # --------------------------------------------

                cv2.imshow(
                    nombre_ventana,
                    frame
                )

                tecla = cv2.waitKey(1) & 0xFF

                if tecla == ord("q"):

                    print("[CAM] Ventana cerrada con Q")

                    camara_activa_global = False
                    evento_abrir_camara.clear()

                    break

                time.sleep(0.005)

        finally:
            # ------------------------------------------------
            # LIBERAR DISPOSITIVO
            # ------------------------------------------------

            if cap is not None:
                try:
                    cap.release()
                except Exception as e:
                    print(
                        f"[CAM] Error liberando camara: {e}"
                    )

            # ------------------------------------------------
            # DESTRUIR VENTANA
            # ------------------------------------------------

            if ventana_creada:
                try:
                    cv2.destroyWindow(
                        nombre_ventana
                    )

                    # Procesar el evento de destruccion
                    cv2.waitKey(1)

                except Exception:
                    pass

            camara_activa_global = False
            evento_abrir_camara.clear()

            _actualizar_estado_kivy(False)

            print("[CAM] Camara liberada")

    # --------------------------------------------------------
    # SALIDA DEFINITIVA DEL HILO
    # --------------------------------------------------------

    try:
        cv2.destroyAllWindows()
        cv2.waitKey(1)
    except Exception:
        pass

    camara_activa_global = False

    print("[CAM] Hilo permanente terminado")


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
