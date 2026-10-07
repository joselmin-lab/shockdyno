# shockdyno

Sistema para adquisición y control del dinamómetro de amortiguadores.

## Requisitos

- Python 3.10+
- PyQt5
- matplotlib
- numpy

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

## Estructura

- `gui_dinamometro.py`: interfaz principal
- `requirements.txt`: dependencias del proyecto
