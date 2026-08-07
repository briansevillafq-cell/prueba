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
            return float(input("Ingrese el tiempo en minutos: "))
        except ValueError:
            pass


def esta_en_rango(temp_actual, temp_objetivo, tolerancia=5.0):
    if temp_actual is None:
        return False
    return (temp_objetivo - tolerancia) <= temp_actual <= (temp_objetivo + tolerancia)


async def leer_temperatura(parrilla):
    try:
        res_placa = await parrilla.query("IN_PV_2")
        if res_placa is not None:
            val_placa = float(res_placa)
            if val_placa >= 0:
                return val_placa
    except Exception:
        pass
    return None


async def esperar_hasta_rango(parrilla, temperatura_final, tolerancia=5.0):
    if temperatura_final > 150:
        margen_rampa = 10.0
    elif temperatura_final > 80:
        margen_rampa = 6.0
    else:
        margen_rampa = 3.0

    print(
        f"\nIniciando calentamiento suave hacia {temperatura_final:.1f} C "
        f"(Margen rampa adaptable: +{margen_rampa:.1f} C)..."
    )

    while True:
        temp_actual = await leer_temperatura(parrilla)
        if temp_actual is not None:
            if temp_actual >= (temperatura_final - margen_rampa):
                await parrilla.set(equipment="heater", setpoint=temperatura_final)
                print(
                    f"Tramo final | Temp actual: {temp_actual:.1f} C | "
                    f"Setpoint final: {temperatura_final:.1f} C"
                )
                if esta_en_rango(temp_actual, temperatura_final, tolerancia):
                    print(f"\nTemperatura en rango alcanzada: {temp_actual:.1f} C. INICIANDO.")
                    return temp_actual
            else:
                setpoint_dinamico = temp_actual + margen_rampa
                await parrilla.set(equipment="heater", setpoint=setpoint_dinamico)
                print(
                    f"Rampa activa | Temp actual: {temp_actual:.1f} C | "
                    f"Setpoint dinamico: {setpoint_dinamico:.1f} C"
                )
        else:
            print("Intentando obtener lectura del sensor...")
        await asyncio.sleep(4)


async def mantener_temperatura(parrilla, temperatura, tiempo_minutos, tolerancia=2.0):
    tiempo_total_segundos = tiempo_minutos * 60
    tiempo_restante = tiempo_total_segundos
    loop = asyncio.get_running_loop()
    ultima_medicion = loop.time()

    print(f"\nIniciando temporizador de {tiempo_minutos:.2f} minutos.")

    while tiempo_restante > 0:
        temp_actual = await leer_temperatura(parrilla)

        if temp_actual is not None and not esta_en_rango(temp_actual, temperatura, tolerancia):
            print(f"\nTemperatura fuera del rango: {temp_actual:.1f} C.")
            print("Recuperando temperatura...")
            await esperar_hasta_rango(parrilla, temperatura, tolerancia)
            ultima_medicion = loop.time()
            print("Temperatura recuperada.\n")
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

        if temperatura > 150:
            margen_inicial = 10.0
        elif temperatura > 80:
            margen_inicial = 6.0
        else:
            margen_inicial = 3.0

        temp_inicial = await leer_temperatura(parrilla)
        sp_inicio = (temp_inicial + margen_inicial) if temp_inicial else 25.0
        if sp_inicio > temperatura:
            sp_inicio = temperatura

        await parrilla.set(equipment="heater", setpoint=sp_inicio)
        await asyncio.sleep(0.3)
        await parrilla.control(equipment="heater", on=True)
        await asyncio.sleep(0.5)

        print(f"Agitacion iniciada a {rpm:.0f} RPM.")
        print(f"Iniciando control dinamico de temperatura hacia {temperatura:.1f} C.")

        await esperar_hasta_rango(parrilla, temperatura, tolerancia=2.0)
        await mantener_temperatura(parrilla, temperatura, tiempo_minutos, tolerancia=2.0)

        print("\nTiempo de reaccion finalizado.")

    except (asyncio.CancelledError, KeyboardInterrupt):
        print("\nInterrupcion detectada (Ctrl+C). Iniciando apagado de emergencia...")
    except Exception as e:
        print(f"\nError durante el proceso: {e}")
    finally:
        await apagar_equipo(parrilla)


def iniciar_proceso():
    try:
        temperatura = obtener_temperatura()
        rpm = obtener_rpm()
        tiempo = obtener_tiempo()

        print("\nResumen:")
        print(f"Temperatura objetivo: {temperatura:.1f} C")
        print(f"Agitacion: {rpm:.0f} RPM")
        print(f"Tiempo efectivo: {tiempo:.2f} minutos")

        asyncio.run(ejecutar_parrilla("/dev/ttyUSB0", temperatura, rpm, tiempo))
        print("\nProceso terminado.")

    except KeyboardInterrupt:
        print("\nPrograma detenido manualmente por el usuario.")
    except Exception as e:
        print(f"\nNo se pudo completar el proceso: {e}")


if __name__ == "__main__":
    iniciar_proceso()
