# Guía de sustentación

Estas son mis notas de estudio para defender este proyecto — no es un manual de usuario, es la preparación que hice para explicar **por qué** el código funciona como funciona, con las preguntas que más me esperaba que me hicieran y la respuesta corta que preparé para cada una.

## Mapa rápido del código

`main.py` tiene 4 bloques:

1. **Configuración de pines y constantes** (líneas 1-75): pines del semáforo, del display, del micrófono, potenciómetro, DAC y touch.
2. **Funciones de sonido** — `tocar_nota()`, `tocar_melodia()`, `verificar_touch()`.
3. **Funciones de display** — `mostrar_numero_1s()` (cuenta peatonal) y `mostrar_vumetro_display()` (nivel de audio).
4. **Ciclo principal** (`while True`) — una máquina de estados con 3 modos: inactivo / vúmetro / semáforo.

---

## Recorrido línea por línea — configuración inicial

Antes de entrar en las funciones (que ya se explican por criterio más abajo), así es como leo el bloque de configuración de arriba a abajo, línea por línea, que es como estudié originalmente todo el archivo:

```python
from machine import Pin, ADC, mem32, DAC, TouchPad
from time import sleep, sleep_ms, sleep_us, ticks_ms
import math
```
Importo solo lo que uso: `Pin` para entradas/salidas digitales, `ADC` para leer el micrófono y el potenciómetro, `mem32` para escribir el registro GPIO de un solo golpe, `DAC` para la melodía, `TouchPad` para el sensor capacitivo. De `time` traigo `sleep`/`sleep_ms`/`sleep_us` (pausas en distintas escalas) y `ticks_ms` (reloj interno para los antirrebotes). `math` es solo para `math.sin()` de la melodía.

```python
pines_semaforo = [12, 13, 14, 19, 22, 23, 26, 27]
for p in pines_semaforo:
    Pin(p, Pin.OUT)
```
Recorro la lista de los 8 pines del semáforo y los configuro como salida. Ojo: no guardo estos objetos `Pin` en ninguna variable — una vez que MicroPython sabe que son salidas, el encendido/apagado real más adelante no pasa por estos objetos sino por `mem32[GPIO]` directamente.

```python
seg = [Pin(5, Pin.OUT), Pin(15, Pin.OUT), Pin(16, Pin.OUT),
       Pin(17, Pin.OUT), Pin(18, Pin.OUT), Pin(32, Pin.OUT), Pin(33, Pin.OUT)]
```
Aquí sí guardo los objetos `Pin`, porque los segmentos del display (a a g) sí se controlan uno por uno con `.value()` más adelante, no por `mem32`. El orden de la lista importa: `seg[0]` es el segmento a, `seg[1]` es b, y así sucesivamente — ese orden es el que después indexa la matriz `DIGITOS`.

```python
dig_decenas  = Pin(0, Pin.OUT)
dig_unidades = Pin(2, Pin.OUT)
dig_decenas.value(1)
dig_unidades.value(1)
for s in seg:
    s.value(0)
```
Los pines que seleccionan qué dígito está activo (cátodo común). Los pongo en `1` (apagado, por la lógica invertida del cátodo) y limpio todos los segmentos en `0`, para que el display arranque completamente apagado y no muestre basura al encender la placa.

```python
GPIO = const(0x3FF44004)
```
La dirección de memoria del registro de salida GPIO del ESP32. `const()` le dice a MicroPython que este valor no cambia nunca, lo que le permite optimizar el código (no tiene que revisarlo en cada vuelta del ciclo).

```python
mic = ADC(Pin(39), atten=ADC.ATTN_11DB)
mic.width(ADC.WIDTH_11BIT)
UMBRAL_SONIDO = 600
UMBRAL_RUIDO_VUMETRO = 340
```
El micrófono en el pin 39 (que es entrada-only, por eso no sirve para salidas). `atten=ADC.ATTN_11DB` amplía el rango de lectura a 0-3.3V completos (sin esto, el ESP32 solo leería hasta 1.1V). `width(WIDTH_11BIT)` fija la resolución en 2048 escalones (0 a 2047). Los dos umbrales se explican en detalle en los criterios 1 y 2 más abajo.

```python
pot = ADC(Pin(35), atten=ADC.ATTN_11DB)
pot.width(ADC.WIDTH_11BIT)
```
Mismo tipo de configuración que el micrófono, pero para el potenciómetro que regula el brillo del display.

```python
salida = DAC(Pin(25))
```
El único pin DAC1 del ESP32 (el otro es el pin 26, DAC2). Por aquí sale la señal analógica real de la melodía hacia el buzzer.

```python
UMBRAL_TOUCH = 600
toque        = TouchPad(Pin(4))
ultimo_touch = 0
```
El sensor táctil en el pin 4. `ultimo_touch` arranca en 0 porque todavía no ha habido ningún toque — se actualiza cada vez que se detecta uno, para el antirrebote.

```python
N           = 50
frecuencias = [262, 330, 392, 330]
duraciones  = [300, 300, 400, 300]
```
Los parámetros de la melodía: `N` es cuántos puntos dibujo por cada ola completa de la onda seno. Las listas de frecuencias (en Hz — Do, Mi, Sol, Mi) y duraciones (en ms) están alineadas por posición: la nota `frecuencias[0]` dura `duraciones[0]`, etc.

```python
VERDE_CALLE = 0b00000100010000000100000000000000
# ... (resto de patrones binarios)
```
Cada constante es un número de 32 bits que representa el estado de todos los pines del registro GPIO a la vez — el detalle bit por bit de qué significa cada posición está en el comentario justo arriba de estas líneas en el código, y se explica a fondo en el Criterio 1.

Con esto termina la configuración. De aquí en adelante, el código son funciones — y esas ya están explicadas por criterio en las secciones de arriba.

---

## Criterio 1 — Semáforo y display de 2 dígitos

### ¿Por qué `mem32[GPIO]` en vez de `pin.value(1)` uno por uno?

Si prendiera cada LED por separado, habría un instante microscópico entre una instrucción y la siguiente donde el semáforo queda en un estado intermedio raro (por ejemplo, un milisegundo con dos calles en verde). Escribiendo los 32 bits del registro GPIO de una sola vez, los 8 LEDs cambian en el mismo ciclo de reloj del procesador — no hay estado intermedio posible.

```python
GPIO = const(0x3FF44004)
mem32[GPIO] = VERDE_CALLE   # cambia los 8 LEDs de golpe
```

### ¿Por qué el cátodo común se maneja "al revés"?

`dig_decenas.value(1)` **apaga** el dígito y `.value(0)` lo **enciende**. Es la lógica invertida del cátodo común: el segmento (ánodo) tiene 3.3V fijo; si el cátodo también está en 3.3V no hay diferencia de potencial y no fluye corriente (apagado). Si el cátodo baja a 0V (GND), sí fluye corriente (encendido).

### ¿Cómo controla el brillo el potenciómetro sin usar PWM de hardware?

La primera versión de este código usaba `PWM(Pin(0)).duty()`. La cambié por un enfoque más simple: en vez de variar el *duty cycle*, varío **cuánto tiempo** queda encendido cada dígito en cada ciclo de multiplexado.

```python
on_time  = (val_pot * 5) // 2047   # 0 a 5 ms según el potenciómetro
off_time = 5 - on_time
```

Es una regla de 3: el potenciómetro entrega 0–2047, y la escojo mapear a un rango de 0–5 ms de tiempo encendido. A más tiempo encendido por ciclo, más brillo percibido (el ojo integra la luz en el tiempo, igual que con PWM — solo que aquí el "duty cycle" lo controlo con `sleep_ms()` en vez de con hardware dedicado).

### ¿Por qué apaga el dígito por completo antes de mostrar el otro?

Para evitar el **efecto fantasma** (ghosting): si cambio los segmentos del segundo dígito mientras el cátodo del primero todavía no ha terminado de apagarse, por una fracción de segundo se mezclan los dos números y se ve borroso. El `off_time` es ese margen de limpieza entre uno y otro.

### ¿Por qué el botón peatonal usa interrupción (IRQ) y no se revisa dentro del `while True`?

Porque el `while True` pasa buena parte del tiempo "dormido" dentro de `esperar()` (en pausas de `sleep(0.1)`). Una interrupción de hardware no espera su turno: en el instante en que sube el voltaje del pin, el procesador para lo que esté haciendo, atiende el botón, y sigue. Así nunca se pierde una pulsación del peatón, sin importar en qué parte del ciclo del semáforo esté el sistema en ese momento.

```python
pulsador1.irq(trigger=Pin.IRQ_RISING, handler=activar_peatonal)
```

**Antirrebote (`> 800`):** un botón físico "rebota" — las láminas metálicas chocan varias veces al presionarlas, y sin control el ESP32 leería 10-20 pulsaciones falsas por una sola presión real. Por eso se ignora cualquier pulsación nueva que llegue antes de 800ms desde la última válida.

**¿Por qué la función recibe un parámetro `pin` que nunca se usa?**
Porque así funciona el mecanismo de interrupciones en MicroPython: cuando se dispara un IRQ, el sistema *siempre* le pasa el objeto `Pin` responsable a la función manejadora. Si la función se definiera sin parámetros (`def activar_peatonal():`), el programa lanzaría un `TypeError` en el instante en que se presione el botón, porque MicroPython intentaría entregarle un argumento a una función que no lo espera.

### ¿Cómo cuenta el contador peatonal 15 segundos sin usar `sleep()`?

```python
for cuenta in range(15, 0, -1):
    mostrar_numero_1s(cuenta)
```

`mostrar_numero_1s()` tarda exactamente ~1 segundo en ejecutarse (son 100 ciclos de multiplexado, cada uno de `on_time + off_time` para cada dígito). En vez de dormir 1 segundo y aparte refrescar el display, la función de display *es* el cronómetro: mientras dibuja el número, el tiempo que tarda en hacerlo ya es el segundo que necesito contar.

---

## Criterio 2 — Vúmetro de audio

### ¿Qué es el "noise gate" (`UMBRAL_RUIDO_VUMETRO`)?

Ningún micrófono analógico lee un cero perfecto en silencio — siempre hay ruido eléctrico de fondo (en este circuito, entre 150 y 300 aprox). Sin filtro, los primeros LEDs del vúmetro parpadearían solos aunque nadie esté hablando. La solución es forzar a 0 cualquier lectura por debajo de `UMBRAL_RUIDO_VUMETRO = 340`.

### ¿Por qué se reutilizan los mismos 8 LEDs del semáforo para el vúmetro?

No hay LEDs adicionales en el circuito para esto — es un truco de diseño: cada nivel de volumen enciende un LED más que el anterior (ver `NIVELES_VUMETRO`), dando el efecto visual de una barra progresiva, sin necesitar hardware extra.

### ¿Por qué el display del vúmetro solo enciende 2-3 segmentos en vez del número completo?

A propósito. La matriz `DIGITOS` está pensada para dibujar dígitos completos (0-9), pero para el vúmetro yo quería un patrón más simple y rápido de refrescar: solo los segmentos `c` y `e`. Con menos segmentos cambiando de estado en cada ciclo, hay menos parpadeo y el número igual se alcanza a leer.

---

## Criterio 3 — Touch y melodía por DAC

### ¿Por qué una onda senoidal y no una onda cuadrada?

Un buzzer activo con onda cuadrada (encendido/apagado brusco) suena como un pitido áspero y robótico. El DAC del ESP32 puede generar voltajes intermedios reales, así que en vez de eso dibujo una onda seno completa — el sonido resultante es un tono limpio, más parecido a una nota musical real.

```python
valor = int(127.5 * (math.sin(2 * math.pi * freq * i / N) + 1))
```

Esto mapea el rango del seno (-1 a 1) al rango de 8 bits del DAC (0 a 255): sumar 1 lo lleva a (0 a 2), multiplicar por 127.5 lo estira a (0 a 255).

### ¿Para qué sirven los dos `for` anidados en `tocar_nota()`?

- El `for` de adentro (`range(N)`) dibuja **una sola ola completa** de la onda (50 puntos).
- El `for` de afuera (`range(ciclos)`) repite esa ola tantas veces como haga falta para llenar la duración pedida en milisegundos.

Una sola ola de una nota grave dura apenas unos milisegundos — muy poco para que el oído lo perciba como una nota. Repetirla decenas de veces seguidas es lo que la hace sonar como un tono sostenido.

### ¿Por qué el touch se revisa constantemente (polling) y no con interrupción, como los botones?

El sensor capacitivo de MicroPython (`TouchPad`) no genera una interrupción de hardware — se lee activamente su valor de capacitancia cada vez que el programa lo consulta. Por eso `verificar_touch()` se llama tanto en el ciclo principal como dentro de `esperar()` cada 100ms: así el toque se detecta casi en cualquier momento, sin depender de una alarma que el sensor no puede disparar por sí solo.

**Antirrebote (`> 1000`):** un toque de medio segundo con el dedo puede ser leído cientos de veces por el procesador. Sin este control, la melodía se reiniciaría una y otra vez sin terminar de sonar nunca.

---

## Chuleta rápida (para repasar 5 minutos antes de sustentar)

| Pregunta | Respuesta en una frase |
|---|---|
| ¿Por qué `mem32` y no `pin.value()`? | Cambia los 8 LEDs en el mismo ciclo de reloj — sin estados intermedios peligrosos |
| ¿Por qué `value(1)` apaga el display? | Cátodo común: sin diferencia de potencial entre segmento y cátodo, no hay corriente |
| ¿Cómo regula el brillo el potenciómetro? | Variando cuánto tiempo (ms) queda encendido cada dígito por ciclo, no con PWM |
| ¿Por qué se apaga el display entre dígitos? | Evita el efecto fantasma (ghosting) al cambiar de número |
| ¿Por qué IRQ en los botones? | El programa puede estar "dormido" en un `sleep()`; una IRQ interrumpe eso al instante |
| ¿Por qué el antirrebote de 800ms/1000ms? | Un botón/touch real genera varias lecturas falsas por una sola pulsación |
| ¿Cómo cuenta 15s sin `sleep()`? | `mostrar_numero_1s()` tarda ~1s en ejecutarse — la función de display es el cronómetro |
| ¿Qué es el noise gate del vúmetro? | Ignora lecturas de ruido de fondo por debajo de un umbral, para que no titile solo |
| ¿Por qué LEDs del semáforo en el vúmetro? | No hay hardware extra — se reutilizan, prendiendo uno más por nivel |
| ¿Por qué onda seno en vez de cuadrada? | El DAC permite un tono limpio; una onda cuadrada suena áspera/robótica |
| ¿Por qué el touch usa polling? | El `TouchPad` de MicroPython no genera interrupciones de hardware |
| ¿Por qué la función IRQ recibe `pin` sin usarlo? | MicroPython siempre entrega ese argumento al disparar la interrupción — omitirlo causa `TypeError` |

---

## Cómo preparé esta sustentación

Fui función por función, línea por línea, hasta entender el *por qué* de cada una (no solo el qué), anticipando las preguntas que más me podían hacer en la sustentación. Esta guía es la versión organizada y condensada de esas notas de estudio, hecha en julio de 2026 a partir del código y comentarios ya definitivos del proyecto.
