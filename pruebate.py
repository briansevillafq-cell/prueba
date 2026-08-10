import asyncio
import cv2
from ika.driver import Shaker

# Variable global compartida para el texto sobre el video
texto_overlay = ""
camara_activa = True
ultima_temperatura_valida = None

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

def esta_en_rango(temp_actual, temp_objetivo, tolerancia=3.0):
    if temp_actual is None:
        return False
    return (temp_objetivo - tolerancia) <= temp_actual <= (temp_objetivo + tolerancia)

async def leer_temperatura(parrilla):
    global ultima_temperatura_valida
    try:
        res_placa = await parrilla.query("IN_PV_2")
        if res_placa is not None:
            val_placa = float(res_placa)
            if val_placa >= 0:
                if ultima_temperatura_valida is not None:
                    if abs(val_placa - ultima_temperatura_valida) > 15.0:
                        print(f"Advertencia: Lectura erratica ignorada ({val_placa:.1f} C). Se conserva {ultima_temperatura_valida:.1f} C")
                        return ultima_temperatura_valida
                ultima_temperatura_valida = val_placa
                return val_placa
    except Exception:
        pass
    return None

async def bucle_camara():
    global texto_overlay, camara_activa

    # Configuracion de la camara USB V4L2 a 720p MJPEG
    cap = cv2.VideoCapture(0, cv2.CAP_V4L2)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
    cap.set(cv2.CAP_PROP_FPS, 30)

    if not cap.isOpened():
        print("Error: No se pudo abrir la camara /dev/video0")
        return

    print("Camara iniciada a 720p MJPEG @ 30 FPS en pantalla.")

    try:
        while camara_activa:
            ret, frame = cap.read()
            if not ret:
                await asyncio.sleep(0.01)
                continue

            # El texto SOLO se dibuja si la variable contiene un mensaje activo
            if texto_overlay:
                cv2.rectangle(frame, (20, 20), (580, 75), (0, 0, 0), -1)

                # Si es una alerta de sobretemperatura usa color rojo
                color_texto = (0, 0, 255) if "ALERTA" in texto_overlay else (0, 255, 0)

                cv2.putText(
                    frame,
                    texto_overlay,
                    (30, 58),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.8,
                    color_texto,
                    2,
                    cv2.LINE_AA,
                )

            cv2.imshow("Monitoreo de Reaccion IKA", frame)

            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

            await asyncio.sleep(0.001)
    finally:
        cap.release()
        cv2.destroyAllWindows()
        print("Camara cerrada correctamente.")

async def enfriar_por_sobretemperatura(parrilla, temperatura_limite):
    global texto_overlay
    print(f"\nIniciando enfriamiento pasivo hasta caer por debajo de {temperatura_limite:.1f} C...")
    
    # Fijar el setpoint a 1.0 C (minimo valido) para forzar al PID interno de IKA a 0% de potencia
    try:
        await parrilla.set(equipment="heater", setpoint=1.0)
    except Exception as e:
        print(f"Advertencia al fijar setpoint minimo a 1.0 C: {e}")

    await parrilla.control(equipment="heater", on=False)
    
    while True:
        temp_actual = await leer_temperatura(parrilla)
        if temp_actual is not None:
            texto_overlay = f"ENFRIANDO: {temp_actual:.1f} C"
            print(f"Enfriando pasivamente... Temp actual: {temp_actual:.1f} C (Objetivo: < {temperatura_limite:.1f} C)")
            if temp_actual <= temperatura_limite:
                print("Temperatura restablecida dentro de parametros seguros.")
                texto_overlay = ""
                break
        await asyncio.sleep(2)  # Consulta cada 2 segundos

async def esperar_hasta_rango(parrilla, temperatura_final, tolerancia=3.0):
    global texto_overlay
    texto_overlay = ""  # Oculta el mensaje en la camara mientras calienta

    print(f"\nIniciando calentamiento controlado hacia {temperatura_final:.1f} C...")

    while True:
        temp_actual = await leer_temperatura(parrilla)
        if temp_actual is not None:

            # 1. PROTECCION DE SEGURIDAD EN SEGUNDO PLANO: No superar +15 C sobre el objetivo
            if temp_actual > (temperatura_final + 15.0):
                texto_overlay = "ALERTA: SOBRETEMPERATURA (+15C)"
                print(
                    f"\nALERTA DE SEGURIDAD: Temp actual ({temp_actual:.1f} C) "
                    f"supero por 15 C el objetivo ({temperatura_final:.1f} C). Apagando calentador..."
                )
                await enfriar_por_sobretemperatura(parrilla, temperatura_final + 2.0)
                continue

            # 2. CONTROL DE RAMPA DINAMICA A +2.0 C Y APAGADO PREVENTIVO AL FALTAR 5 C
            diferencia = temperatura_final - temp_actual
            if diferencia > 5.0:
                # Rampa activa con avance de +2.0 C sobre la lectura real
                setpoint_dinamico = min(temp_actual + 2.0, temperatura_final)
                await parrilla.set(equipment="heater", setpoint=setpoint_dinamico)
                await parrilla.control(equipment="heater", on=True)
            else:
                # Apagado preventivo directo al faltar 5 C o menos para aprovechar la inercia
                setpoint_dinamico = temperatura_final
                await parrilla.set(equipment="heater", setpoint=1.0)
                await parrilla.control(equipment="heater", on=False)

            print(
                f"Rampa activa | Temp actual: {temp_actual:.1f} C | "
                f"Setpoint enviado: {setpoint_dinamico:.1f} C"
            )

            # 3. CONDICION DE INICIO: Inicia SOLO cuando alcanza o supera la temperatura deseada
            if temp_actual >= temperatura_final:
                print(
                    f"\nTemperatura objetivo alcanzada/superada: {temp_actual:.1f} C. "
                    f"INICIANDO CRONOMETRO."
                )
                return temp_actual
        else:
            print("Error: Lectura de sensor invalida (None). Apagando calentador por seguridad...")
            await parrilla.set(equipment="heater", setpoint=1.0)
            await parrilla.control(equipment="heater", on=False)
        await asyncio.sleep(2)  # Consulta cada 2 segundos

async def mantener_temperatura(parrilla, temperatura, tiempo_minutos, tolerancia=3.0):
    global texto_overlay
    tiempo_total_segundos = tiempo_minutos * 60
    tiempo_restante = tiempo_total_segundos
    loop = asyncio.get_running_loop()
    ultima_medicion = loop.time()

    print(f"\nIniciando temporizador de {tiempo_minutos:.2f} minutos.")

    while tiempo_restante > 0:
        temp_actual = await leer_temperatura(parrilla)

        if temp_actual is not None:
            # Proteccion de segundo plano (+15 C)
            if temp_actual > (temperatura + 15.0):
                texto_overlay = "ALERTA: SOBRETEMPERATURA (+15C)"
                print(
                    f"\nALERTA SEGURIDAD: Temp actual ({temp_actual:.1f} C) "
                    f"excedio por 15 C el objetivo. Pausando cronometro y apagando calentador..."
                )
                await enfriar_por_sobretemperatura(parrilla, temperatura + 2.0)
                ultima_medicion = loop.time()
                print("Temperatura recuperada.\n")
                continue

            # Verificacion de tolerancia inferior para mantener cronometro
            if temp_actual < (temperatura - tolerancia):
                texto_overlay = ""
                print(f"\nTemperatura cayo por debajo del rango: {temp_actual:.1f} C.")
                print("Recuperando temperatura...")
                await esperar_hasta_rango(parrilla, temperatura, tolerancia=tolerancia)
                ultima_medicion = loop.time()
                print("Temperatura recuperada.\n")
                continue

            # Mantener setpoint en 1 C si sobrepasa o inyectar calor suave (+0.8 C) si cae
            if temp_actual > temperatura:
                await parrilla.set(equipment="heater", setpoint=1.0)
                await parrilla.control(equipment="heater", on=False)
            else:
                sp_mantener = min(temp_actual + 0.8, temperatura)
                await parrilla.set(equipment="heater", setpoint=sp_mantener)
                await parrilla.control(equipment="heater", on=True)

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

        texto_overlay = f"Tiempo restante: {minutos_restantes:02d}:{segundos_restantes:02d}"

        temp_mostrar = temp_actual if temp_actual is not None else 0.0
        print(
            f"Tiempo restante: {minutos_restantes:02d}:{segundos_restantes:02d} | "
            f"Tiempo transcurrido: {int(tiempo_transcurrido_valido)} s | "
            f"Temp actual: {temp_mostrar:.1f} C"
        )

        if tiempo_restante > 0:
            tiempo_espera = min(2, tiempo_restante)  # Consulta cada 2 segundos
            await asyncio.sleep(tiempo_espera)

    texto_overlay = "REACCION FINALIZADA"
    await asyncio.sleep(3)
    texto_overlay = ""

async def apagar_equipo(parrilla):
    global camara_activa, texto_overlay
    texto_overlay = ""
    camara_activa = False

    print("\nApagando equipo y liberando control remoto...")
    try:
        await parrilla.set(equipment="heater", setpoint=1.0)
        await parrilla.control(equipment="heater", on=False)
    except Exception as e:
        print(f"Error al apagar calentador: {e}")

    try:
        await parrilla.control(equipment="shaker", on=False)
    except Exception as e:
        print(f"Error al apagar agitador: {e}")

    print("Equipo apagado correctamente.")

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

        print("Configurando agitacion inicial...")
        await parrilla.set(equipment="shaker", setpoint=rpm)
        await asyncio.sleep(0.3)
        await parrilla.control(equipment="shaker", on=True)
        await asyncio.sleep(0.3)

        temp_inicial = await leer_temperatura(parrilla)
        if temp_inicial is not None:
            sp_inicio = min((temp_inicial + 2.0), temperatura)
        else:
            sp_inicio = 25.0

        await parrilla.set(equipment="heater", setpoint=sp_inicio)
        await asyncio.sleep(0.3)
        await parrilla.control(equipment="heater", on=True)
        await asyncio.sleep(0.5)

        print(f"Agitacion iniciada a {rpm:.0f} RPM.")
        print(f"Iniciando control dinamico fino hacia {temperatura:.1f} C.")

        await esperar_hasta_rango(parrilla, temperatura, tolerancia=3.0)
        await mantener_temperatura(parrilla, temperatura, tiempo_minutos, tolerancia=3.0)

        print("\nTiempo de reaccion finalizado.")

    except (asyncio.CancelledError, KeyboardInterrupt):
        print("\nInterrupcion detectada (Ctrl+C). Iniciando apagado de emergencia...")
    except Exception as e:
        print(f"\nError durante el proceso: {e}")
    finally:
        await apagar_equipo(parrilla)

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
