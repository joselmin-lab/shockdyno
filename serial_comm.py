"""
Comunicación serial con el firmware de sensores del ESP32.

Protocolo (ver firmware/shockdyno_sensores/shockdyno_sensores.ino):
  - Lectura continua en streaming: líneas JSON con fuerza, posición y temperaturas.
  - Comandos puntuales de prueba/calibración con respuesta JSON (ack o test).
"""

import json

import serial
import serial.tools.list_ports as list_ports
from PyQt5.QtCore import QObject, QThread, pyqtSignal


def available_ports():
    """Devuelve la lista de puertos seriales disponibles en el sistema."""
    return [p.device for p in list_ports.comports()]


class SerialReaderThread(QThread):
    """Hilo que lee líneas del puerto serial sin bloquear la interfaz."""

    line_received = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, serial_port):
        super().__init__()
        self._serial = serial_port
        self._running = True

    def run(self):
        while self._running:
            try:
                if self._serial is None or not self._serial.is_open:
                    self.msleep(50)
                    continue
                raw = self._serial.readline()
                if not raw:
                    continue
                text = raw.decode("utf-8", errors="ignore").strip()
                if text:
                    self.line_received.emit(text)
            except Exception as exc:  # puerto desconectado, error de IO, etc.
                self.error.emit(str(exc))
                self.msleep(200)

    def stop(self):
        self._running = False


class SensorSerial(QObject):
    """Administra la conexión serial con el ESP32: lectura continua y envío de comandos."""

    data_received = pyqtSignal(dict)   # lectura continua (streaming)
    test_result = pyqtSignal(dict)     # respuesta a TEST:<SENSOR>
    ack_received = pyqtSignal(dict)    # respuesta a PING/TARE/CAL/ZERO_POS/STREAM
    error = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.serial_port = None
        self.reader_thread = None

    @property
    def is_open(self):
        return self.serial_port is not None and self.serial_port.is_open

    def connect(self, port, baudrate=115200, timeout=1.0):
        self.disconnect()
        self.serial_port = serial.Serial(port, baudrate=baudrate, timeout=timeout)
        self.reader_thread = SerialReaderThread(self.serial_port)
        self.reader_thread.line_received.connect(self._handle_line)
        self.reader_thread.error.connect(self.error.emit)
        self.reader_thread.start()

    def disconnect(self):
        if self.reader_thread is not None:
            self.reader_thread.stop()
            self.reader_thread.wait(500)
            self.reader_thread = None
        if self.serial_port is not None:
            try:
                if self.serial_port.is_open:
                    self.serial_port.close()
            except Exception:
                pass
            self.serial_port = None

    def send_command(self, command):
        if not self.is_open:
            raise ConnectionError("El puerto serial no está abierto.")
        line = command.strip() + "\n"
        self.serial_port.write(line.encode("utf-8"))
        self.serial_port.flush()

    def _handle_line(self, text):
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            return

        if "test" in payload:
            self.test_result.emit(payload)
        elif "ack" in payload:
            self.ack_received.emit(payload)
        elif "fuerza_n" in payload or "fuerza_raw" in payload:
            self.data_received.emit(payload)
