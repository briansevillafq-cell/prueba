import asyncio
from ika.driver import Shaker


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
            return float(input("Ingrese el tiempo de mantenimiento en minutos: "))
        except ValueError:
            pass


def esta_en_rango(temp_actual, temp_objetivo, tolerancia=5.0):
    if temp_actual is None:
        return False
    return (temp_objetivo - tolerancia) <= temp_actual <= (temp_objetivo + tolerancia)


async def leer_temperatura(parrilla):
    try:
        if hasattr(parrilla, "READ_ACTUAL_TEMPERATURE"):
            val = await parrilla.query(parrilla.READ_ACTUAL_TEMPERATURE)
            if val is not None:
                return float(val)
    except NotImplementedError:
        pass
    except Exception as e:
        print(f"Error de lectura directa [{type(e).__name__}]: {repr(e)}")

    try:
        info = await parrilla.get()
        val = info.get("temp", {}).get("actual")
        if val is not None:
            return float(val)
    except Exception as e:
        print(f"Error de lectura get [{type(e).__name__}]: {repr(e)}")

    return None


async def esperar_hasta_rango(parrilla, temperatura, tolerancia=5.0):
    print("\nEsperando a llegar a la temperatura...")
    while True:
        temp_actual = await leer_temperatura(parrilla)
        if temp_actual is not None:
            print(f"Calentando | Temp actual: {temp_actual:.1f} C | Objetivo: {temperatura:.1f} +/- {tolerancia:.1f} C")
            if esta_en_rango(temp_actual, temperatura, tolerancia):
                print(f"\nTemperatura en rango alcanzada: {temp_actual:.1f} C. Iniciando temporizador...")
                return temp_actual
        else:
            print("Intentando obtener lectura del sensor...")
        await asyncio.sleep(3)


async def mantener_temperatura(parrilla, temperatura, tiempo_minutos, tolerancia=5.0):
    tiempo_total_segundos = tiempo_minutos * 60
    tiempo_restante = tiempo_total_segundos
    loop = asyncio.get_running_loop()
    ultima_medicion = loop.time()

    print(f"\nIniciando temporizador de {tiempo_minutos:.2f} minutos.")

    while tiempo_restante > 0:
        temp_actual = await leer_temperatura(parrilla)

        if temp_actual is not None and not esta_en_rango(temp_actual, temperatura, tolerancia):
            print(f"\nTemperatura fuera del rango: {temp_actual:.1f} C.")
            print("Recuperando temperatura. Este tiempo no sera descontado.")
            await esperar_hasta_rango(parrilla, temperatura, tolerancia)
            ultima_medicion = loop.time()
            print("Temperatura recuperada. Continuando el temporizador.\n")
            continue

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

        temp_mostrar = temp_actual if temp_actual is not None else 0.0
        print(
            f"Tiempo restante: {minutos_restantes:02d}:{segundos_restantes:02d} | "
            f"Tiempo transcurrido: {int(tiempo_transcurrido_valido)} s | "
            f"Temp actual: {temp_mostrar:.1f} C"
        )

        if tiempo_restante > 0:
            tiempo_espera = min(5, tiempo_restante)
            await asyncio.sleep(tiempo_espera)


async def apagar_equipo(parrilla):
    print("\nApagando equipo y liberando control remoto...")
    try:
        await parrilla.set(equipment="heater", setpoint=0)
        await parrilla.set(equipment="shaker", setpoint=0)
        await asyncio.sleep(0.5)
        await parrilla.control(equipment="heater", on=False)
        await parrilla.control(equipment="shaker", on=False)
        print("Equipo apagado y setpoints reestablecidos a 0.")
    except Exception as e:
        print(f"Error al apagar el equipo: {e}")


async def ejecutar_parrilla(puerto, temperatura, rpm, tiempo_minutos):
    parrilla = Shaker(address=puerto)
    try:
        print("\nLimpiando estado del equipo...")
        try:
            await parrilla.control(equipment="heater", on=False)
            await parrilla.control(equipment="shaker", on=False)
            await asyncio.sleep(1.0)
        except Exception:
            pass

        print("Configurando equipo...")
        await parrilla.set(equipment="shaker", setpoint=rpm)
        await asyncio.sleep(0.5)
        await parrilla.set(equipment="heater", setpoint=temperatura)
        await asyncio.sleep(0.5)

        await parrilla.control(equipment="shaker", on=True)
        await asyncio.sleep(0.5)
        await parrilla.control(equipment="heater", on=True)
        await asyncio.sleep(1.0)

        print(f"Agitacion iniciada a {rpm:.0f} RPM.")
        print(f"Calentando hasta {temperatura:.1f} +/- 5.0 C.")

        await esperar_hasta_rango(parrilla, temperatura, tolerancia=5.0)
        await mantener_temperatura(parrilla, temperatura, tiempo_minutos, tolerancia=5.0)

        print("\nTiempo de mantenimiento finalizado.")

    except asyncio.CancelledError:
        print("\nInterrupcion detectada. Iniciando apagado de seguridad...")
        raise
    except Exception as e:
        print(f"\nError durante el proceso: {e}")
        raise
    finally:
        await apagar_equipo(parrilla)


def iniciar_proceso():
    try:
        temperatura = obtener_temperatura()
        rpm = obtener_rpm()
        tiempo = obtener_tiempo()

        print("\nResumen:")
        print(f"Temperatura: {temperatura:.1f} +/- 5.0 C")
        print(f"Agitacion: {rpm:.0f} RPM")
        print(f"Tiempo efectivo: {tiempo:.2f} minutos")

        asyncio.run(ejecutar_parrilla("/dev/ttyUSB0", temperatura, rpm, tiempo))
        print("\nProceso terminado con exito.")

    except KeyboardInterrupt:
        print("\nPrograma detenido manualmente. Salida segura realizada.")
    except Exception as e:
        print(f"\nNo se pudo completar el proceso: {e}")


if __name__ == "__main__":
    iniciar_proceso()
