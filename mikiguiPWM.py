import asyncio
import threading
import time
import pruebate3

from actuarsPWM import cleanUp, pumpsWork, pumpsWorkTC
from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import Color, Ellipse
from kivy.lang import Builder
from kivy.properties import BooleanProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.textinput import TextInput
from kivy.uix.togglebutton import ToggleButton

Window.size = (1135, 665)
Window.resizable = False
Window.title = "MIK-I"

class MikiScreen(FloatLayout):

    camara_activa = BooleanProperty(False)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.create_pumps()
        self.selection_mood = ""
        self.stir_stage = None
        self.used_pines = {}
        self.usb_port = "/dev/ttyUSB0"

        # Evita que un mismo clic/evento de CAM se procese dos veces
        self._ultimo_toggle_camara = 0.0

    def toggle_camera(self):

        ahora = time.monotonic()

        if ahora - self._ultimo_toggle_camara < 0.8:
            print("[CAM UI] Evento duplicado ignorado")
            return

        self._ultimo_toggle_camara = ahora

        if pruebate3.camara_activa_global:
            print("[CAM UI] Apagando cámara")
            pruebate3.detener_camara()
            self.camara_activa = False
            return

        print("Encendiendo cámara")

        pruebate3.texto_overlay = "EN ESPERA"
        pruebate3.color_overlay = (0, 255, 0)

        iniciada = pruebate3.iniciar_camara(self)

        if iniciada:
            self.camara_activa = True

    def stirring(self, temp, rpm, time_wait, time_min):
        """Ejecuta IKA desde pruebate3.py."""

        hilo_cam = pruebate3.hilo_camara_global

        if (
            not pruebate3.camara_activa_global
            and (
                hilo_cam is None
                or not hilo_cam.is_alive()
            )
        ):
            pruebate3.iniciar_camara(self)

        self.camara_activa = pruebate3.camara_activa_global

        def run_async():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(
                pruebate3.ejecutar_parrilla(
                    self.usb_port, temp, rpm, time_min
                )
            )

        threading.Thread(target=run_async, daemon=True).start()

    def update_interface(self, result):
        print(f"Principal thread running: {result}")

    def create_pumps(self):
        for i in range(4):
            with self.canvas:
                Color(0, 0, 0, 1)
                Ellipse(pos=(259 + 220 * i, 430), size=(150, 152))
                Color(0, 194, 0, 0.6)
                Ellipse(pos=(260 + 220 * i, 432), size=(148, 148))
                Color(3, 0.55, 8, 0.63)
                Ellipse(pos=(326 + 221 * i, 499), size=(13, 13))

            self.add_widget(
                Label(
                    text=f"Pump {i + 1}",
                    size_hint=(None, None),
                    size=(100, 30),
                    pos=(285 + 220 * i, 585),
                    color=(0, 0, 0, 1),
                    font_size=20,
                )
            )

            self.add_widget(
                Label(
                    text="Vol (ml): ",
                    size_hint=(None, None),
                    size=(100, 30),
                    pos=(238 + 225 * i, 385),
                    color=(0, 0, 0, 1),
                    font_size=18,
                )
            )

        for j in range(5):
            x = 110 + 203 * j
            y = 170

            with self.canvas:
                Color(0, 0, 0, 1)
                Ellipse(pos=(x + 24, y + 5), size=(150, 152))
                Color(0, 194, 0, 0.6)
                Ellipse(pos=(x + 25, y + 7), size=(148, 148))
                Color(3, 0.55, 8, 0.63)
                Ellipse(pos=(x + 92, y + 73), size=(13, 13))

            self.add_widget(
                Label(
                    text=f"Pump {j + 5}",
                    size_hint=(None, None),
                    size=(90, 30),
                    pos=(152 + 206 * j, 332),
                    color=(0, 0, 0, 1),
                    font_size=20,
                )
            )

            self.add_widget(
                Label(
                    text="Vol (ml): ",
                    size_hint=(None, None),
                    size=(30, 30),
                    pos=(155 + 204 * j, 133),
                    color=(0, 0, 0, 1),
                    font_size=18,
                )
            )

        with self.canvas:
            Color(0, 0, 0, 1)
            Ellipse(pos=(49, 428), size=(150, 152))
            Color(1, 1, 5, 0.95)
            Ellipse(pos=(50, 430), size=(148, 148))
            Color(12, 0.35, 0.2, 0.15)
            Ellipse(pos=(119, 499), size=(13, 13))

        labels = [
            ("Service Pump", (150, 300), (45, 445), 20),
            ("Vol (ml): ", (150, 3), (4.5, 400), 18),
            ("Addition", (150, 3), (220, 80), 18),
            ("Heat/Stir", (150, 3), (560, 80), 18),
            ("temp (°C)", (100, 30), (480, 58), 14),
            ("rpm", (100, 30), (560, 58), 14),
            ("time (min)", (100, 30), (640, 58), 14),
        ]

        for text, size, pos, fsize in labels:
            self.add_widget(
                Label(
                    text=text,
                    size_hint=(None, None),
                    size=size,
                    pos=pos,
                    color=(0, 0, 0, 1),
                    font_size=fsize,
                )
            )

    def set_stirringStage(self, value, active):
        if active:
            self.stir_stage = value

    def set_moodWork(self, togglebutton):
        if togglebutton.state == "down":
            self.selection_mood = togglebutton.text

    def clr_text(self):
        for n in [
            self.ids.checkno,
            self.ids.checkyes,
            self.ids.parallel,
            self.ids.inorder,
        ]:
            n.state = "normal"

        self.selection_mood = ""

        for i in range(10):
            self.ids[f"vol{i}"].text = "0"

        self.ids.temp_input.text = "0"
        self.ids.rpm_input.text = "0"
        self.ids.stir_time.text = "0"
        self.ids.checkno.active = True

    def reaction_finished(self):
        popup = Popup(
            title="Info",
            content=Label(
                text="Reaction finished",
                font_size=18
            ),
            size_hint=(None, None),
            size=(300, 150),
        )

        popup.open()

        Clock.schedule_once(
            lambda dt: self.ask_clean_tubes(),
            5
        )

    def ask_clean_tubes(self):
        layout = BoxLayout(
            orientation="vertical",
            spacing=10,
            padding=10
        )

        layout.add_widget(
            Label(
                text="Do you want to clean the tubes?",
                font_size=18
            )
        )

        btn_layout = BoxLayout(
            spacing=10,
            size_hint_y=None,
            height=40
        )

        btn_yes = Button(text="Yes")
        btn_no = Button(text="No")

        btn_layout.add_widget(btn_yes)
        btn_layout.add_widget(btn_no)

        layout.add_widget(btn_layout)

        popup = Popup(
            title="Clean Tubes",
            content=layout,
            size_hint=(None, None),
            size=(300, 180),
            auto_dismiss=False,
        )

        def on_yes(instance):
            self.flow = {
                14: 28,
                17: 0.2481,
                27: 0.1892,
                22: 0.2099,
                13: 0.2285,
                2: 0.2290,
                18: 0.2290,
                25: 0.2409,
                4: 0.2290,
                7: 0.2290,
            }

            popup.dismiss()

            cleanUp(
                True,
                self.used_pines,
                self.flow
            )

            self.ids.srtButton.disabled = False

        def on_no(instance):
            popup.dismiss()
            self.ids.srtButton.disabled = False

        btn_yes.bind(on_release=on_yes)
        btn_no.bind(on_release=on_no)

        popup.open()

    def _run_reaction(self, include_load_time):

        self.pps = [
            14,
            17,
            27,
            22,
            13,
            2,
            18,
            25,
            4,
            7,
        ]

        self.strpins = [
            15,
            23,
            5,
            6,
            26,
            16,
            20,
            21,
            1,
            8,
            24,
            12,
        ]

        self.flow = {
            14: 28,
            17: 0.2481,
            27: 0.1892,
            22: 0.2099,
            13: 0.2285,
            2: 0.2290,
            18: 0.2290,
            25: 0.2409,
            4: 0.2290,
            7: 0.2290,
        }

        self.tc = [
            2,
            16,
            17,
            18,
            17,
            18,
            17,
            18,
            19,
            18,
        ]

        self.used_pines = {}

        def wmk():
            self.tempstr = (
                int(self.ids.temp_input.text)
                if self.ids.temp_input.text.strip()
                else 0
            )

            self.rpmstr = (
                int(self.ids.rpm_input.text)
                if self.ids.rpm_input.text.strip()
                else 0
            )

            self.tmstr = (
                int(self.ids.stir_time.text)
                if self.ids.stir_time.text.strip()
                else 0
            )

            self.vs = (
                int(self.ids.vol0.text)
                if self.ids.vol0.text.strip()
                else 0
            )

            self.v1 = (
                int(self.ids.vol1.text)
                if self.ids.vol1.text.strip()
                else 0
            )

            self.v2 = (
                int(self.ids.vol2.text)
                if self.ids.vol2.text.strip()
                else 0
            )

            self.v3 = (
                int(self.ids.vol3.text)
                if self.ids.vol3.text.strip()
                else 0
            )

            self.v4 = (
                int(self.ids.vol4.text)
                if self.ids.vol4.text.strip()
                else 0
            )

            self.v5 = (
                int(self.ids.vol5.text)
                if self.ids.vol5.text.strip()
                else 0
            )

            self.v6 = (
                int(self.ids.vol6.text)
                if self.ids.vol6.text.strip()
                else 0
            )

            self.v7 = (
                int(self.ids.vol7.text)
                if self.ids.vol7.text.strip()
                else 0
            )

            self.v8 = (
                int(self.ids.vol8.text)
                if self.ids.vol8.text.strip()
                else 0
            )

            self.v9 = (
                int(self.ids.vol9.text)
                if self.ids.vol9.text.strip()
                else 0
            )

            volumes = [
                self.vs,
                self.v1,
                self.v2,
                self.v3,
                self.v4,
                self.v5,
                self.v6,
                self.v7,
                self.v8,
                self.v9,
            ]

            def load_time(index):
                return self.tc[index] if include_load_time else 0

            def pump_time(index):
                return (
                    volumes[index] / self.flow[self.pps[index]]
                    + load_time(index)
                )

            def flow_time(index):
                return volumes[index] / self.flow[self.pps[index]]

            def td_wait(index):

                Pmp2 espera a Pmp1.
                Desde Pmp3 se conserva también el término de la Service Pump,
                tal como estaba definido en la lógica original.
                """
                if index == 2:
                    return flow_time(1)

                return flow_time(0) + sum(
                    flow_time(i)
                    for i in range(1, index)
                )

            stir_wait_1 = sum(
                pump_time(i) for i in range(1, 10)
            )
            stir_wait_2 = sum(
                pump_time(i) for i in range(2, 10)
            )
            stir_wait_3 = sum(
                pump_time(i) for i in range(3, 10)
            )

            def stir1():
                if self.stir_stage == 1:
                    self.stirring(
                        self.tempstr,
                        self.rpmstr,
                        stir_wait_1 if self.tmstr != 0 else 1,
                        self.tmstr,
                    )

            def stir2():
                if self.stir_stage == 2:
                    self.stirring(
                        self.tempstr,
                        self.rpmstr,
                        stir_wait_2 if self.tmstr != 0 else 1,
                        self.tmstr,
                    )

            def stir3():
                if self.stir_stage == 3:
                    self.stirring(
                        self.tempstr,
                        self.rpmstr,
                        stir_wait_3 if self.tmstr != 0 else 1,
                        self.tmstr,
                    )

            def Pmps():
                if self.vs != 0:
                    pumpsWork(
                        0,
                        int(self.pps[0]),
                        int(self.strpins[0]),
                        pump_time(0),
                    )
                    self.used_pines[0] = (
                        self.pps[0],
                        self.strpins[0],
                    )

            def Pmp1():
                if self.v1 != 0:
                    pumpsWork(
                        1,
                        int(self.pps[1]),
                        int(self.strpins[1]),
                        pump_time(1),
                    )
                    self.used_pines[1] = (
                        self.pps[1],
                        self.strpins[1],
                    )

            def Pmp2():
                if self.v2 != 0:
                    pumpsWork(
                        2,
                        int(self.pps[2]),
                        int(self.strpins[2]),
                        pump_time(2),
                    )
                    self.used_pines[2] = (
                        self.pps[2],
                        self.strpins[2],
                    )

            def Pmp3():
                if self.v3 != 0:
                    pumpsWork(
                        3,
                        int(self.pps[3]),
                        int(self.strpins[3]),
                        pump_time(3),
                    )
                    self.used_pines[3] = (
                        self.pps[3],
                        self.strpins[3],
                    )

            def Pmp4():
                if self.v4 != 0:
                    pumpsWork(
                        4,
                        int(self.pps[4]),
                        int(self.strpins[4]),
                        pump_time(4),
                    )
                    self.used_pines[4] = (
                        self.pps[4],
                        self.strpins[4],
                    )

            def Pmp5():
                if self.v5 != 0:
                    pumpsWork(
                        5,
                        int(self.pps[5]),
                        int(self.strpins[5]),
                        pump_time(5),
                    )
                    self.used_pines[5] = (
                        self.pps[5],
                        self.strpins[5],
                    )

            def Pmp6():
                if self.v6 != 0:
                    pumpsWork(
                        6,
                        int(self.pps[6]),
                        int(self.strpins[6]),
                        pump_time(6),
                    )
                    self.used_pines[6] = (
                        self.pps[6],
                        self.strpins[6],
                    )

            def Pmp7():
                if self.v7 != 0:
                    pumpsWork(
                        7,
                        int(self.pps[7]),
                        int(self.strpins[7]),
                        pump_time(7),
                    )
                    self.used_pines[7] = (
                        self.pps[7],
                        self.strpins[7],
                    )

            def Pmp8():
                if self.v8 != 0:
                    pumpsWork(
                        8,
                        int(self.pps[8]),
                        int(self.strpins[8]),
                        pump_time(8),
                    )
                    self.used_pines[8] = (
                        self.pps[8],
                        self.strpins[8],
                    )

            def Pmp9():
                if self.v9 != 0:
                    pumpsWork(
                        9,
                        int(self.pps[9]),
                        int(self.strpins[9]),
                        pump_time(9),
                    )
                    self.used_pines[9] = (
                        self.pps[9],
                        self.strpins[9],
                    )

            def Pmp2TD():
                if self.v2 != 0:
                    pumpsWorkTC(
                        2,
                        int(self.pps[2]),
                        int(self.strpins[2]),
                        td_wait(2),
                        pump_time(2),
                    )
                    self.used_pines[2] = (
                        self.pps[2],
                        self.strpins[2],
                    )

            def Pmp3TD():
                if self.v3 != 0:
                    pumpsWorkTC(
                        3,
                        int(self.pps[3]),
                        int(self.strpins[3]),
                        td_wait(3),
                        pump_time(3),
                    )
                    self.used_pines[3] = (
                        self.pps[3],
                        self.strpins[3],
                    )

            def Pmp4TD():
                if self.v4 != 0:
                    pumpsWorkTC(
                        4,
                        int(self.pps[4]),
                        int(self.strpins[4]),
                        td_wait(4),
                        pump_time(4),
                    )
                    self.used_pines[4] = (
                        self.pps[4],
                        self.strpins[4],
                    )

            def Pmp5TD():
                if self.v5 != 0:
                    pumpsWorkTC(
                        5,
                        int(self.pps[5]),
                        int(self.strpins[5]),
                        td_wait(5),
                        pump_time(5),
                    )
                    self.used_pines[5] = (
                        self.pps[5],
                        self.strpins[5],
                    )

            def Pmp6TD():
                if self.v6 != 0:
                    pumpsWorkTC(
                        6,
                        int(self.pps[6]),
                        int(self.strpins[6]),
                        td_wait(6),
                        pump_time(6),
                    )
                    self.used_pines[6] = (
                        self.pps[6],
                        self.strpins[6],
                    )

            def Pmp7TD():
                if self.v7 != 0:
                    pumpsWorkTC(
                        7,
                        int(self.pps[7]),
                        int(self.strpins[7]),
                        td_wait(7),
                        pump_time(7),
                    )
                    self.used_pines[7] = (
                        self.pps[7],
                        self.strpins[7],
                    )

            def Pmp8TD():
                if self.v8 != 0:
                    pumpsWorkTC(
                        8,
                        int(self.pps[8]),
                        int(self.strpins[8]),
                        td_wait(8),
                        pump_time(8),
                    )
                    self.used_pines[8] = (
                        self.pps[8],
                        self.strpins[8],
                    )

            def Pmp9TD():
                if self.v9 != 0:
                    pumpsWorkTC(
                        9,
                        int(self.pps[9]),
                        int(self.strpins[9]),
                        td_wait(9),
                        pump_time(9),
                    )
                    self.used_pines[9] = (
                        self.pps[9],
                        self.strpins[9],
                    )

            hilo_ms1 = threading.Thread(target=stir1)
            hilo_ms2 = threading.Thread(target=stir2)
            hilo_ms3 = threading.Thread(target=stir3)

            hilo_s = threading.Thread(target=Pmps)
            hilo_1 = threading.Thread(target=Pmp1)
            hilo_2 = threading.Thread(target=Pmp2)
            hilo_3 = threading.Thread(target=Pmp3)
            hilo_4 = threading.Thread(target=Pmp4)
            hilo_5 = threading.Thread(target=Pmp5)
            hilo_6 = threading.Thread(target=Pmp6)
            hilo_7 = threading.Thread(target=Pmp7)
            hilo_8 = threading.Thread(target=Pmp8)
            hilo_9 = threading.Thread(target=Pmp9)

            h_2 = threading.Thread(target=Pmp2TD)
            h_3 = threading.Thread(target=Pmp3TD)
            h_4 = threading.Thread(target=Pmp4TD)
            h_5 = threading.Thread(target=Pmp5TD)
            h_6 = threading.Thread(target=Pmp6TD)
            h_7 = threading.Thread(target=Pmp7TD)
            h_8 = threading.Thread(target=Pmp8TD)
            h_9 = threading.Thread(target=Pmp9TD)

            if self.selection_mood == "Parallel":
                parallel_threads = [
                    hilo_s,
                    hilo_ms1,
                    hilo_1,
                    hilo_2,
                    hilo_3,
                    hilo_4,
                    hilo_5,
                    hilo_6,
                    hilo_7,
                    hilo_8,
                    hilo_9,
                ]

                for hilo in parallel_threads:
                    hilo.start()

                for hilo in parallel_threads:
                    hilo.join()

                self.reaction_finished()

            elif self.selection_mood == "In-Order":

                # Sin agitación durante la adición.
                if self.stir_stage == 0:
                    Pmp1()
                    Pmp2()
                    Pmp3()
                    Pmp4()
                    Pmp5()
                    Pmp6()
                    Pmp7()
                    Pmp8()
                    Pmp9()

                    self.reaction_finished()

                # Agitación desde la primera etapa.
                elif self.stir_stage == 1:
                    in_order_threads = [
                        hilo_1,
                        h_2,
                        hilo_ms1,
                        h_3,
                        h_4,
                        h_5,
                        h_6,
                        h_7,
                        h_8,
                        h_9,
                    ]

                    for hilo in in_order_threads:
                        hilo.start()

                    for hilo in in_order_threads:
                        hilo.join()

                    self.reaction_finished()

                # Agitación a partir de la segunda etapa.
                elif self.stir_stage == 2:
                    Pmp1()

                    in_order_threads = [
                        hilo_ms2,
                        h_2,
                        h_3,
                        h_4,
                        h_5,
                        h_6,
                        h_7,
                        h_8,
                        h_9,
                    ]

                    for hilo in in_order_threads:
                        hilo.start()

                    for hilo in in_order_threads:
                        hilo.join()

                    self.reaction_finished()

                # Agitación a partir de la tercera etapa.
                elif self.stir_stage == 3:
                    Pmp1()
                    Pmp2()

                    in_order_threads = [
                        hilo_ms3,
                        h_3,
                        h_4,
                        h_5,
                        h_6,
                        h_7,
                        h_8,
                        h_9,
                    ]

                    for hilo in in_order_threads:
                        hilo.start()

                    for hilo in in_order_threads:
                        hilo.join()

                    self.reaction_finished()

        confirm_popup = Popup(
            title="CONFIRM",
            size_hint=(None, None),
            size=(300, 200),
        )

        content = BoxLayout(
            orientation="vertical"
        )

        content.add_widget(
            Label(
                text="Do you want to start the reaction?",
                font_size=18,
            )
        )

        buttons = BoxLayout(
            size_hint_y=0.4
        )

        yes_btn = Button(
            text="YES"
        )

        no_btn = Button(
            text="NO"
        )

        yes_btn.bind(
            on_press=lambda x: [
                confirm_popup.dismiss(),
                wmk(),
            ]
        )

        no_btn.bind(
            on_press=lambda x: [
                confirm_popup.dismiss()
            ]
        )

        buttons.add_widget(yes_btn)
        buttons.add_widget(no_btn)
        content.add_widget(buttons)

        confirm_popup.content = content
        confirm_popup.open()

    def rxnY(self, *args):
        # YES: considera tiempos de carga tc.
        self._run_reaction(include_load_time=True)

    def rxnN(self, *args):
        # NO: NO considera tiempos de carga tc.
        self._run_reaction(include_load_time=False)

    def chyorn(self):

        if self.selection_mood == "":
            Popup(
                title="Error",
                content=Label(
                    text="Select the addition!",
                    font_size=18
                ),
                size_hint=(None, None),
                size=(300, 150),
            ).open()

            return

        try:
            self.volumes = [
                int(self.ids[f"vol{i}"].text)
                for i in range(10)
            ]

        except ValueError:

            Popup(
                title="Error",
                content=Label(
                    text="Only numbers allowed in volumes!",
                    font_size=18
                ),
                size_hint=(None, None),
                size=(300, 150),
            ).open()

            return

        confirm_popup = Popup(
            title="CONFIRM",
            size_hint=(None, None),
            size=(300, 200)
        )

        content = BoxLayout(
            orientation="vertical"
        )

        content.add_widget(
            Label(
                text="Consider the load time?",
                font_size=18
            )
        )

        buttons = BoxLayout(
            size_hint_y=0.4
        )

        yes_btn = Button(
            text="YES"
        )

        no_btn = Button(
            text="NO"
        )

        yes_btn.bind(
            on_press=lambda x: [
                confirm_popup.dismiss(),
                self.rxnY()
            ]
        )

        no_btn.bind(
            on_press=lambda x: [
                confirm_popup.dismiss(),
                self.rxnN()
            ]
        )

        buttons.add_widget(
            yes_btn
        )

        buttons.add_widget(
            no_btn
        )

        content.add_widget(
            buttons
        )

        confirm_popup.content = content

        confirm_popup.open()


class MikiApp(App):

    def build(self):
        Builder.load_file(
            "mikiscreen_fixed.kv"
        )

        return MikiScreen()


if __name__ == "__main__":
    MikiApp().run()
