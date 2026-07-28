# main.py
# Proyecto Final: Semáforo Medellín + Vumetro + Melodía DAC + Touch
# ESP32 D1 R32 - MicroPython
# Criterio 1: Semáforo mem32 + display contador + potenciómetro en display + interrupción peatonal
# Criterio 2: Interrupción vumetro + micrófono ADC + 8 LEDs progresivos
# Criterio 3: Touch dispara melodía propia con DAC en cualquier momento

from machine import Pin, ADC, mem32, DAC, TouchPad
from time import sleep, sleep_ms, sleep_us, ticks_ms
import math

# Pines semáforo como salidas digitales
# Solo se usan aquí para fijar la dirección (OUT); el encendido real
# de cada LED se hace más abajo escribiendo directo en mem32[GPIO]
pines_semaforo = [12, 13, 14, 19, 22, 23, 26, 27]
for p in pines_semaforo:
    Pin(p, Pin.OUT)

# Pines display 7 segmentos
# seg[0]=a, seg[1]=b, seg[2]=c, seg[3]=d, seg[4]=e, seg[5]=f, seg[6]=g
seg = [Pin(5,  Pin.OUT),
       Pin(15, Pin.OUT),
       Pin(16, Pin.OUT),
       Pin(17, Pin.OUT),
       Pin(18, Pin.OUT),
       Pin(32, Pin.OUT),
       Pin(33, Pin.OUT)]

# Selección de dígitos - cátodo común, LOW activa el dígito
# GPIO0 y GPIO2 tienen R 10kΩ a 3.3V para arranque correcto del ESP32
dig_decenas  = Pin(0, Pin.OUT)
dig_unidades = Pin(2, Pin.OUT)
dig_decenas.value(1)
dig_unidades.value(1)
for s in seg:
    s.value(0)

# Registro de salida GPIO del ESP32
# Se usa en vez de pin.value(1)/(0) uno por uno porque escribir los 32 bits
# de una sola vez cambia todos los LEDs en el mismo ciclo de reloj — así se
# evita que, por un instante, dos calles queden en verde al mismo tiempo
GPIO = const(0x3FF44004)

# Micrófono - GPIO39 (VN en D1 R32)
# Circuito: 3.3V - 1kΩ - nodo - Mic(+), nodo - 0.1uF - GPIO39 - GND
# ADC1, 11 bits (0-2047), usado para arranque del semáforo y vumetro
mic = ADC(Pin(39), atten=ADC.ATTN_11DB)
mic.width(ADC.WIDTH_11BIT)
UMBRAL_SONIDO = 600  # ADC > 600 = aplauso/grito fuerte, dispara el arranque
                     # (coincide en valor con UMBRAL_TOUCH de más abajo, pero
                     # miden cosas distintas — sonido vs. capacitancia — es casualidad)
UMBRAL_RUIDO_VUMETRO = 340  # por debajo de esto se considera silencio/ruido de fondo

# Potenciómetro - GPIO35
# VCC - 3.3V, OUT - GPIO35, GND - GND
# Regula el brillo de los 2 dígitos del display 7 segmentos
pot = ADC(Pin(35), atten=ADC.ATTN_11DB)
pot.width(ADC.WIDTH_11BIT)

# DAC - GPIO25 (único DAC1 del ESP32)
# GPIO25 - 100Ω - Buzzer pasivo(+), GND - Buzzer(-)
salida = DAC(Pin(25))

# Touch - GPIO4, cable pelado ~3cm como electrodo
# Al tocar dispara la melodía inmediatamente en cualquier momento
# En reposo lee ~719, al tocar baja a ~152
UMBRAL_TOUCH = 600
toque        = TouchPad(Pin(4))
ultimo_touch = 0

# Melodía Do-Mi-Sol-Mi
# N = muestras por ciclo de onda senoidal
N           = 50
frecuencias = [262, 330, 392, 330]   # Hz: Do4, Mi4, Sol4, Mi4
duraciones  = [300, 300, 400, 300]   # ms por nota

# Patrones binarios semáforo - control por mem32
# Bit 27=AmarilloCarrera 26=RojoCarrera 23=VerdeCarrera 22=RojoPeatonal
# Bit 19=VerdePeatonal   14=VerdeCalle  13=RojoCalle    12=AmarilloCalle
VERDE_CALLE      = 0b00000100010000000100000000000000
AMARILLO_CALLE   = 0b00000100010000000001000000000000
VERDE_CARRERA    = 0b00000000110000000010000000000000
AMARILLO_CARR    = 0b00001000010000000010000000000000
VERDE_CALLE_OFF  = 0b00000100010000000000000000000000
VERDE_CARR_OFF   = 0b00000000010000000010000000000000
TODOS_APAGADOS   = 0b00000000000000000000000000000000
PEATON_VERDE     = 0b00000100000010000010000000000000
PEATON_ROJO      = 0b00000100010000000010000000000000
PEATON_VERDE_OFF = 0b00000100000000000010000000000000

# Patrones vumetro - LEDs progresivos según orden solicitado
# Reutiliza los mismos 8 LEDs del semáforo (no hay LEDs extra para el vúmetro):
# cada nivel prende un LED más que el anterior, dando el efecto de barra
# Bit 19=VerdePeat, 22=RojoPeat, 14=VerdeCalle, 12=AmarCalle
# Bit 13=RojoCalle, 23=VerdeCarr, 27=AmarCarr, 26=RojoCarr
NIVELES_VUMETRO = [
    0b00000000000000000000000000000000,  # 0 LEDs
    0b00000000000010000000000000000000,  # 1 LED  - bit19 Verde Peatonal
    0b00000000010010000000000000000000,  # 2 LEDs - +bit22 Rojo Peatonal
    0b00000000010010000100000000000000,  # 3 LEDs - +bit14 Verde Calle
    0b00000000010010000101000000000000,  # 4 LEDs - +bit12 Amarillo Calle
    0b00000000010010000111000000000000,  # 5 LEDs - +bit13 Rojo Calle
    0b00000000110010000111000000000000,  # 6 LEDs - +bit23 Verde Carrera
    0b00001000110010000111000000000000,  # 7 LEDs - +bit27 Amarillo Carrera
    0b00001100110010000111000000000000,  # 8 LEDs - +bit26 Rojo Carrera
]

# Patrones display 7 segmentos cátodo común
# [a, b, c, d, e, f, g] - 1=encendido, 0=apagado
DIGITOS = [
    [1,1,1,1,1,1,0],  # 0
    [0,1,1,0,0,0,0],  # 1
    [1,1,0,1,1,0,1],  # 2
    [1,1,1,1,0,0,1],  # 3
    [0,1,1,0,0,1,1],  # 4
    [1,0,1,1,0,1,1],  # 5
    [1,0,1,1,1,1,1],  # 6
    [1,1,1,0,0,0,0],  # 7
    [1,1,1,1,1,1,1],  # 8
    [1,1,1,1,0,1,1],  # 9
]

# Genera una onda senoidal (no cuadrada) para que la nota suene como un tono
# suave en vez del pitido áspero de un buzzer activo
# valor = 127.5*(sin(2*pi*f*i/N)+1) mapea el rango [-1,1] del seno a [0,255] del DAC
def tocar_nota(freq, duracion_ms):
    ciclos = (freq * duracion_ms) // 1000
    for _ in range(ciclos):
        for i in range(N):
            valor = int(127.5 * (math.sin(2 * math.pi * freq * i / N) + 1))
            salida.write(valor)
            sleep_us(int(1000000 / (freq * N)))
    salida.write(0)

# Toca la melodía completa Do-Mi-Sol-Mi
def tocar_melodia():
    for i in range(len(frecuencias)):
        tocar_nota(frecuencias[i], duraciones[i])
    salida.write(0)

# Criterio 3: Touch detectado dispara la melodía inmediatamente
# Antirrebote 1000ms para evitar doble activación
def verificar_touch():
    global ultimo_touch
    ahora = ticks_ms()
    if toque.read() < UMBRAL_TOUCH and (ahora - ultimo_touch > 1000):
        ultimo_touch = ahora
        print("Touch! Tocando melodia...")
        tocar_melodia()

# Criterio 1: muestra número de 2 dígitos durante 1 segundo
# Multiplexado con brillo regulado por potenciómetro
# on_time: tiempo encendido por dígito (1 a 5ms según pot)
# off_time: tiempo apagado = 5 - on_time
# Total por ciclo: 10ms — 100 ciclos = 1 segundo exacto
def mostrar_numero_1s(numero):
    decenas  = (numero // 10) % 10
    unidades = numero % 10
    val_pot  = pot.read()
    on_time  = (val_pot * 5) // 2047
    if on_time < 1:
        on_time = 1
    off_time = 5 - on_time
    for _ in range(100):
        dig_unidades.value(1)
        for i in range(7):
            seg[i].value(DIGITOS[decenas][i])
        dig_decenas.value(0)
        sleep_ms(on_time)
        dig_decenas.value(1)
        sleep_ms(off_time)
        dig_decenas.value(1)
        for i in range(7):
            seg[i].value(DIGITOS[unidades][i])
        dig_unidades.value(0)
        sleep_ms(on_time)
        dig_unidades.value(1)
        sleep_ms(off_time)
    dig_decenas.value(1)
    dig_unidades.value(1)

# Criterio 2: muestra nivel de audio 0-99 usando 3 segmentos
# A propósito no se dibuja el dígito completo (las 7 rayitas): con solo
# 2-3 segmentos el número igual se lee, y se evita el parpadeo extra de
# encender/apagar segmentos que aquí no aportan nada al vúmetro
# D2 unidades: seg c (idx 2) y seg e (idx 4)
# D1 decenas:  solo seg c (idx 2)
# Si valor es 0 apaga el display completamente
def mostrar_vumetro_display(valor_adc):
    if valor_adc == 0:
        for s in seg:
            s.value(0)
        dig_decenas.value(1)
        dig_unidades.value(1)
        return
    nivel    = (valor_adc * 99) // 2047
    decenas  = (nivel // 10) % 10
    unidades = nivel % 10
    # D2 unidades - seg c y seg e
    for s in seg:
        s.value(0)
    dig_decenas.value(1)
    seg[2].value(DIGITOS[unidades][2])
    seg[4].value(DIGITOS[unidades][4])
    dig_unidades.value(0)
    sleep_ms(5)
    dig_unidades.value(1)
    # D1 decenas - solo seg c
    for s in seg:
        s.value(0)
    seg[2].value(DIGITOS[decenas][2])
    dig_decenas.value(0)
    sleep_ms(5)
    dig_decenas.value(1)
    dig_unidades.value(1)

# Criterio 1: espera un tiempo con el estado del semáforo encendido
# LEDs siempre a brillo completo - sin PWM
# verificar_touch() cada 100ms para responder durante el semáforo
def esperar(estado, segundos):
    mem32[GPIO] = estado
    ciclos = int(segundos * 10)
    for _ in range(ciclos):
        sleep(0.1)
        verificar_touch()

# Criterio 1: Interrupción pulsador 1 - activa ciclo peatonal
# GPIO34 input-only, pull-down externo 10kΩ a GND, antirrebote 800ms
bandera_peatonal = 0
ultimo_tiempo    = 0
ciclo_en_curso   = False

def activar_peatonal(pin):
    global bandera_peatonal, ultimo_tiempo, ciclo_en_curso
    ahora = ticks_ms()
    if (ahora - ultimo_tiempo > 800) and not ciclo_en_curso:
        bandera_peatonal = 1
        ultimo_tiempo = ahora
        print("Pulsador 1! Ciclo peatonal pendiente...")

pulsador1 = Pin(34, Pin.IN)
pulsador1.irq(trigger=Pin.IRQ_RISING, handler=activar_peatonal)

# Criterio 2: Interrupción pulsador 2 - alterna modo semáforo/vumetro
# GPIO36 input-only, pull-down externo 10kΩ a GND, antirrebote 800ms
modo_vumetro     = False
ultimo_tiempo_p2 = 0

def alternar_modo(pin):
    global modo_vumetro, ultimo_tiempo_p2
    ahora = ticks_ms()
    if ahora - ultimo_tiempo_p2 > 800:
        modo_vumetro = not modo_vumetro
        ultimo_tiempo_p2 = ahora
        if modo_vumetro:
            print("Modo VUMETRO activado")
        else:
            print("Modo SEMAFORO activado")

pulsador2 = Pin(36, Pin.IN)
pulsador2.irq(trigger=Pin.IRQ_RISING, handler=alternar_modo)

# Sistema inactivo al inicio - arranca con sonido fuerte
mem32[GPIO] = TODOS_APAGADOS
sistema_activo = False
print("Sistema en espera... aplaudí o gritá para arrancar")

# Ciclo principal
while True:

    # Criterio 3: Touch se verifica en cada iteración
    # También se verifica dentro de esperar() cada 100ms
    verificar_touch()

    # Estado 1: inactivo - espera sonido fuerte
    if not sistema_activo:
        valor_mic = mic.read()
        print("Mic:", valor_mic)
        if valor_mic > UMBRAL_SONIDO:
            print("Sonido detectado! Arrancando semaforo...")
            sleep(0.5)
            sistema_activo = True

    # Estado 2: modo vumetro - criterio 2
    # Print para calibrar umbrales según ambiente
    elif modo_vumetro:
        valor = mic.read()
        print("Mic vumetro:", valor)
        if valor < UMBRAL_RUIDO_VUMETRO:
            valor = 0
        num_leds = (valor * 8) // 2047
        mem32[GPIO] = NIVELES_VUMETRO[num_leds]
        mostrar_vumetro_display(valor)

    # Estado 3: modo semáforo - criterio 1
    elif sistema_activo:

        esperar(VERDE_CALLE, 5)

        esperar(VERDE_CALLE_OFF, 0.3)
        esperar(VERDE_CALLE,     0.3)
        esperar(VERDE_CALLE_OFF, 0.3)
        esperar(VERDE_CALLE,     0.3)
        esperar(VERDE_CALLE_OFF, 0.3)
        esperar(VERDE_CALLE,     0.3)

        esperar(AMARILLO_CALLE, 2)

        esperar(VERDE_CARRERA, 5)

        esperar(VERDE_CARR_OFF, 0.3)
        esperar(VERDE_CARRERA,  0.3)
        esperar(VERDE_CARR_OFF, 0.3)
        esperar(VERDE_CARRERA,  0.3)
        esperar(VERDE_CARR_OFF, 0.3)
        esperar(VERDE_CARRERA,  0.3)

        esperar(AMARILLO_CARR, 2)

        # Ciclo peatonal - entra solo si pulsador 1 fue presionado
        if bandera_peatonal == 1:
            bandera_peatonal = 0
            ciclo_en_curso   = True
            print("Iniciando ciclo peatonal...")

            mem32[GPIO] = PEATON_VERDE

            # Contador regresivo 15s con brillo regulado por potenciómetro
            for cuenta in range(15, 0, -1):
                print("Contador:", cuenta)
                mostrar_numero_1s(cuenta)

            esperar(PEATON_VERDE_OFF, 0.3)
            esperar(PEATON_VERDE,     0.3)
            esperar(PEATON_VERDE_OFF, 0.3)
            esperar(PEATON_VERDE,     0.3)
            esperar(PEATON_VERDE_OFF, 0.3)
            esperar(PEATON_VERDE,     0.3)

            mem32[GPIO] = PEATON_ROJO
            salida.write(0)
            dig_decenas.value(1)
            dig_unidades.value(1)
            sleep(2)
            ciclo_en_curso = False
            print("Ciclo peatonal terminado. Retomando vehicular...")