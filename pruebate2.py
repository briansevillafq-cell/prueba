import asyncio
import cv2
import time
from ika.driver import Shaker

# Variables globales compartidas
texto_overlay = ""
color_overlay = (0, 255, 0)  # Verde por defecto (BGR)
camara_activa = True
ultima_temp_placa = None

# Configuración del parpadeo (en segundos)
INTERVALO_PARPADEO = 0.5 

def obtener_temperatura():
    while True:
        try:
            return float(input("Ingrese la temperatura deseada en C (0 a 400): "))
        except ValueError:
            pass

def obtener_rpm():
    while True:
        try:
            return float(input("Ingrese la velocidad de agitacion en RPM (300 a 3000): "))
        except ValueError:
            pass

def obtener_tiempo():
    while True:
        try:
            return float(input("Ingrese el tiempo en minutos: "))
        except ValueError:
            pass

async def leer_temperatura_placa(parrilla):
    """
    Lee unicamente el sensor interno de la placa calefactora real (IN_PV_1)
    """
    global ultima_temp_placa
    try:
        res_placa = await parrilla.query("IN_PV_1")
        if res_placa is not None:
            val_placa = float(res_placa)
            if val_placa >= 0:
                if ultima_temp_placa is not None:
                    # Filtro basico para lecturas erraticas drasticas
                    if abs(val_placa - ultima_temp_placa) > 20.0:
                        val_placa = ultima_temp_placa
                ultima_temp_placa = val_placa
                return val_placa
    except Exception:
        pass
    return None

async def bucle_camara():
    global texto_overlay, color_overlay, camara_activa

    # Configuracion de la camara USB V4L2 a 720p MJPEG
    cap = cv2.VideoCapture(0, cv2.CAP_V4L2)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
    cap.set(cv2.CAP_PROP_FPS, 30)

    if not cap.isOpened():
        print("Error: No se pudo abrir la camara /dev/video0")
        return

    print("Camara iniciada. Presione 'q' en la ventana de video para salir.")

    try:
        while camara_activa:
            ret, frame = cap.read()
            if not ret:
                await asyncio.sleep(0.01)
                continue

            if texto_overlay:
                # Lógica de parpadeo SOLO si el color es Rojo (estado OFF)
                mostrar_texto = True
                if color_overlay == (0, 0, 255): # Rojo BGR
                    if int(time.time() / INTERVALO_PARPADEO) % 2 == 0:
                        mostrar_texto = False

                if mostrar_texto:
                    # Recuadro adaptado al ancho del texto
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

            cv2.imshow("Monitoreo de Reaccion IKA", frame)

            # Salida manual con la tecla 'q'
            if cv2.waitKey(1) & 0xFF == ord("q"):
                camara_activa = False
                break

            await asyncio.sleep(0.001)
    finally:
        cap.release()
        cv2.destroyAllWindows()
        print("Camara cerrada correctamente.")

async def esperar_hasta_rango(parrilla, temperatura_final):
    global texto_overlay, color_overlay
    color_overlay = (0, 255, 0)  # Verde (fijo)

    print(f"\nEsperando a que la placa de la parrilla alcance {temperatura_final:.1f} C...")

    while True:
        temp_placa = await leer_temperatura_placa(parrilla)
        txt_placa = f"{temp_placa:.1f} C" if temp_placa is not None else "N/A"

        print(f"Calentando... | Temp Placa Real: {txt_placa} | Goal: {temperatura_final:.1f} C")
        texto_overlay = f"Temperatua Placa: {txt_placa}"

        if temp_placa is not None and temp_placa >= temperatura_final:
            print(f"\nTemperatura objetivo alcanzada en la placa: {temp_placa:.1f} C. INICIANDO CRONOMETRO.")
            return temp_placa

        await asyncio.sleep(2)

async def mantener_temperatura(parrilla, temperatura, tiempo_minutos):
    global texto_overlay, color_overlay
    color_overlay = (0, 255, 0)  # Verde (fijo)

    tiempo_total_segundos = tiempo_minutos * 60
    tiempo_restante = tiempo_total_segundos
    loop = asyncio.get_running_loop()
    ultima_medicion = loop.time()

    print(f"\nIniciando temporizador de {tiempo_minutos:.2f} minutos.")

    while tiempo_restante > 0:
        temp_placa = await leer_temperatura_placa(parrilla)

        momento_actual = loop.time()
        tiempo_transcurrido = momento_actual - ultima_medicion
        tiempo_restante -= tiempo_transcurrido
        ultima_medicion = momento_actual

        if tiempo_restante < 0:
            tiempo_restante = 0

        segundos_totales = int(tiempo_restante)
        if tiempo_restante > segundos_totales:
            segundos_totales += 1

        minutos_restantes = segundos_totales // 60
        segundos_restantes = segundos_totales % 60
        tiempo_transcurrido_valido = tiempo_total_segundos - tiempo_restante

        txt_placa = f"{temp_placa:.1f} C" if temp_placa is not None else "N/A"
        
        texto_overlay = f"Tiempo restante: {minutos_restantes:02d}:{segundos_restantes:02d} | Temperatua Placa: {txt_placa}"

        print(
            f"Tiempo restante: {minutos_restantes:02d}:{segundos_restantes:02d} | "
            f"Tiempo transcurrido: {int(tiempo_transcurrido_valido)} s | "
            f"Temp Placa Real: {txt_placa}"
        )

        if tiempo_restante > 0:
            tiempo_espera = min(2, tiempo_restante)
            await asyncio.sleep(tiempo_espera)

async def apagar_equipo(parrilla):
    """Apaga los elementos calefactor y agitador de forma segura."""
    print("\nApagando calefactor y agitador...")
    try:
        await parrilla.set(equipment="heater", setpoint=1.0)
        await parrilla.control(equipment="heater", on=False)
    except Exception as e:
        print(f"Error al apagar calentador: {e}")

    try:
        await parrilla.control(equipment="shaker", on=False)
    except Exception as e:
        print(f"Error al apagar agitador: {e}")

    print("Calefaccion y agitación APAGADAS.")

async def cronometro_post_reaccion(parrilla):
    """
    Actualiza el texto global con la leyenda explícita '[OFF] Tiempo sin calentar y agitar: +MM:SS'
    en ROJO INTERMITENTE.
    """
    global texto_overlay, color_overlay, camara_activa
    color_overlay = (0, 0, 255)  # Rojo BGR (activa parpadeo)
    inicio_post = time.time()

    print("\nIniciando cronometro post-reaccion INTERMITENTE en rojo.")
    print("Presione 'q' en la ventana de video para finalizar por completo.")

    while camara_activa:
        tiempo_inactivo = int(time.time() - inicio_post)
        horas = tiempo_inactivo // 3600
        minutos = (tiempo_inactivo % 3600) // 60
        segundos = tiempo_inactivo % 60

        if horas > 0:
            str_tiempo = f"{horas:02d}:{minutos:02d}:{segundos:02d}"
        else:
            str_tiempo = f"{minutos:02d}:{segundos:02d}"

        # Texto explícito solicitado
        texto_overlay = f"[OFF] Tiempo sin calentar y agitar: +{str_tiempo}"
        
        await asyncio.sleep(1)

async def ejecutar_parrilla(puerto, temperatura, rpm, tiempo_minutos):
    parrilla = Shaker(address=puerto)
    try:
        print("\nLimpiando estado del equipo...")
        try:
            await parrilla.set(equipment="heater", setpoint=1.0)
            await parrilla.control(equipment="heater", on=False)
            await parrilla.control(equipment="shaker", on=False)
            await asyncio.sleep(0.5)
        except Exception:
            pass

        print("Configurando agitacion e inicio de calentamiento...")
        await parrilla.set(equipment="shaker", setpoint=rpm)
        await asyncio.sleep(0.3)
        await parrilla.control(equipment="shaker", on=True)
        await asyncio.sleep(0.3)

        await parrilla.set(equipment="heater", setpoint=temperatura)
        await asyncio.sleep(0.3)
        await parrilla.control(equipment="heater", on=True)
        await asyncio.sleep(0.5)

        print(f"Agitacion iniciada a {rpm:.0f} RPM.")
        print(f"Setpoint fijo en {temperatura:.1f} C enviado. Control asignado a la parrilla.")

        await esperar_hasta_rango(parrilla, temperatura)
        await mantener_temperatura(parrilla, temperatura, tiempo_minutos)

        print("\nTiempo de reaccion finalizado.")

    except (asyncio.CancelledError, KeyboardInterrupt):
        print("\nInterrupcion detectada (Ctrl+C). Iniciando apagado...")
    except Exception as e:
        print(f"\nError durante el proceso: {e}")
    finally:
        # Apaga calefacción y agitación
        await apagar_equipo(parrilla)
        # Mantiene la cámara activa con el mensaje explícito en rojo intermitente
        await cronometro_post_reaccion(parrilla)

async def programa_principal(puerto, temperatura, rpm, tiempo):
    task_camara = asyncio.create_task(bucle_camara())
    await ejecutar_parrilla(puerto, temperatura, rpm, tiempo)
    await task_camara

def iniciar_proceso():
    try:
        temperatura = obtener_temperatura()
        rpm = obtener_rpm()
        tiempo = obtener_tiempo()

        print("\nResumen:")
        print(f"Temperatura objetivo: {temperatura:.1f} C")
        print(f"Agitacion: {rpm:.0f} RPM")
        print(f"Tiempo efectivo: {tiempo:.2f} minutos")

        asyncio.run(programa_principal("/dev/ttyUSB0", temperatura, rpm, tiempo))
        print("\nProceso terminado.")

    except KeyboardInterrupt:
        print("\nPrograma detenido manualmente por el usuario.")
    except Exception as e:
        print(f"\nNo se pudo completar el proceso: {e}")

if __name__ == "__main__":
    iniciar_proceso()
