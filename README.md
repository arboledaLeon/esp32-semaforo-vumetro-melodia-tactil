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

- **Import roto que impedía arrancar el programa:** una versión anterior de este código controlaba el brillo del display con PWM de hardware. Cuando pasé a controlar el brillo con un `Pin` digital simple y tiempos calculados en milisegundos (como pidió el profesor), quedó un `import pwm` suelto y sin usar — y encima mal escrito (la clase real se llama `PWM`, en mayúscula). En el ESP32 real esto lanza un `ImportError` y el script ni siquiera arranca. Lo resolví eliminando el import muerto.
- **Dos umbrales sin nombre que coincidían por casualidad:** el umbral del touch y el umbral del micrófono para arrancar el sistema tenían el mismo valor (600) sin relación real entre ellos — uno mide capacitancia, el otro volumen de sonido. Los convertí en constantes con nombre (`UMBRAL_TOUCH`, `UMBRAL_SONIDO`) y dejé un comentario aclarando que es coincidencia, para no confundir a futuro.
- **GPIO0 y GPIO2 son pines de arranque del ESP32:** usarlos para seleccionar los dígitos del display podía interferir con el boot del microcontrolador. La solución (ya en el circuito físico) fue agregar resistencias externas de 10kΩ a 3.3V en ambos pines, para forzar el estado correcto durante el arranque.
- **Evitar un estado inseguro en el semáforo:** si cada LED se prendiera/apagara uno por uno con `pin.value()`, había un instante intermedio donde dos calles podían quedar en verde a la vez. Por eso el semáforo se controla escribiendo los 8 LEDs de una sola vez en el registro `mem32[GPIO]` — cambian todos en el mismo ciclo de reloj.

## 🚀 Cómo compilarlo / flashearlo

1. Instala MicroPython en el ESP32 (con `esptool` o Thonny: Tools → Install/Update firmware).
2. Sube `main.py` a la placa. Este proyecto usa [Pymakr](https://marketplace.visualstudio.com/items?itemName=pycom.Pymakr) (extensión de VS Code) — el archivo `pymakr.conf` ya está configurado. También funciona con Thonny o `ampy`.
3. No requiere librerías externas: solo usa módulos incluidos en MicroPython (`machine`, `time`, `math`).
4. Arma el circuito según la tabla de conexiones de arriba.
5. Reinicia la placa. Por el monitor serial verás `"Sistema en espera... aplaudí o gritá para arrancar"`.

## 📸 Demo

*(Agrega aquí una foto o video corto del circuito armado y funcionando — no encontré fotos del montaje físico en tus documentos, solo diagramas de referencia.)*

## 🧠 Contexto de construcción

Proyecto desarrollado para la asignatura de Electrónica Digital 2 (Ingeniería Biomédica). Código, comentarios y esta documentación revisados y pulidos en julio de 2026 para reflejar con precisión cómo funciona el sistema.
