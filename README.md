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

## Firmware (ESP32-S3)

El sketch `firmware/shockdyno_sensores/shockdyno_sensores.ino` lee:

- Potenciómetro lineal por ADC (**GPIO1**, ADC1_CH0)
- Celda de carga vía **HX711** (DOUT = GPIO4, SCK = GPIO5)
- Dos sensores de temperatura **DS18B20** en un bus OneWire compartido (GPIO6, con pull-up de 4.7k)

En ESP32-S3 se evitan los pines de strapping (GPIO0/3/45/46) y GPIO26-37 (reservados si el
módulo usa PSRAM/flash octal); por eso se usan pines bajos en vez de los típicos del ESP32 original.

Requiere las librerías `HX711` (bogde), `OneWire` y `DallasTemperature` desde el Arduino Library Manager.
En Arduino IDE selecciona la placa **"ESP32S3 Dev Module"** a 115200 baudios. Si tu placa solo tiene
un puerto USB nativo (sin chip USB-UART aparte), activa **"USB CDC On Boot: Enabled"** en Herramientas,
o el puerto serie no aparecerá hasta que inicialice el stack USB. Si tu placa tiene dos puertos
(uno "USB" y otro "COM"/"UART"), usa el puerto **COM** para programar: pasa por un chip USB-serie
dedicado y es más confiable que el puerto nativo.

### Potenciómetro / transductor lineal (ej. Gefran LT-M)

Conexión de 3 hilos (potenciómetro conductivo), excitación a 3.3V (coincide con el rango del ADC,
sin necesitar divisor de voltaje):

| Cable (color típico Gefran) | Función | Pin ESP32-S3 |
|---|---|---|
| Café/marrón | +V (excitación) | 3V3 |
| Celeste/azul | Salida (cursor) | GPIO1 |
| Verde/amarillo | GND | GND |

Para reducir ruido:
- El firmware promedia 16 muestras del ADC por lectura (ver `leerPotCrudo()`).
- Si el cable del sensor trae una malla/blindaje, conéctala a GND **solo en el extremo del ESP32**
  (no en ambos extremos, para evitar bucles de tierra).
- Separa el cableado del sensor de cualquier cable de potencia/motor; si deben cruzarse, que sea
  en ángulo recto (90°), nunca en paralelo.
- Si el ruido persiste, agrega un capacitor cerámico de 100nF entre GPIO1 y GND, lo más cerca
  posible del pin del ESP32.

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
