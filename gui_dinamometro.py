import sys
import json
from datetime import datetime
from pathlib import Path

from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QTabWidget,
    QLabel,
    QPushButton,
    QComboBox,
    QSpinBox,
    QDoubleSpinBox,
    QTextEdit,
    QGroupBox,
    QMessageBox,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
)
from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtGui import QFont
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import numpy as np

from serial_comm import SensorSerial, available_ports


DARK_STYLESHEET = """
QMainWindow, QWidget {
    background-color: #171a1f;
    color: #f2f5f7;
}

QTabWidget::pane {
    border: 1px solid #2b313d;
    background: #171a1f;
}

QTabBar::tab {
    background: #202833;
    color: #e5edf5;
    padding: 10px 18px;
    border: 1px solid #2b313d;
}

QTabBar::tab:selected {
    background: #0e88d8;
    color: white;
}

QPushButton {
    background: #1d4ed8;
    color: white;
    border: none;
    border-radius: 6px;
    padding: 8px 14px;
    font-weight: bold;
}

QPushButton:hover { background: #2563eb; }
QPushButton:pressed { background: #1e3a8a; }

QPushButton#danger {
    background: #dc2626;
}

QPushButton#danger:hover { background: #ef4444; }

QPushButton#success {
    background: #16a34a;
}

QPushButton#success:hover { background: #22c55e; }

QGroupBox {
    border: 1px solid #2b313d;
    border-radius: 6px;
    margin-top: 12px;
    padding-top: 10px;
    font-weight: bold;
    color: #7dd3fc;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 8px;
    padding: 0 6px;
}

QComboBox, QSpinBox, QDoubleSpinBox, QTextEdit, QTableWidget {
    background: #1d2430;
    color: #f3f4f6;
    border: 1px solid #2b313d;
    border-radius: 5px;
}

QLabel#title {
    font-size: 26px;
    font-weight: bold;
    color: #7dd3fc;
}

QLabel#value {
    font-size: 22px;
    font-weight: bold;
    color: #86efac;
}

QLabel#smallTitle {
    font-size: 12px;
    color: #dbeafe;
}
"""


class MplCanvas(FigureCanvas):
    def __init__(self, parent=None, width=5, height=4, dpi=100):
        self.fig = Figure(figsize=(width, height), dpi=dpi)
        self.ax = self.fig.add_subplot(111)
        self.ax.set_facecolor("#1f2937")
        self.ax.tick_params(colors="#e5e7eb")
        self.ax.spines["top"].set_visible(False)
        self.ax.spines["right"].set_visible(False)
        self.ax.spines["left"].set_color("#334155")
        self.ax.spines["bottom"].set_color("#334155")
        super().__init__(self.fig)
        self.setParent(parent)


class ValuesPanel(QWidget):
    def __init__(self):
        super().__init__()
        layout = QGridLayout()
        layout.setSpacing(16)

        self.force_label = QLabel("0.00 N")
        self.force_label.setObjectName("value")
        self.recorrido_label = QLabel("0.00 mm")
        self.recorrido_label.setObjectName("value")
        self.temp1_label = QLabel("0.0 °C")
        self.temp1_label.setObjectName("value")
        self.temp2_label = QLabel("0.0 °C")
        self.temp2_label.setObjectName("value")
        self.estado_label = QLabel("DESCONECTADO")
        self.estado_label.setStyleSheet("color: #fca5a5; font-weight: bold; font-size: 18px;")
        self.motor_label = QLabel("APAGADO")
        self.motor_label.setStyleSheet("color: #fca5a5; font-weight: bold; font-size: 18px;")
        self.tiempo_label = QLabel("00:00:00")
        self.tiempo_label.setStyleSheet("color: #7dd3fc; font-weight: bold; font-size: 18px;")

        layout.addWidget(QLabel("FUERZA"), 0, 0)
        layout.addWidget(self.force_label, 1, 0)
        layout.addWidget(QLabel("RECORRIDO"), 0, 1)
        layout.addWidget(self.recorrido_label, 1, 1)
        layout.addWidget(QLabel("TEMPERATURA 1"), 2, 0)
        layout.addWidget(self.temp1_label, 3, 0)
        layout.addWidget(QLabel("TEMPERATURA 2"), 2, 1)
        layout.addWidget(self.temp2_label, 3, 1)
        layout.addWidget(QLabel("ESTADO"), 4, 0)
        layout.addWidget(self.estado_label, 5, 0)
        layout.addWidget(QLabel("MOTOR"), 4, 1)
        layout.addWidget(self.motor_label, 5, 1)
        layout.addWidget(QLabel("TIEMPO"), 6, 0)
        layout.addWidget(self.tiempo_label, 7, 0)

        self.setLayout(layout)

    def update_values(self, fuerza, recorrido, temp1, temp2, estado, motor, tiempo):
        self.force_label.setText(f"{fuerza:.2f} N")
        self.recorrido_label.setText(f"{recorrido:.2f} mm")
        self.temp1_label.setText(f"{temp1:.1f} °C")
        self.temp2_label.setText(f"{temp2:.1f} °C")

        if estado == "Conectado":
            self.estado_label.setText("CONECTADO")
            self.estado_label.setStyleSheet("color: #86efac; font-weight: bold; font-size: 18px;")
        elif estado == "Pruebando":
            self.estado_label.setText("PRUEBANDO")
            self.estado_label.setStyleSheet("color: #fbbf24; font-weight: bold; font-size: 18px;")
        else:
            self.estado_label.setText("DESCONECTADO")
            self.estado_label.setStyleSheet("color: #fca5a5; font-weight: bold; font-size: 18px;")

        if motor:
            self.motor_label.setText("ENCENDIDO")
            self.motor_label.setStyleSheet("color: #86efac; font-weight: bold; font-size: 18px;")
        else:
            self.motor_label.setText("APAGADO")
            self.motor_label.setStyleSheet("color: #fca5a5; font-weight: bold; font-size: 18px;")

        total = int(tiempo)
        hrs, rem = divmod(total, 3600)
        mins, secs = divmod(rem, 60)
        self.tiempo_label.setText(f"{hrs:02d}:{mins:02d}:{secs:02d}")


class GraphPanel(QWidget):
    def __init__(self):
        super().__init__()
        self.data = {"t": [], "f": [], "r": [], "t1": [], "t2": []}
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        selector_layout = QHBoxLayout()

        selector_layout.addWidget(QLabel("Gráfico:"))
        self.selector = QComboBox()
        self.selector.addItems([
            "Fuerza vs Tiempo",
            "Fuerza vs Recorrido",
            "Temperatura 1 vs Tiempo",
            "Temperatura 2 vs Tiempo",
            "Fuerza y Recorrido",
            "Ambas Temperaturas",
        ])
        self.selector.currentTextChanged.connect(self.render_graph)
        selector_layout.addWidget(self.selector)
        selector_layout.addStretch()
        layout.addLayout(selector_layout)

        self.canvas = MplCanvas(self, width=8, height=5, dpi=100)
        layout.addWidget(self.canvas)
        self.setLayout(layout)

    def update_data(self, t, f, r, t1, t2):
        self.data["t"].append(t)
        self.data["f"].append(f)
        self.data["r"].append(r)
        self.data["t1"].append(t1)
        self.data["t2"].append(t2)
        self.render_graph()

    def clear_data(self):
        self.data = {"t": [], "f": [], "r": [], "t1": [], "t2": []}
        self.render_graph()

    def render_graph(self):
        self.canvas.ax.clear()

        if not self.data["t"]:
            self.canvas.draw()
            return

        t = np.array(self.data["t"])
        name = self.selector.currentText()

        if name == "Fuerza vs Tiempo":
            f = np.array(self.data["f"])
            self.canvas.ax.plot(t, f, color="#60a5fa", linewidth=2)
            self.canvas.ax.set_title("Fuerza vs Tiempo")
            self.canvas.ax.set_xlabel("Tiempo (s)")
            self.canvas.ax.set_ylabel("Fuerza (N)")

        elif name == "Fuerza vs Recorrido":
            r = np.array(self.data["r"])
            f = np.array(self.data["f"])
            self.canvas.ax.plot(r, f, color="#34d399", linewidth=2)
            self.canvas.ax.set_title("Fuerza vs Recorrido")
            self.canvas.ax.set_xlabel("Recorrido (mm)")
            self.canvas.ax.set_ylabel("Fuerza (N)")

        elif name == "Temperatura 1 vs Tiempo":
            t1 = np.array(self.data["t1"])
            self.canvas.ax.plot(t, t1, color="#f59e0b", linewidth=2)
            self.canvas.ax.set_title("Temperatura 1 vs Tiempo")
            self.canvas.ax.set_xlabel("Tiempo (s)")
            self.canvas.ax.set_ylabel("Temperatura (°C)")

        elif name == "Temperatura 2 vs Tiempo":
            t2 = np.array(self.data["t2"])
            self.canvas.ax.plot(t, t2, color="#f97316", linewidth=2)
            self.canvas.ax.set_title("Temperatura 2 vs Tiempo")
            self.canvas.ax.set_xlabel("Tiempo (s)")
            self.canvas.ax.set_ylabel("Temperatura (°C)")

        elif name == "Fuerza y Recorrido":
            f = np.array(self.data["f"])
            r = np.array(self.data["r"])
            self.canvas.ax.plot(t, f, color="#60a5fa", linewidth=2, label="Fuerza")
            ax2 = self.canvas.ax.twinx()
            ax2.plot(t, r, color="#34d399", linewidth=2, label="Recorrido")
            self.canvas.ax.set_title("Fuerza y Recorrido")
            self.canvas.ax.set_xlabel("Tiempo (s)")
            self.canvas.ax.set_ylabel("Fuerza (N)")
            ax2.set_ylabel("Recorrido (mm)")
            self.canvas.ax.legend(loc="upper left")

        elif name == "Ambas Temperaturas":
            t1 = np.array(self.data["t1"])
            t2 = np.array(self.data["t2"])
            self.canvas.ax.plot(t, t1, color="#f59e0b", linewidth=2, label="Temp 1")
            self.canvas.ax.plot(t, t2, color="#f97316", linewidth=2, label="Temp 2")
            self.canvas.ax.set_title("Ambas Temperaturas")
            self.canvas.ax.set_xlabel("Tiempo (s)")
            self.canvas.ax.set_ylabel("Temperatura (°C)")
            self.canvas.ax.legend()

        self.canvas.ax.grid(True, alpha=0.2)
        self.canvas.draw()


class CalibrationPanel(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()

        pos_group = QGroupBox("Calibración de posición inicial")
        pos_layout = QVBoxLayout()
        pos_layout.addWidget(QLabel("Coloca el amortiguador en la posición inicial y calibra la referencia 0 mm."))
        self.btn_pos = QPushButton("Calibrar posición inicial")
        self.lbl_pos = QLabel("Estado: no calibrado")
        self.lbl_pos.setStyleSheet("color: #fca5a5;")
        pos_layout.addWidget(self.btn_pos)
        pos_layout.addWidget(self.lbl_pos)
        pos_group.setLayout(pos_layout)

        celda_group = QGroupBox("Calibración de celda")
        celda_layout = QVBoxLayout()
        celda_layout.addWidget(QLabel("Peso conocido para calibrar la celda de carga."))
        row = QHBoxLayout()
        row.addWidget(QLabel("Peso (kg):"))
        self.peso_box = QDoubleSpinBox()
        self.peso_box.setValue(1.0)
        self.peso_box.setMaximum(1000.0)
        row.addWidget(self.peso_box)
        celda_layout.addLayout(row)
        self.btn_celda = QPushButton("Calibrar celda")
        self.lbl_celda = QLabel("Estado: no calibrado")
        self.lbl_celda.setStyleSheet("color: #fca5a5;")
        celda_layout.addWidget(self.btn_celda)
        celda_layout.addWidget(self.lbl_celda)
        celda_group.setLayout(celda_layout)

        info_group = QGroupBox("Información")
        info_layout = QVBoxLayout()
        self.info_box = QTextEdit()
        self.info_box.setReadOnly(True)
        info_layout.addWidget(self.info_box)
        info_group.setLayout(info_layout)

        layout.addWidget(pos_group)
        layout.addWidget(celda_group)
        layout.addWidget(info_group)
        self.setLayout(layout)


class ControlPanel(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()

        manual = QGroupBox("Control manual")
        manual_layout = QHBoxLayout()
        self.btn_on = QPushButton("ENCENDER MOTOR")
        self.btn_on.setObjectName("success")
        self.btn_off = QPushButton("APAGAR MOTOR")
        self.btn_off.setObjectName("danger")
        self.btn_stop = QPushButton("PARADA DE EMERGENCIA")
        self.btn_stop.setObjectName("danger")
        manual_layout.addWidget(self.btn_on)
        manual_layout.addWidget(self.btn_off)
        manual_layout.addWidget(self.btn_stop)
        manual.setLayout(manual_layout)

        auto = QGroupBox("Secuencia automática")
        auto_layout = QGridLayout()
        auto_layout.addWidget(QLabel("Encendido (s):"), 0, 0)
        self.encendido_box = QSpinBox()
        self.encendido_box.setValue(10)
        auto_layout.addWidget(self.encendido_box, 0, 1)

        auto_layout.addWidget(QLabel("Apagado (s):"), 0, 2)
        self.apagado_box = QSpinBox()
        self.apagado_box.setValue(5)
        auto_layout.addWidget(self.apagado_box, 0, 3)

        auto_layout.addWidget(QLabel("Ciclos:"), 1, 0)
        self.ciclos_box = QSpinBox()
        self.ciclos_box.setValue(1)
        self.ciclos_box.setMinimum(1)
        auto_layout.addWidget(self.ciclos_box, 1, 1)

        self.btn_sequence = QPushButton("INICIAR SECUENCIA")
        auto_layout.addWidget(self.btn_sequence, 1, 2, 1, 2)

        self.sequence_state = QLabel("Estado: detenido")
        auto_layout.addWidget(self.sequence_state, 2, 0, 1, 4)
        auto.setLayout(auto_layout)

        layout.addWidget(manual)
        layout.addWidget(auto)
        layout.addStretch()
        self.setLayout(layout)


class SensorTestPanel(QWidget):
    """Permite probar cada sensor de forma individual mientras se cablea el hardware."""

    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        layout.addWidget(
            QLabel(
                "Conéctate al ESP32 (arriba) y prueba cada sensor por separado "
                "antes de iniciar una prueba completa."
            )
        )

        grid = QGridLayout()
        grid.setSpacing(16)

        celda_group = QGroupBox("Celda de carga (HX711)")
        celda_layout = QVBoxLayout()
        self.btn_test_celda = QPushButton("Probar celda de carga")
        self.lbl_celda_estado = QLabel("Estado: sin probar")
        self.lbl_celda_estado.setStyleSheet("color: #9ca3af;")
        self.lbl_celda_valor = QLabel("Crudo: -- | Fuerza: -- N")
        self.lbl_celda_valor.setObjectName("smallTitle")
        celda_layout.addWidget(self.btn_test_celda)
        celda_layout.addWidget(self.lbl_celda_estado)
        celda_layout.addWidget(self.lbl_celda_valor)
        celda_group.setLayout(celda_layout)

        pot_group = QGroupBox("Potenciómetro lineal")
        pot_layout = QVBoxLayout()
        self.btn_test_pot = QPushButton("Probar potenciómetro")
        self.lbl_pot_estado = QLabel("Estado: sin probar")
        self.lbl_pot_estado.setStyleSheet("color: #9ca3af;")
        self.lbl_pot_valor = QLabel("Crudo: -- | Volts: -- | Posición: -- mm")
        self.lbl_pot_valor.setObjectName("smallTitle")
        pot_layout.addWidget(self.btn_test_pot)
        pot_layout.addWidget(self.lbl_pot_estado)
        pot_layout.addWidget(self.lbl_pot_valor)
        pot_group.setLayout(pot_layout)

        temp_group = QGroupBox("Temperatura (DS18B20 x2)")
        temp_layout = QVBoxLayout()
        self.btn_test_temp = QPushButton("Probar sensores de temperatura")
        self.lbl_temp_estado = QLabel("Estado: sin probar")
        self.lbl_temp_estado.setStyleSheet("color: #9ca3af;")
        self.lbl_temp_valor = QLabel("Detectados: -- | T1: -- °C | T2: -- °C")
        self.lbl_temp_valor.setObjectName("smallTitle")
        temp_layout.addWidget(self.btn_test_temp)
        temp_layout.addWidget(self.lbl_temp_estado)
        temp_layout.addWidget(self.lbl_temp_valor)
        temp_group.setLayout(temp_layout)

        grid.addWidget(celda_group, 0, 0)
        grid.addWidget(pot_group, 0, 1)
        grid.addWidget(temp_group, 0, 2)
        layout.addLayout(grid)
        layout.addStretch()
        self.setLayout(layout)

    def _set_estado(self, label, ok, texto_ok, texto_fail):
        if ok:
            label.setText(f"Estado: {texto_ok}")
            label.setStyleSheet("color: #86efac; font-weight: bold;")
        else:
            label.setText(f"Estado: {texto_fail}")
            label.setStyleSheet("color: #fca5a5; font-weight: bold;")

    def mostrar_resultado_celda(self, payload):
        ok = bool(payload.get("ok"))
        self._set_estado(self.lbl_celda_estado, ok, "OK", "no responde")
        self.lbl_celda_valor.setText(
            f"Crudo: {payload.get('raw', '--')} | Fuerza: {payload.get('fuerza_n', 0):.3f} N"
        )

    def mostrar_resultado_pot(self, payload):
        ok = bool(payload.get("ok"))
        self._set_estado(self.lbl_pot_estado, ok, "OK", "no responde")
        self.lbl_pot_valor.setText(
            f"Crudo: {payload.get('raw', '--')} | Volts: {payload.get('volts', 0):.3f} | "
            f"Posición: {payload.get('pos_mm', 0):.2f} mm"
        )

    def mostrar_resultado_temp(self, payload):
        ok = bool(payload.get("ok"))
        self._set_estado(self.lbl_temp_estado, ok, "OK", "ningún sensor detectado")
        detectados = payload.get("detectados", 0)
        t1 = payload.get("temp1", -127.0)
        t2 = payload.get("temp2", -127.0)
        t1_txt = f"{t1:.2f} °C" if payload.get("temp1_ok") else "no detectado"
        t2_txt = f"{t2:.2f} °C" if payload.get("temp2_ok") else "no detectado"
        self.lbl_temp_valor.setText(f"Detectados: {detectados} | T1: {t1_txt} | T2: {t2_txt}")


class HistoryPanel(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Fecha/Hora", "Nombre", "Duración", "Fuerza Máx", "Estado"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.table)
        self.setLayout(layout)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ShockDyno - Dinamómetro de amortiguadores")
        self.resize(1400, 920)
        self.setStyleSheet(DARK_STYLESHEET)

        self.connected = False
        self.motor_on = False
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_live)
        self.elapsed = 0.0
        self.last_reading = {"fuerza_n": 0.0, "pos_mm": 0.0, "temp1": 0.0, "temp2": 0.0}

        self.serial = SensorSerial()
        self.serial.data_received.connect(self.on_sensor_data)
        self.serial.test_result.connect(self.on_test_result)
        self.serial.ack_received.connect(self.on_ack_received)
        self.serial.error.connect(self.on_serial_error)

        self.init_ui()

    def init_ui(self):
        central = QWidget()
        layout = QVBoxLayout()

        header = QHBoxLayout()
        title = QLabel("DINAMÓMETRO DE AMORTIGUADORES")
        title.setObjectName("title")
        header.addWidget(title)
        header.addStretch()

        self.port_box = QComboBox()
        self.refresh_ports()
        self.refresh_ports_btn = QPushButton("ACTUALIZAR")
        self.refresh_ports_btn.clicked.connect(self.refresh_ports)
        self.connect_btn = QPushButton("CONECTAR")
        self.connect_btn.clicked.connect(self.toggle_connection)
        header.addWidget(QLabel("Puerto:"))
        header.addWidget(self.port_box)
        header.addWidget(self.refresh_ports_btn)
        header.addWidget(self.connect_btn)
        layout.addLayout(header)

        tabs = QTabWidget()

        acquisition = QWidget()
        acquisition_layout = QHBoxLayout()
        self.values_panel = ValuesPanel()
        self.graph_panel = GraphPanel()
        acquisition_layout.addWidget(self.values_panel, 0)
        acquisition_layout.addWidget(self.graph_panel, 1)
        acquisition.setLayout(acquisition_layout)

        calibration = CalibrationPanel()
        self.calibration_panel = calibration
        self.calibration_panel.btn_pos.clicked.connect(self.calibrate_position)
        self.calibration_panel.btn_celda.clicked.connect(self.calibrate_cell)

        control = ControlPanel()
        self.control_panel = control
        self.control_panel.btn_on.clicked.connect(self.turn_motor_on)
        self.control_panel.btn_off.clicked.connect(self.turn_motor_off)
        self.control_panel.btn_stop.clicked.connect(self.emergency_stop)
        self.control_panel.btn_sequence.clicked.connect(self.run_sequence)

        history = HistoryPanel()
        self.history_panel = history

        sensor_test = SensorTestPanel()
        self.sensor_test_panel = sensor_test
        self.sensor_test_panel.btn_test_celda.clicked.connect(lambda: self.run_sensor_test("TEST:HX711"))
        self.sensor_test_panel.btn_test_pot.clicked.connect(lambda: self.run_sensor_test("TEST:POT"))
        self.sensor_test_panel.btn_test_temp.clicked.connect(lambda: self.run_sensor_test("TEST:TEMP"))

        tabs.addTab(acquisition, "ADQUISICIÓN")
        tabs.addTab(sensor_test, "PRUEBA DE SENSORES")
        tabs.addTab(calibration, "CALIBRACIÓN")
        tabs.addTab(control, "CONTROL")
        tabs.addTab(history, "HISTORIAL")
        layout.addWidget(tabs)

        footer = QHBoxLayout()
        self.new_test_btn = QPushButton("NUEVA PRUEBA")
        self.stop_test_btn = QPushButton("PARAR PRUEBA")
        self.save_test_btn = QPushButton("GUARDAR PRUEBA")
        self.file_label = QLabel("Archivo: ninguno")
        self.stop_test_btn.setEnabled(False)
        self.save_test_btn.setEnabled(False)

        self.new_test_btn.clicked.connect(self.start_test)
        self.stop_test_btn.clicked.connect(self.stop_test)
        self.save_test_btn.clicked.connect(self.save_test)

        footer.addWidget(self.new_test_btn)
        footer.addWidget(self.stop_test_btn)
        footer.addWidget(self.save_test_btn)
        footer.addStretch()
        footer.addWidget(self.file_label)
        layout.addLayout(footer)

        central.setLayout(layout)
        self.setCentralWidget(central)

    def refresh_ports(self):
        puertos = available_ports()
        current = self.port_box.currentText() if self.port_box.count() else None
        self.port_box.clear()
        self.port_box.addItems(puertos)
        if current and current in puertos:
            self.port_box.setCurrentText(current)

    def toggle_connection(self):
        if not self.connected:
            port = self.port_box.currentText()
            if not port:
                QMessageBox.warning(self, "Error", "Selecciona un puerto serial. Usa ACTUALIZAR si no aparece.")
                return
            try:
                self.serial.connect(port, baudrate=115200)
            except Exception as exc:
                QMessageBox.critical(self, "Error de conexión", f"No se pudo conectar en {port}:\n{exc}")
                return

            self.connected = True
            self.connect_btn.setText("DESCONECTAR")
            self.values_panel.update_values(0, 0, 0, 0, "Conectado", False, 0)
            QMessageBox.information(self, "Conexión", f"ESP32 conectado en {port}.")
        else:
            try:
                self.serial.send_command("STREAM:OFF")
            except Exception:
                pass
            self.serial.disconnect()
            self.connected = False
            self.connect_btn.setText("CONECTAR")
            self.values_panel.update_values(0, 0, 0, 0, "Desconectado", False, 0)
            QMessageBox.information(self, "Conexión", "ESP32 desconectado.")

    def run_sensor_test(self, comando):
        if not self.connected:
            QMessageBox.warning(self, "Error", "Debe conectarse primero al ESP32.")
            return
        try:
            self.serial.send_command(comando)
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"No se pudo enviar el comando: {exc}")

    def on_test_result(self, payload):
        tipo = payload.get("test")
        if tipo == "HX711":
            self.sensor_test_panel.mostrar_resultado_celda(payload)
        elif tipo == "POT":
            self.sensor_test_panel.mostrar_resultado_pot(payload)
        elif tipo == "TEMP":
            self.sensor_test_panel.mostrar_resultado_temp(payload)

    def on_ack_received(self, payload):
        ack = payload.get("ack")
        if ack == "TARE_OK":
            self.calibration_panel.lbl_celda.setText("Estado: tara aplicada")
            self.calibration_panel.lbl_celda.setStyleSheet("color: #86efac;")
        elif ack == "CAL_OK":
            factor = payload.get("factor", 0.0)
            self.calibration_panel.lbl_celda.setText(f"Estado: calibrado (factor {factor:.3f})")
            self.calibration_panel.lbl_celda.setStyleSheet("color: #86efac;")
            self.calibration_panel.info_box.setText(
                f"Celda calibrada. Factor de conversión: {factor:.3f} cuentas/N."
            )
        elif ack == "CAL_ERROR":
            self.calibration_panel.lbl_celda.setText("Estado: error de calibración")
            self.calibration_panel.lbl_celda.setStyleSheet("color: #fca5a5;")
            QMessageBox.warning(self, "Calibración", "No se pudo calibrar la celda. Verifica la conexión del HX711.")
        elif ack == "ZERO_POS_OK":
            self.calibration_panel.lbl_pos.setText("Estado: calibrado")
            self.calibration_panel.lbl_pos.setStyleSheet("color: #86efac;")
            self.calibration_panel.info_box.setText("Posición inicial calibrada correctamente.\nReferencia 0 mm establecida.")

    def on_serial_error(self, mensaje):
        QMessageBox.critical(self, "Error de comunicación serial", mensaje)

    def on_sensor_data(self, data):
        self.last_reading = data
        if not self.connected:
            return
        fuerza = data.get("fuerza_n", 0.0)
        recorrido = data.get("pos_mm", 0.0)
        temp1 = data.get("temp1", 0.0)
        temp2 = data.get("temp2", 0.0)
        estado = "Pruebando" if self.timer.isActive() else "Conectado"
        self.values_panel.update_values(fuerza, recorrido, temp1, temp2, estado, self.motor_on, self.elapsed)
        if self.timer.isActive():
            self.graph_panel.update_data(self.elapsed, fuerza, recorrido, temp1, temp2)

    def start_test(self):
        if not self.connected:
            QMessageBox.warning(self, "Error", "Debe conectarse primero al ESP32.")
            return

        self.elapsed = 0.0
        self.graph_panel.clear_data()
        try:
            self.serial.send_command("STREAM:ON")
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"No se pudo iniciar la transmisión: {exc}")
            return
        self.timer.start(100)
        self.stop_test_btn.setEnabled(True)
        self.file_label.setText("Archivo: prueba_" + datetime.now().strftime("%Y%m%d_%H%M%S") + ".json")
        self.save_test_btn.setEnabled(False)

    def stop_test(self):
        self.timer.stop()
        try:
            self.serial.send_command("STREAM:OFF")
        except Exception:
            pass
        self.stop_test_btn.setEnabled(False)
        self.save_test_btn.setEnabled(True)
        self.turn_motor_off()

    def save_test(self):
        folder = Path("historial")
        folder.mkdir(exist_ok=True)
        file_name = self.file_label.text().replace("Archivo: ", "")
        path = folder / file_name
        payload = {
            "fecha": datetime.now().isoformat(),
            "duracion": self.elapsed,
            "datos": self.graph_panel.data,
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

        QMessageBox.information(self, "Guardado", f"Prueba guardada en: {path}")
        self.save_test_btn.setEnabled(False)

    def update_live(self):
        self.elapsed += 0.1
        fuerza = self.last_reading.get("fuerza_n", 0.0)
        recorrido = self.last_reading.get("pos_mm", 0.0)
        temp1 = self.last_reading.get("temp1", 0.0)
        temp2 = self.last_reading.get("temp2", 0.0)
        self.values_panel.update_values(fuerza, recorrido, temp1, temp2, "Pruebando", self.motor_on, self.elapsed)

    def calibrate_position(self):
        if not self.connected:
            QMessageBox.warning(self, "Error", "Debe conectarse primero al ESP32.")
            return
        try:
            self.serial.send_command("ZERO_POS")
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"No se pudo calibrar la posición: {exc}")

    def calibrate_cell(self):
        if not self.connected:
            QMessageBox.warning(self, "Error", "Debe conectarse primero al ESP32.")
            return
        value = self.calibration_panel.peso_box.value()
        try:
            self.serial.send_command("TARE")
            self.serial.send_command(f"CAL:{value}")
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"No se pudo calibrar la celda: {exc}")

    def turn_motor_on(self):
        self.motor_on = True
        self.values_panel.update_values(0, 0, 0, 0, "Conectado", True, self.elapsed)

    def turn_motor_off(self):
        self.motor_on = False
        self.values_panel.update_values(0, 0, 0, 0, "Conectado", False, self.elapsed)

    def emergency_stop(self):
        self.motor_on = False
        self.timer.stop()
        QMessageBox.critical(self, "PARADA DE EMERGENCIA", "Se activó la parada de emergencia.")

    def run_sequence(self):
        enc = self.control_panel.encendido_box.value()
        apag = self.control_panel.apagado_box.value()
        ciclos = self.control_panel.ciclos_box.value()
        self.control_panel.sequence_state.setText(f"Estado: ejecutando ({enc}s ON / {apag}s OFF / {ciclos} ciclos)")
        self.control_panel.sequence_state.setStyleSheet("color: #fbbf24; font-weight: bold;")
        QMessageBox.information(
            self,
            "Secuencia",
            f"Encendido: {enc}s\nApagado: {apag}s\nCiclos: {ciclos}",
        )

    def closeEvent(self, event):
        try:
            if self.serial.is_open:
                self.serial.send_command("STREAM:OFF")
        except Exception:
            pass
        self.serial.disconnect()
        super().closeEvent(event)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
