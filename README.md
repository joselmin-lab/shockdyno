# shockdyno

Sistema para adquisición y control del dinamómetro de amortiguadores.

## Requisitos

- Python 3.10 a 3.14 (probado con 3.14.2)
- PyQt5
- matplotlib
- numpy
- pyserial (comunicación con el ESP32)

## Instalación

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Ejecutar la GUI

```bash
python gui_dinamometro.py
```

## Funcionalidades previstas

- Visualización de valores en vivo
- Selección de gráficos
- Calibración de posición inicial
- Calibración de celda de carga
- Encendido/apagado del motor
- Secuencia automática de prueba
- Guardado de historial por carpeta
- Exportación a CSV/PDF (preparado)

## Firmware (ESP32)

El sketch `firmware/shockdyno_sensores/shockdyno_sensores.ino` lee:

- Celda de carga vía **HX711** (DOUT = GPIO16, SCK = GPIO4)
- Potenciómetro lineal por ADC (GPIO34)
- Dos sensores de temperatura **DS18B20** en un bus OneWire compartido (GPIO15, con pull-up de 4.7k)

Requiere las librerías `HX711` (bogde), `OneWire` y `DallasTemperature` desde el Arduino Library Manager.
Súbelo con Arduino IDE/PlatformIO a 115200 baudios.

## Probar los sensores uno por uno

1. Sube el firmware al ESP32 y conéctalo por USB.
2. Ejecuta la GUI, selecciona el puerto (botón **ACTUALIZAR** si no aparece) y presiona **CONECTAR**.
3. Ve a la pestaña **PRUEBA DE SENSORES** y presiona cada botón para verificar, de forma individual:
   - **Celda de carga (HX711)**: valor crudo y fuerza calculada.
   - **Potenciómetro**: valor crudo, voltaje y posición estimada.
   - **Temperatura (DS18B20 x2)**: cuántos sensores fueron detectados y su lectura.
4. Usa la pestaña **CALIBRACIÓN** para tarar/calibrar la celda (con un peso conocido) y fijar la referencia 0 mm del potenciómetro, una vez verificados los sensores.

## Estructura

- `gui_dinamometro.py`: interfaz principal
- `serial_comm.py`: comunicación serial (hilo de lectura + comandos) con el ESP32
- `firmware/shockdyno_sensores/`: firmware del ESP32 para los sensores
- `requirements.txt`: dependencias del proyecto
