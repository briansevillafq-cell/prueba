from gpiozero import OutputDevice
from time import sleep
pines = [17, 18, 27, 22, 23, 24, 25, 5, 6]

pumps = [
    OutputDevice(pin, active_high=False, initial_value=False)
    for pin in pines
]

start = input("Escribe 'si' para iniciar: ").strip().lower()

if start in ("si"):
    try:
        for i, pump in enumerate(pumps):
            pump.on()
            print(f"Pump {i + 1}_ON")
            sleep(2)

        print("Las bombas están encendidas")
        input("Presiona ENTER para apagar")

    except KeyboardInterrupt:
        print("\nProceso detenido")

    finally:
        for pump in pumps:
            pump.off()
            pump.close()

        print("Todas las bombas están apagadas")

else:
    for pump in pumps:
        pump.off()
        pump.close()

    print("Operación cancelada")
