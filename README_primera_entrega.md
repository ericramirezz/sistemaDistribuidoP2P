# Sistema de Mensajería Distribuida P2P: Correspondiente a la primera entrega

Implementación de mensajería distribuida por sockets TCP con programación paralela (hilos).  
**Materia:** Sistemas Distribuidos  
**Entorno:** Debian 12 (Bookworm) en VMs KVM/QEMU sobre Fedora

---

## Requisitos

- Python 3.x (incluido en Debian 12 por defecto, sin dependencias externas)
- Conectividad de red entre los nodos (`192.168.122.x`)

---

## Archivos

| Archivo | Descripción |
|---|---|
| `node.py` | Programa principal (servidor + cliente en paralelo) |
| `config.json` | Configuración del nodo local y mapa de la red |
| `historial.json` | Generado automáticamente; almacena mensajes y ACKs |

---

## Configuración por VM

Copia `node.py` y `config.json` a cada VM. En cada VM **edita únicamente** el campo `hostname`:

**VM 1 — nodo1**
```json
{
    "hostname": "nodo1",
    "puerto": 5000,
    "nodos": {
        "nodo1": "192.168.122.101",
        "nodo2": "192.168.122.102",
        "nodo3": "192.168.122.103"
    }
}
```

**VM 2 — nodo2**
```json
{
    "hostname": "nodo2",
    ...
}
```

> La sección `nodos` es **idéntica en todas las VMs**; solo cambia `hostname`.

---

## Despliegue rápido con SCP

Desde el host Fedora, copia los archivos a cada VM en un solo paso:

```bash
# Nodo 1
scp node.py config.json usuario@192.168.122.101:~/mensajeria/

# Nodo 2 (cambia hostname antes o edítalo en la VM)
scp node.py config.json usuario@192.168.122.102:~/mensajeria/

# Nodo 3
scp node.py config.json usuario@192.168.122.103:~/mensajeria/
```

---

## Ejecución

En cada VM, dentro del directorio de trabajo:

```bash
python3 node.py
```

Verás:

```
[SERVIDOR] Escuchando en 192.168.122.101:5000 ...

════════════════════════════════════════
   NODO ACTIVO: NODO1  (192.168.122.101)
════════════════════════════════════════
  1. Enviar a TODOS (Broadcast)
  2. Enviar a nodo2 (192.168.122.102)  [Privado]
  3. Enviar a nodo3 (192.168.122.103)  [Privado]
  4. Ver historial local
  5. Salir
════════════════════════════════════════
  Seleccion (1-5):
```

---

## Flujo de operación

```
EMISOR                          RECEPTOR
  │                                │
  │── TCP connect ────────────────▶│
  │── {tipo:MENSAJE, timestamp,    │
  │    text, sender, ...} ────────▶│
  │                                │── guardar en historial.json
  │                                │── mostrar alerta en pantalla
  │◀── {tipo:ACK, status,         │
  │     timestamp_receptor} ───────│── guardar ACK en historial.json
  │── guardar ACK en historial.json│
  │── mostrar confirmación         │
```

---

## Formato de historial.json

```json
[
    {
        "tipo": "MENSAJE",
        "msg_id": "nodo1-20261027183500123456",
        "sender": "nodo1",
        "destino": "nodo2",
        "text": "Hola desde nodo1",
        "timestamp": "2026-10-27 18:35:00",
        "alcance": "privado"
    },
    {
        "tipo": "ACK",
        "emisor": "nodo2",
        "para": "nodo1",
        "msg_id": "nodo1-20261027183500123456",
        "status": "recibido",
        "timestamp": "2026-10-27 18:35:01"
    }
]
```

---

## Comportamiento paralelo

| Componente | Modelo de concurrencia |
|---|---|
| Servidor | 1 hilo por conexión entrante (`threading.Thread`) |
| Broadcast | 1 hilo por nodo destino (envíos simultáneos) |
| Escritura a disco | Mutex (`threading.Lock`) — thread-safe |
| Impresión en consola | Mutex (`threading.Lock`) — sin mezcla de salidas |

---

## Verificar IPs de las VMs

```bash
# En cada VM
ip addr show
# o
hostname -I
```

---

## Prueba rápida desde host

```bash
# Verifica que el puerto 5000 esté escuchando en una VM
nc -zv 192.168.122.101 5000
```
