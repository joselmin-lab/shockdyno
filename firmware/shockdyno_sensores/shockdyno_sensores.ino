/*
 * ShockDyno - Firmware de sensores (ESP32)
 * -----------------------------------------
 * Lee celda de carga (HX711), potenciómetro lineal (ADC) y dos sensores
 * de temperatura DS18B20, y los expone por puerto serie (USB) en formato
 * JSON para la GUI de PyQt (gui_dinamometro.py).
 *
 * Librerías necesarias (Arduino Library Manager):
 *   - HX711 (bogde/HX711)
 *   - OneWire (PaulStoffregen/OneWire)
 *   - DallasTemperature (milesburton/Arduino-Temperature-Control-Library)
 *
 * Conexiones sugeridas (ESP32 DevKit):
 *   HX711   DOUT -> GPIO16   SCK -> GPIO4
 *   Potenciómetro (salida) -> GPIO34 (ADC1, solo entrada)
 *   DS18B20 x2 (bus OneWire compartido) -> GPIO15 con resistencia
 *     pull-up de 4.7k entre datos y 3.3V
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

// ----- Pines -----
#define HX711_DOUT_PIN   16
#define HX711_SCK_PIN    4
#define POT_PIN          34   // ADC1_CH6, pin de solo entrada en ESP32
#define ONEWIRE_PIN      15

// ----- Parámetros -----
#define POT_VREF         3.3f
#define POT_ADC_MAX      4095.0f
// Recorrido físico (mm) correspondiente al rango completo del potenciómetro.
// Ajustar según el montaje mecánico real.
#define POT_RECORRIDO_MM 100.0f

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

float leerPosicionMM() {
  int crudo = analogRead(POT_PIN);
  long relativo = crudo - posicionReferenciaRaw;
  return (relativo / POT_ADC_MAX) * POT_RECORRIDO_MM;
}

void enviarLecturaCompleta() {
  long fuerzaRaw = balanza.is_ready() ? balanza.read() : 0;
  float fuerzaN = leerFuerzaN();
  int posRaw = analogRead(POT_PIN);
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
  int crudo = analogRead(POT_PIN);
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
    posicionReferenciaRaw = analogRead(POT_PIN);
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

  analogReadResolution(12);
  pinMode(POT_PIN, INPUT);
  posicionReferenciaRaw = analogRead(POT_PIN);

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
