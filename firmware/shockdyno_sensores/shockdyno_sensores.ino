/*
 * ShockDyno - Firmware de sensores (multiplataforma)
 * -----------------------------------------
 * Lee celda de carga (HX711), potenciómetro lineal (ADC) y dos sensores
 * de temperatura DS18B20, y los expone por puerto serie (USB) en formato
 * JSON para la GUI de PyQt (gui_dinamometro.py).
 *
 * Este mismo archivo compila sin cambios para:
 *   - Arduino Uno (placa de pruebas temporal, 5V / ADC 10 bits)
 *   - ESP32-WROOM-32 clásico (3.3V / ADC 12 bits)
 *   - ESP32-S3 (3.3V / ADC 12 bits, pines seguros sin strapping)
 * La detección de placa es automática (ver bloque "Selección de placa").
 * Simplemente elige la placa correcta en Arduino IDE (Tools > Board) y
 * compila; no hay que editar pines a mano.
 *
 * Librerías necesarias (Arduino Library Manager):
 *   - HX711 (bogde/HX711)
 *   - OneWire (PaulStoffregen/OneWire)
 *   - DallasTemperature (milesburton/Arduino-Temperature-Control-Library)
 *
 * Conexiones por placa:
 *   Arduino Uno:
 *     Potenciómetro (cursor/wiper) -> A0
 *     HX711   DOUT -> D6            SCK -> D7
 *     DS18B20 x2 (bus compartido)   -> D2  (pull-up 4.7k a 5V)
 *     Excitación potenciómetro -> 5V (no 3.3V, Uno no tiene salida 3.3V de sobra)
 *
 *   ESP32-WROOM-32 clásico:
 *     Potenciómetro -> GPIO34 (ADC1_CH6, solo entrada, ideal)
 *     HX711   DOUT -> GPIO16        SCK -> GPIO17
 *     DS18B20 x2 -> GPIO4 (pull-up 4.7k a 3.3V)
 *
 *   ESP32-S3:
 *     Potenciómetro -> GPIO1  (ADC1_CH0)
 *     HX711   DOUT -> GPIO4        SCK -> GPIO5
 *     DS18B20 x2 -> GPIO6 (pull-up 4.7k a 3.3V)
 *     NOTA: en ESP32-S3 se evitan GPIO0/3/45/46 (strapping) y GPIO26-37
 *     (reservados si el módulo usa PSRAM/flash octal).
 *     Placa en Arduino IDE: "ESP32S3 Dev Module". Si tu placa tiene un
 *     solo puerto USB nativo (no un chip USB-UART aparte), activa
 *     "USB CDC On Boot: Enabled" en Herramientas.
 *
 * Protocolo serie (115200 baudios, líneas terminadas en \n):
 *   GUI -> ESP32:
 *     PING            responde {"ack":"PONG"}
 *     TARE            pone a cero la celda de carga (offset)
 *     CAL:<kg>        calibra la celda con un peso conocido en kg
 *     ZERO_POS        fija la posición actual del potenciómetro como 0 mm
 *     TEST:HX711      lectura puntual de la celda de carga
 *     TEST:POT        lectura puntual del potenciómetro
 *     TEST:TEMP       escaneo + lectura puntual de los DS18B20
 *     STREAM:ON/OFF   activa/desactiva el envío continuo de datos
 *   ESP32 -> GUI (streaming, cada 100 ms):
 *     {"t":<ms>,"fuerza_raw":<cuentas>,"fuerza_n":<N>,
 *      "pos_raw":<cuentas ADC>,"pos_mm":<mm>,
 *      "temp1":<°C>,"temp2":<°C>}
 */

#include <Arduino.h>
#include <HX711.h>
#include <OneWire.h>
#include <DallasTemperature.h>

// ----- Selección de placa (automática, no editar) -----
#if defined(ARDUINO_ARCH_AVR)
  #define BOARD_UNO
#elif defined(CONFIG_IDF_TARGET_ESP32S3)
  #define BOARD_ESP32S3
#elif defined(ARDUINO_ARCH_ESP32)
  #define BOARD_ESP32_CLASICO
#else
  #error "Placa no soportada: usa Arduino Uno, ESP32-WROOM-32 o ESP32-S3"
#endif

// ----- Pines y parámetros por placa -----
#if defined(BOARD_UNO)
  #define HX711_DOUT_PIN   6
  #define HX711_SCK_PIN    7
  #define POT_PIN          A0
  #define ONEWIRE_PIN      2
  #define POT_VREF         5.0f
  #define POT_ADC_MAX      1023.0f
#elif defined(BOARD_ESP32_CLASICO)
  #define HX711_DOUT_PIN   16
  #define HX711_SCK_PIN    17
  #define POT_PIN          34   // ADC1_CH6, solo entrada
  #define ONEWIRE_PIN      4
  #define POT_VREF         3.3f
  #define POT_ADC_MAX      4095.0f
#elif defined(BOARD_ESP32S3)
  #define HX711_DOUT_PIN   4
  #define HX711_SCK_PIN    5
  #define POT_PIN          1    // ADC1_CH0
  #define ONEWIRE_PIN      6
  #define POT_VREF         3.3f
  #define POT_ADC_MAX      4095.0f
#endif
// Recorrido físico (mm) correspondiente al rango completo del potenciómetro.
// Gefran LT-M-0150-S: 150 mm de carrera.
#define POT_RECORRIDO_MM 150.0f

// Invierte el sentido de lectura si 0 mm (comprimido) y máximo (extendido)
// quedan al revés según el cableado físico. Cambia a false si se invierten
// los cables café/verde-amarillo del potenciómetro.
#define POT_INVERTIR_SENTIDO true

HX711 balanza;
OneWire oneWire(ONEWIRE_PIN);
DallasTemperature sensoresTemp(&oneWire);
DeviceAddress direccionTemp1;
DeviceAddress direccionTemp2;
bool temp1Detectado = false;
bool temp2Detectado = false;

float factorCalibracionCelda = 1.0f; // cuentas crudas por Newton
long offsetCelda = 0;
long posicionReferenciaRaw = 0;

bool streaming = false;
unsigned long ultimoEnvio = 0;
const unsigned long intervaloEnvioMs = 100;

void detectarSensoresTemperatura() {
  sensoresTemp.begin();
  temp1Detectado = sensoresTemp.getAddress(direccionTemp1, 0);
  temp2Detectado = sensoresTemp.getAddress(direccionTemp2, 1);
}

float leerTemperatura(DeviceAddress direccion, bool detectado) {
  if (!detectado) return -127.0f; // valor centinela: sensor no detectado
  return sensoresTemp.getTempC(direccion);
}

float leerFuerzaN() {
  if (!balanza.is_ready() || factorCalibracionCelda == 0.0f) return 0.0f;
  long crudo = balanza.read() - offsetCelda;
  return (float)crudo / factorCalibracionCelda;
}

// Promedia varias lecturas del ADC para reducir el ruido típico del ESP32/Arduino.
// Descarta el valor más alto y más bajo (recorte de picos) antes de promediar.
int leerPotCrudo() {
  const int muestras = 32;
  int lecturas[muestras];
  for (int i = 0; i < muestras; i++) {
    lecturas[i] = analogRead(POT_PIN);
    delayMicroseconds(200);
  }
  // Orden simple por inserción (muestras es pequeño, no afecta el tiempo real).
  for (int i = 1; i < muestras; i++) {
    int clave = lecturas[i];
    int j = i - 1;
    while (j >= 0 && lecturas[j] > clave) {
      lecturas[j + 1] = lecturas[j];
      j--;
    }
    lecturas[j + 1] = clave;
  }
  long suma = 0;
  const int descarte = 4; // descarta los 4 más bajos y los 4 más altos
  for (int i = descarte; i < muestras - descarte; i++) {
    suma += lecturas[i];
  }
  int promedio = (int)(suma / (muestras - 2 * descarte));
#if POT_INVERTIR_SENTIDO
  promedio = (int)POT_ADC_MAX - promedio;
#endif
  return promedio;
}

float leerPosicionMM() {
  int crudo = leerPotCrudo();
  long relativo = crudo - posicionReferenciaRaw;
  return (relativo / POT_ADC_MAX) * POT_RECORRIDO_MM;
}


void enviarLecturaCompleta() {
  long fuerzaRaw = balanza.is_ready() ? balanza.read() : 0;
  float fuerzaN = leerFuerzaN();
  int posRaw = leerPotCrudo();
  float posMM = leerPosicionMM();
  sensoresTemp.requestTemperatures();
  float t1 = leerTemperatura(direccionTemp1, temp1Detectado);
  float t2 = leerTemperatura(direccionTemp2, temp2Detectado);

  Serial.print("{");
  Serial.print("\"t\":"); Serial.print(millis());
  Serial.print(",\"fuerza_raw\":"); Serial.print(fuerzaRaw);
  Serial.print(",\"fuerza_n\":"); Serial.print(fuerzaN, 3);
  Serial.print(",\"pos_raw\":"); Serial.print(posRaw);
  Serial.print(",\"pos_mm\":"); Serial.print(posMM, 3);
  Serial.print(",\"temp1\":"); Serial.print(t1, 2);
  Serial.print(",\"temp2\":"); Serial.print(t2, 2);
  Serial.println("}");
}

void responderAck(const String &mensaje) {
  Serial.print("{\"ack\":\"");
  Serial.print(mensaje);
  Serial.println("\"}");
}

void probarCelda() {
  bool listo = balanza.is_ready();
  long crudo = listo ? (balanza.read() - offsetCelda) : 0;
  float fuerzaN = leerFuerzaN();
  Serial.print("{\"test\":\"HX711\",\"ok\":");
  Serial.print(listo ? "true" : "false");
  Serial.print(",\"raw\":"); Serial.print(crudo);
  Serial.print(",\"fuerza_n\":"); Serial.print(fuerzaN, 3);
  Serial.println("}");
}

void probarPotenciometro() {
  int crudo = leerPotCrudo();
  float volts = (crudo / POT_ADC_MAX) * POT_VREF;
  float posMM = leerPosicionMM();
  Serial.print("{\"test\":\"POT\",\"ok\":true");
  Serial.print(",\"raw\":"); Serial.print(crudo);
  Serial.print(",\"volts\":"); Serial.print(volts, 3);
  Serial.print(",\"pos_mm\":"); Serial.print(posMM, 3);
  Serial.println("}");
}

void probarTemperatura() {
  detectarSensoresTemperatura();
  sensoresTemp.requestTemperatures();
  float t1 = leerTemperatura(direccionTemp1, temp1Detectado);
  float t2 = leerTemperatura(direccionTemp2, temp2Detectado);
  int cantidad = sensoresTemp.getDeviceCount();
  Serial.print("{\"test\":\"TEMP\",\"ok\":");
  Serial.print((temp1Detectado || temp2Detectado) ? "true" : "false");
  Serial.print(",\"detectados\":"); Serial.print(cantidad);
  Serial.print(",\"temp1_ok\":"); Serial.print(temp1Detectado ? "true" : "false");
  Serial.print(",\"temp2_ok\":"); Serial.print(temp2Detectado ? "true" : "false");
  Serial.print(",\"temp1\":"); Serial.print(t1, 2);
  Serial.print(",\"temp2\":"); Serial.print(t2, 2);
  Serial.println("}");
}

void procesarComando(String linea) {
  linea.trim();
  if (linea.length() == 0) return;

  if (linea == "PING") {
    responderAck("PONG");
  } else if (linea == "TARE") {
    if (balanza.is_ready()) offsetCelda = balanza.read();
    responderAck("TARE_OK");
  } else if (linea.startsWith("CAL:")) {
    float pesoKg = linea.substring(4).toFloat();
    if (pesoKg > 0 && balanza.is_ready()) {
      long crudo = balanza.read() - offsetCelda;
      float pesoN = pesoKg * 9.80665f;
      factorCalibracionCelda = crudo / pesoN;
      Serial.print("{\"ack\":\"CAL_OK\",\"factor\":");
      Serial.print(factorCalibracionCelda, 6);
      Serial.println("}");
    } else {
      responderAck("CAL_ERROR");
    }
  } else if (linea == "ZERO_POS") {
    posicionReferenciaRaw = leerPotCrudo();
    responderAck("ZERO_POS_OK");
  } else if (linea == "TEST:HX711") {
    probarCelda();
  } else if (linea == "TEST:POT") {
    probarPotenciometro();
  } else if (linea == "TEST:TEMP") {
    probarTemperatura();
  } else if (linea == "STREAM:ON") {
    streaming = true;
    responderAck("STREAM_ON");
  } else if (linea == "STREAM:OFF") {
    streaming = false;
    responderAck("STREAM_OFF");
  }
}

void setup() {
  Serial.begin(115200);
  delay(200);

  balanza.begin(HX711_DOUT_PIN, HX711_SCK_PIN);
  balanza.set_scale();
  if (balanza.is_ready()) {
    offsetCelda = balanza.read();
  }

#if defined(ARDUINO_ARCH_ESP32)
  analogReadResolution(12);
  pinMode(POT_PIN, INPUT);
  analogSetPinAttenuation(POT_PIN, ADC_11db); // habilita rango completo 0-3.3V
#else
  pinMode(POT_PIN, INPUT); // Arduino Uno: ADC fijo de 10 bits, sin configuración extra
#endif
  posicionReferenciaRaw = leerPotCrudo();

  detectarSensoresTemperatura();

  responderAck("READY");
}

void loop() {
  if (Serial.available()) {
    String linea = Serial.readStringUntil('\n');
    procesarComando(linea);
  }

  if (streaming && (millis() - ultimoEnvio >= intervaloEnvioMs)) {
    ultimoEnvio = millis();
    enviarLecturaCompleta();
  }
}
