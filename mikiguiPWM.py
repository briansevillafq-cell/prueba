from kivy.config import Config

Config.set("graphics", "width", "1135")
Config.set("graphics", "height", "665")
Config.set("graphics", "resizable", "0")

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
        self._ultimo_toggle_camara = 0.0
        Clock.schedule_interval(self.sync_camera_state, 0.25)

    def sync_camera_state(self, dt):
        self.camara_activa = bool(pruebate3.camara_activa_global)

    def toggle_camera(self):
        ahora = time.monotonic()

        if ahora - self._ultimo_toggle_camara < 0.8:
            print("[CAM UI] Evento duplicado ignorado")
            return

        self._ultimo_toggle_camara = ahora

        if pruebate3.camara_activa_global:
            print("[CAM UI] Apagando cÃ¡mara")
            pruebate3.detener_camara()
            self.camara_activa = False
            return

        print("Encendiendo cÃ¡mara")

        pruebate3.texto_overlay = "EN ESPERA"
        pruebate3.color_overlay = (0, 255, 0)

        iniciada = pruebate3.iniciar_camara(self)

        if iniciada:
            self.camara_activa = True

    def stirring(self, temp, rpm, time_wait, time_min):
        hilo_cam = pruebate3.hilo_camara_global

        if (
            not pruebate3.camara_activa_global
            and (hilo_cam is None or not hilo_cam.is_alive())
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
            x = 63 + 203 * j
            y = 170
            center_x = x + 99

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
                    size=(110, 30),
                    pos=(center_x - 55, 332),
                    color=(0, 0, 0, 1),
                    font_size=20,
                )
            )

            self.add_widget(
                Label(
                    text="Vol (ml): ",
                    size_hint=(None, None),
                    size=(95, 30),
                    pos=(center_x - 92, 133),
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
            ("Service Pump", (170, 30), (35, 585), 20),
            ("Vol (ml): ", (100, 30), (30, 386), 18),
            ("Addition", (200, 28), (220, 76), 18),
            ("Heat/Stir", (245, 28), (560, 76), 18),
            ("temp (Â°C)", (80, 24), (560, 52), 14),
            ("rpm", (80, 24), (645, 52), 14),
            ("time (min)", (80, 24), (730, 52), 14),
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
            content=Label(text="Reaction finished", font_size=18),
            size_hint=(None, None),
            size=(300, 150),
        )
        popup.open()
        Clock.schedule_once(lambda dt: self.ask_clean_tubes(), 5)

    def ask_clean_tubes(self):
        layout = BoxLayout(orientation="vertical", spacing=10, padding=10)
        layout.add_widget(
            Label(text="Do you want to clean the tubes?", font_size=18)
        )

        btn_layout = BoxLayout(spacing=10, size_hint_y=None, height=40)
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
                0: 28,
                17: 0.2481,
                27: 0.1892,
                22: 0.2099,
                13: 0.2285,
                2: 0.22,
                18: 0.22,
                25: 0.2409,
                4: 0.22,
                7: 0.22,
            }
            popup.dismiss()
            cleanUp(True, self.used_pines, self.flow)
            self.ids.srtButton.disabled = False

        def on_no(instance):
            popup.dismiss()
            self.ids.srtButton.disabled = False

        btn_yes.bind(on_release=on_yes)
        btn_no.bind(on_release=on_no)
        popup.open()

    def rxnY(self, *args):
        self.pps = [14, 17, 27, 22, 13, 2, 18, 25, 4, 7]
        self.strpins = [15, 23, 5, 6, 26, 16, 20, 21, 1, 8, 24, 12]
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
        self.tc = [2, 16, 17, 18, 17, 18, 17, 18, 19, 18]
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
                int(self.ids.vol0.text) if self.ids.vol0.text.strip() else 0
            )
            self.v1 = (
                int(self.ids.vol1.text) if self.ids.vol1.text.strip() else 0
            )
            self.v2 = (
                int(self.ids.vol2.text) if self.ids.vol2.text.strip() else 0
            )
            self.v3 = (
                int(self.ids.vol3.text) if self.ids.vol3.text.strip() else 0
            )
            self.v4 = (
                int(self.ids.vol4.text) if self.ids.vol4.text.strip() else 0
            )
            self.v5 = (
                int(self.ids.vol5.text) if self.ids.vol5.text.strip() else 0
            )
            self.v6 = (
                int(self.ids.vol6.text) if self.ids.vol6.text.strip() else 0
            )
            self.v7 = (
                int(self.ids.vol7.text) if self.ids.vol7.text.strip() else 0
            )
            self.v8 = (
                int(self.ids.vol8.text) if self.ids.vol8.text.strip() else 0
            )
            self.v9 = (
                int(self.ids.vol9.text) if self.ids.vol9.text.strip() else 0
            )

            t_wait = (self.v1 / self.flow[self.pps[1]] + self.tc[1]) + (
                self.v2 / self.flow[self.pps[2]] + self.tc[2]
            )

            def stir1():
                if self.stir_stage == 1:
                    self.stirring(
                        self.tempstr,
                        self.rpmstr,
                        t_wait if self.tmstr != 0 else 1,
                        self.tmstr,
                    )

            def Pmps():
                if self.vs != 0:
                    pumpsWork(
                        0,
                        int(self.pps[0]),
                        int(self.strpins[0]),
                        self.vs / self.flow[self.pps[0]] + self.tc[0],
                    )
                    self.used_pines[0] = self.pps[0], self.strpins[0]

            def Pmp1():
                if self.v1 != 0:
                    pumpsWork(
                        1,
                        int(self.pps[1]),
                        int(self.strpins[1]),
                        (self.v1 / self.flow[self.pps[1]]) + self.tc[1],
                    )
                    self.used_pines[1] = self.pps[1], self.strpins[1]

            def Pmp2():
                if self.v2 != 0:
                    pumpsWork(
                        2,
                        int(self.pps[2]),
                        int(self.strpins[2]),
                        (self.v2 / self.flow[self.pps[2]]) + self.tc[2],
                    )
                    self.used_pines[2] = self.pps[2], self.strpins[2]

            def Pmp2TD():
                if self.v2 != 0:
                    pumpsWorkTC(
                        2,
                        int(self.pps[2]),
                        int(self.strpins[2]),
                        self.v1 / self.flow[self.pps[1]],
                        self.v2 / self.flow[self.pps[2]] + self.tc[2],
                    )
                    self.used_pines[2] = self.pps[2], self.strpins[2]

            hilo_ms1 = threading.Thread(target=stir1)
            hilo_s = threading.Thread(target=Pmps)
            hilo_1 = threading.Thread(target=Pmp1)
            hilo_2 = threading.Thread(target=Pmp2)
            h_2 = threading.Thread(target=Pmp2TD)

            if self.selection_mood == "Parallel":
                hilo_s.start()
                hilo_ms1.start()
                hilo_1.start()
                hilo_2.start()

                hilo_s.join()
                hilo_ms1.join()
                hilo_1.join()
                hilo_2.join()
                self.reaction_finished()

            elif self.selection_mood == "In-Order":
                if self.stir_stage == 0:
                    Pmp1()
                    Pmp2()
                    self.reaction_finished()
                elif self.stir_stage == 1:
                    hilo_1.start()
                    h_2.start()
                    hilo_ms1.start()

                    hilo_1.join()
                    h_2.join()
                    hilo_ms1.join()
                    self.reaction_finished()

        confirm_popup = Popup(
            title="CONFIRM",
            size_hint=(None, None),
            size=(300, 200),
        )

        content = BoxLayout(orientation="vertical")
        content.add_widget(
            Label(
                text="Do you want to start the reaction?",
                font_size=18,
            )
        )

        buttons = BoxLayout(size_hint_y=0.4)
        yes_btn = Button(text="YES")
        no_btn = Button(text="NO")
        yes_btn.bind(on_press=lambda x: [confirm_popup.dismiss(), wmk()])
        no_btn.bind(on_press=lambda x: [confirm_popup.dismiss()])
        buttons.add_widget(yes_btn)
        buttons.add_widget(no_btn)
        content.add_widget(buttons)
        confirm_popup.content = content
        confirm_popup.open()

    def rxnN(self, *args):
        self.rxnY(*args)

    def chyorn(self):
        if self.selection_mood == "":
            Popup(
                title="Error",
                content=Label(text="Select the addition!", font_size=18),
                size_hint=(None, None),
                size=(300, 150),
            ).open()
            return

        try:
            self.volumes = [
                int(self.ids[f"vol{i}"].text) for i in range(10)
            ]
        except ValueError:
            Popup(
                title="Error",
                content=Label(
                    text="Only numbers allowed in volumes!",
                    font_size=18,
                ),
                size_hint=(None, None),
                size=(300, 150),
            ).open()
            return

        confirm_popup = Popup(
            title="CONFIRM",
            size_hint=(None, None),
            size=(300, 200),
        )

        content = BoxLayout(orientation="vertical")
        content.add_widget(
            Label(text="Consider the load time?", font_size=18)
        )

        buttons = BoxLayout(size_hint_y=0.4)
        yes_btn = Button(text="YES")
        no_btn = Button(text="NO")

        yes_btn.bind(
            on_press=lambda x: [confirm_popup.dismiss(), self.rxnY()]
        )
        no_btn.bind(
            on_press=lambda x: [confirm_popup.dismiss(), self.rxnN()]
        )

        buttons.add_widget(yes_btn)
        buttons.add_widget(no_btn)
        content.add_widget(buttons)
        confirm_popup.content = content
        confirm_popup.open()


class MikiApp(App):

    def build(self):
        Builder.load_file("mikiscreen_fixed.kv")
        return MikiScreen()


if __name__ == "__main__":
    MikiApp().run()
