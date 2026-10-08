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

## Firmware (multiplataforma: Arduino Uno / ESP32-WROOM-32 / ESP32-S3)

El sketch `firmware/shockdyno_sensores/shockdyno_sensores.ino` detecta automáticamente la placa
seleccionada en Arduino IDE (Tools > Board) y usa los pines correctos sin editar código. Lee:

- Potenciómetro lineal por ADC
- Celda de carga vía **HX711**
- Dos sensores de temperatura **DS18B20** en un bus OneWire compartido

Requiere las librerías `HX711` (bogde), `OneWire` y `DallasTemperature` desde el Arduino Library
Manager (o instaladas manualmente vía "Add .ZIP Library..." si el índice del Library Manager
no las muestra). A 115200 baudios en todas las placas.

### Pines por placa

| Función | Arduino Uno | ESP32-WROOM-32 | ESP32-S3 |
|---|---|---|---|
| Potenciómetro (ADC) | A0 | GPIO34 | GPIO1 |
| HX711 DOUT | D6 | GPIO16 | GPIO4 |
| HX711 SCK | D7 | GPIO17 | GPIO5 |
| DS18B20 (OneWire) | D2 | GPIO4 | GPIO6 |
| Excitación potenciómetro | 5V | 3.3V | 3.3V |
| Referencia ADC | 5V / 10 bits | 3.3V / 12 bits | 3.3V / 12 bits |

En ESP32-S3 se evitan los pines de strapping (GPIO0/3/45/46) y GPIO26-37 (reservados si el
módulo usa PSRAM/flash octal). En ESP32-WROOM-32 clásico, GPIO34 es solo-entrada, ideal para ADC.

En Arduino IDE selecciona la placa correspondiente: **"Arduino Uno"**, **"ESP32 Dev Module"**
(para el WROOM-32 clásico) o **"ESP32S3 Dev Module"**. Para placas ESP32 con un solo puerto USB
nativo (sin chip USB-UART aparte), activa **"USB CDC On Boot: Enabled"** en Herramientas, o el
puerto serie no aparecerá hasta que inicialice el stack USB. Si tu placa tiene dos puertos
(uno "USB" y otro "COM"/"UART"), usa el puerto **COM** para programar: pasa por un chip USB-serie
dedicado y es más confiable que el puerto nativo.

> **Arduino Uno como placa de pruebas temporal**: si aún no tienes el ESP32 definitivo, puedes
> usar un Arduino Uno para probar los 3 sensores con el mismo protocolo serie y la misma GUI.
> Solo cambia el voltaje de excitación del potenciómetro a 5V (no 3.3V) según la tabla de pines.

### Potenciómetro / transductor lineal (ej. Gefran LT-M)

Conexión de 3 hilos (potenciómetro conductivo):

| Cable (color típico Gefran) | Función | Arduino Uno | ESP32 (clásico o S3) |
|---|---|---|---|
| Café/marrón | +V (excitación) | 5V | 3V3 |
| Celeste/azul | Salida (cursor) | A0 | GPIO34 (clásico) / GPIO1 (S3) |
| Verde/amarillo | GND | GND | GND |

Para reducir ruido:
- El firmware promedia 16 muestras del ADC por lectura (ver `leerPotCrudo()`).
- Si el cable del sensor trae una malla/blindaje, conéctala a GND **solo en un extremo**
  (no en ambos, para evitar bucles de tierra).
- Separa el cableado del sensor de cualquier cable de potencia/motor; si deben cruzarse, que sea
  en ángulo recto (90°), nunca en paralelo.
- Si el ruido persiste, agrega un capacitor cerámico de 100nF entre el pin de señal y GND, lo más
  cerca posible del microcontrolador.

### Diagnóstico: "Error en una solicitud del descriptor de dispositivo USB" / Código 43

Si Windows no reconoce la placa en ningún puerto (ni "USB" ni "COM"), con distintos cables y
puertos de la PC, y un pendrive sí funciona en el mismo puerto/cable, es una falla de hardware
en la placa (posible ESD o pico de corriente), no del cable, del puerto o del firmware. Prueba
un power-cycle largo (2 min desconectada) y revisa visualmente los conectores; si persiste,
probablemente haya que reemplazar la placa.

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
