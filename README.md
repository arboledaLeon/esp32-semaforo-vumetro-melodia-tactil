# Semáforo ESP32 con Vúmetro y Melodía

Semáforo vehicular/peatonal en MicroPython que además funciona como vúmetro de audio y toca una melodía al tocar un sensor capacitivo — todo en el mismo ESP32.

## 🔧 Hardware

- **Board:** ESP32 D1 R32 (MicroPython)
- **Componentes:**
  - 8 LEDs (semáforo vehicular de 2 vías + semáforo peatonal)
  - Display 7 segmentos de 2 dígitos, cátodo común
  - Micrófono electret (para arrancar el sistema con un aplauso/grito y para el vúmetro)
  - Potenciómetro (controla el brillo del display)
  - Buzzer pasivo (melodía vía DAC)
  - Sensor táctil capacitivo (cable pelado ~3cm)
  - 2 pulsadores

**Conexiones** (según el código):

| Función | Pin | Notas |
|---|---|---|
| Amarillo/Rojo/Verde Calle | GPIO12 / 13 / 14 | Semáforo vehicular vía 1 |
| Amarillo/Rojo/Verde Carrera | GPIO27 / 26 / 23 | Semáforo vehicular vía 2 |
| Rojo/Verde Peatonal | GPIO22 / 19 | |
| Segmentos a–g del display | GPIO5, 15, 16, 17, 18, 32, 33 | |
| Dígito decenas / unidades | GPIO0 / GPIO2 | **Necesitan resistencia de 10kΩ a 3.3V** — son pines de arranque del ESP32 |
| Micrófono | GPIO39 (VN) | 3.3V–1kΩ–nodo–Mic(+), nodo–0.1µF–GPIO39–GND |
| Potenciómetro | GPIO35 | 3.3V / GND / cursor a GPIO35 |
| Buzzer pasivo (DAC) | GPIO25 | Con resistencia de 100Ω en serie |
| Touch | GPIO4 | Cable pelado como electrodo |
| Pulsador ciclo peatonal | GPIO34 | Pull-down externo 10kΩ a GND |
| Pulsador alternar modo | GPIO36 | Pull-down externo 10kΩ a GND |

## ⚙️ Qué hace

El sistema arranca inactivo y espera un sonido fuerte (aplauso/grito) captado por el micrófono para empezar el ciclo del semáforo. Mientras corre, un pulsador puede pedir un ciclo peatonal (con cuenta regresiva de 15s en el display) y otro pulsador cambia a "modo vúmetro", donde los mismos 8 LEDs del semáforo se usan como una barra de nivel de audio y el display muestra el nivel numérico (0-99). En cualquier momento, tocar el sensor capacitivo dispara una melodía de 4 notas generada con una onda senoidal por el DAC, sin interrumpir lo demás.

## 🐛 Problemas que encontré y cómo los resolví

- **GPIO34 (pulsador peatonal) daba lecturas caóticas:** un pin de entrada sin nada conectado "flota" y capta ruido eléctrico del ambiente, leyendo 0 y 1 al azar sin que nadie toque el botón. Lo resolví agregando una resistencia pull-down externa de 10kΩ a GND, que fuerza el pin a 0V estable cuando el botón no está presionado.
- **GPIO0 y GPIO2 (selección de dígitos del display) son pines de arranque del ESP32:** si quedan en el estado equivocado durante el boot, la placa puede fallar al arrancar. La solución fue agregar una resistencia pull-up externa de 10kΩ a 3.3V en cada uno, para garantizar que arranquen en HIGH sin afectar su uso normal después del boot.
- **Regular el brillo del display sin usar PWM de hardware:** la consigna era controlar el semáforo con `mem32` y tiempos fijos, sin el periférico de PWM del ESP32. Para tener brillo regulable en el display de todos modos, terminé simulando un "PWM por software": alternar encendido y apagado a alta velocidad según la lectura del potenciómetro, en vez de usar `PWM().duty()`.

## 🚀 Cómo compilarlo / flashearlo

1. Instala MicroPython en el ESP32 (con `esptool` o Thonny: Tools → Install/Update firmware).
2. Sube `main.py` a la placa. Este proyecto usa [Pymakr](https://marketplace.visualstudio.com/items?itemName=pycom.Pymakr) (extensión de VS Code) — el archivo `pymakr.conf` ya está configurado. También funciona con Thonny o `ampy`.
3. No requiere librerías externas: solo usa módulos incluidos en MicroPython (`machine`, `time`, `math`).
4. Arma el circuito según la tabla de conexiones de arriba.
5. Reinicia la placa. Por el monitor serial verás `"Sistema en espera... aplaudí o gritá para arrancar"`.

## 📸 Demo

*(Agrega aquí una foto o video corto del circuito armado y funcionando — no encontré fotos del montaje físico en tus documentos, solo diagramas de referencia.)*

## 🧠 Contexto de construcción

Proyecto desarrollado para la asignatura de Electrónica Digital 2-2026-1.ITM (Ingeniería Biomédica). Código, comentarios y esta documentación revisados y pulidos en julio de 2026 para reflejar con precisión cómo funciona el sistema.
