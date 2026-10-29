#!/usr/bin/env python3
"""
  SISTEMA DE MENSAJERIA DISTRIBUIDA P2P - Proyecto primer avance
  Sistemas Distribuidos
  Descripcion:
    Cada nodo puede enviar y recibir mensajes de manera
    paralela usando sockets TCP. Los mensajes incluyen
    el timestamp del nodo emisor, se confirman con ACK
    automatico y se almacenan en ambos extremos.
"""

import socket
import threading
import json
import datetime
import os
import sys

#config

CONFIG_FILE  = "config.json"
HISTORY_FILE = "historial.json"

archivo_lock = threading.Lock()   #mutex para escritura en disco
print_lock   = threading.Lock()   #mutex para imprimir sin mezclar salida


def cargar_config() -> dict:
    """Carga config.json. Aborta con mensaje claro si no existe."""
    if not os.path.exists(CONFIG_FILE):
        print(f"[ERROR] No se encontro '{CONFIG_FILE}'.")
        print("        Crea el archivo con el formato indicado en el README.")
        sys.exit(1)
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)


config      = cargar_config()
my_hostname = config["hostname"]
my_ip       = config["nodos"][my_hostname]
port        = config["puerto"]



#PERSISTENCIA 
# se logra a través de un archivo JSON local (historial.json) que almacena todos los mensajes y ACKs enviados 
# y recibidos por el nodo, utilizando un mutex para evitar corrupcion de archivo si varios hilos escriben a la vez

def guardar_msg(entrada: dict) -> None:
    """Agrega una entrada (mensaje o ACK) al historial JSON local."""
    with archivo_lock: #usamos el mutex para evitar corrupcion de archivo si varios hilos escriben a la vez
        mensajes = []
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                try:
                    mensajes = json.load(f)
                except json.JSONDecodeError:
                    mensajes = []
        mensajes.append(entrada)
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(mensajes, f, indent=4, ensure_ascii=False)

#UTILIDADES DE PRESENTACION

def timestamp() -> str:
    """Devuelve el timestamp ISO 8601 local del nodo."""
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def formatear_ts(ts_raw: str) -> str:
    """Normaliza cualquier timestamp a 'DD-MM-YYYY HH:MM:SS'."""
    try:
        dt = datetime.datetime.strptime(ts_raw.split(".")[0], "%Y-%m-%d %H:%M:%S")
        return dt.strftime("%d-%m-%Y %H:%M:%S")
    except Exception:
        return ts_raw


def imprimir(linea: str) -> None:
    """Imprime de forma thread-safe."""
    with print_lock:
        print(linea)


def ver_historial() -> None:
    """Muestra el contenido completo de historial.json."""
    separador = "─" * 55
    imprimir(f"\n{separador}")
    imprimir(f"  HISTORIAL LOCAL — {my_hostname.upper()}")
    imprimir(separador)
    if not os.path.exists(HISTORY_FILE):
        imprimir("  (sin registros aún)")
    else:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            try:
                contenido = json.load(f)
                if not contenido:
                    imprimir("  (sin registros)")
                else:
                    for i, entrada in enumerate(contenido, 1):
                        tipo  = entrada.get("tipo", "?")
                        ts    = formatear_ts(entrada.get("timestamp", ""))
                        if tipo == "MENSAJE":
                            imprimir(
                                f"  [{i:03}] MSG | {ts} | "
                                f"EMISOR: {entrada.get('sender','?')} → "
                                f"DESTINO: {entrada.get('destino','todos')} | "
                                f"\"{entrada.get('text','')}\""
                            )
                        elif tipo == "ACK":
                            imprimir(
                                f"  [{i:03}] ACK | {ts} | "
                                f"EMISOR: {entrada.get('emisor','?')} → "
                                f"DESTINO: {entrada.get('para','?')} "
                                f"[{entrada.get('status','?')}]"
                            )
                        else:
                            imprimir(f"  [{i:03}] {json.dumps(entrada, ensure_ascii=False)}")
            except json.JSONDecodeError:
                imprimir("  [!] El archivo existe pero tiene formato invalido.")
    imprimir(separador)
    input("\n  Presiona Enter para volver al menu...")


#  SERVIDOR  (hilo principal de escucha)

def manejar_cliente(conn: socket.socket, addr: tuple) -> None:
    """
    Hilo dedicado por conexion entrante.
    1. Recibe el mensaje.
    2. Lo guarda en disco (receptor).
    3. Muestra alerta en pantalla.
    4. Envia ACK automático.
    5. Guarda el ACK en disco (receptor).
    """
    try:
        partes = []
        while True:
            chunk = conn.recv(4096)
            if not chunk:
                break
            partes.append(chunk)
            # Intentamos parsear; si esta completo salimos del loop
            try:
                json.loads(b"".join(partes).decode("utf-8"))
                break
            except json.JSONDecodeError:
                continue  # seguir leyendo

        raw = b"".join(partes).decode("utf-8")
        if not raw:
            return

        msg = json.loads(raw)

        #Guardar mensaje recibido
        guardar_msg(msg)

        #Mostrar en pantalla
        tipo_str = "PRIVADO" if msg.get("alcance") == "privado" else "BROADCAST"
        ts_fmt   = formatear_ts(msg.get("timestamp", ""))
        with print_lock:
            print(f"\n{'- -'*20}")
            print(f"  NUEVO MENSAJE — {tipo_str}")
            print(f"  EMISOR       : {msg.get('sender', '?')}")
            print(f"  HORA ENVIO : {ts_fmt}")
            print(f"  HORA RECEPCION : {timestamp()}")
            print(f"  DESTINO  : {msg.get('destino', 'todos')}")
            print(f"  MENSAJE (TEXTO)    : {msg.get('text', '')}")
            print(f"{'- -'*20}\n")

        #Construir y enviar ACK
        ack = {
            "tipo"     : "ACK",
            "emisor"   : my_hostname,
            "para"     : msg.get("sender", "?"),
            "msg_id"   : msg.get("msg_id", ""),
            "status"   : "recibido",
            "timestamp": timestamp()
        }
        conn.sendall(json.dumps(ack, ensure_ascii=False).encode("utf-8"))

        #Guardar ACK emitido por el receptor 
        guardar_msg(ack)

    except (json.JSONDecodeError, OSError) as e:
        imprimir(f"[SERVIDOR] Error procesando mensaje entrante: {e}")
    finally:
        conn.close()


def servidor() -> None:
    """
    Servidor TCP multi-hilo.
    por cada conexion entrante lanza un hilo independiente,
    garantizando recepcion paralela sin bloquear.
    """
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM) #creamos el socket TCP (SOCK_STREAM) y que responde a ipv4 (AF_INET)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) #para liberar el puerto 5000 si el nodo se cierra y se vuelve a abrir rapidamente
    try:
        srv.bind((my_ip, port)) #encola las conexiones entrantes en el puerto 5000 de la ip del nodo
    except OSError as e:
        imprimir(f"ERROR: No se pudo iniciar el servidor para '{my_hostname}' — {e}")
        sys.exit(1)
    srv.listen(10) #ejecuta el listen para aceptar hasta 10 conexiones entrantes en cola
    imprimir(f"El nodo '{my_hostname}' esta listo para recibir mensajes.")

    while True:
        try:
            conn, addr = srv.accept()
            hilo = threading.Thread(
                target=manejar_cliente,
                args=(conn, addr),
                daemon=True
            )
            hilo.start()
        except OSError:
            break


#CLIENTE  (CLI interactivo)

def enviar_mensaje(destino_nombre: str, destino_ip: str, payload: dict) -> None:
    """
    Hilo de envio a un nodo especifico.
    1. Guarda el mensaje en disco (emisor) ANTES de enviar.
    2. Conecta y envía via TCP.
    3. Espera y muestra el ACK.
    4. Guarda el ACK recibido en disco (emisor).
    """
    # Guardar mensaje saliente (independientemente del exito de red)
    guardar_msg(payload)

    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(5)
        s.connect((destino_ip, port))
        s.sendall(json.dumps(payload, ensure_ascii=False).encode("utf-8"))

        # Recibir ACK
        partes = []
        while True:
            chunk = s.recv(4096)
            if not chunk:
                break
            partes.append(chunk)
            try:
                json.loads(b"".join(partes).decode("utf-8"))
                break
            except json.JSONDecodeError:
                continue

        ack = json.loads(b"".join(partes).decode("utf-8"))
        guardar_msg(ack)

        ack_ts = formatear_ts(ack.get("timestamp", ""))
        imprimir(f"ACK de '{destino_nombre}' a las {ack_ts} — {ack.get('status','?')}")
        s.close()

    except (ConnectionRefusedError, socket.timeout, OSError) as e:
        imprimir(f"No se pudo contactar a '{destino_nombre}': {e}")


def cliente() -> None:
    """Bucle parala interfaz de linea de comandos"""
    vecinos = {n: ip for n, ip in config["nodos"].items() if n != my_hostname}

    while True:
        sep = "═" * 40
        with print_lock:
            print(f"\n{sep}")
            print(f"   Nodo actual: {my_hostname.upper()}")
            print(sep)
            print("  1. Enviar a todos (Broadcast)")
            opciones = {}
            idx = 2
            for nombre, ip in vecinos.items():
                print(f"  {idx}. Enviar a {nombre}")
                opciones[idx] = (nombre, ip)
                idx += 1
            opc_historial = idx
            print(f"  {opc_historial}. Ver historial del nodo actual (historial.json)")
            opc_salir = idx + 1
            print(f"  {opc_salir}. Salir")
            print(sep)

        try:
            sel = int(input(f"  Seleccion (1-{opc_salir}): ").strip())
        except (ValueError, EOFError):
            imprimir("  [!] Ingresa un numero valido.")
            continue

        if sel == opc_salir:
            imprimir("*****   Cerrando nodo.   *****")
            break

        if sel == opc_historial:
            ver_historial()
            continue

        if sel != 1 and sel not in opciones:
            imprimir("Seleccion invalida. Intenta de nuevo.")
            continue

        texto = input("  Escribe el mensaje: ").strip()
        if not texto:
            imprimir("  El mensaje no puede estar vacio.")
            continue

        # ID unico simple basado en timestamp
        msg_id = f"{my_hostname}-{datetime.datetime.now().strftime('%Y%m%d%H%M%S%f')}"

        if sel == 1:
            # Broadcast: lanza un hilo por cada vecino en paralelo
            alcance   = "broadcast"
            objetivos = list(vecinos.items())
        else:
            nombre_dest, ip_dest = opciones[sel]
            alcance   = "privado"
            objetivos = [(nombre_dest, ip_dest)]

        for nombre_dest, ip_dest in objetivos:
            payload = {
                "tipo"     : "MENSAJE",
                "msg_id"   : msg_id,
                "sender"   : my_hostname,
                "destino"  : nombre_dest if alcance == "privado" else "todos",
                "text"     : texto,
                "timestamp": timestamp(),   # Reloj del nodo emisor
                "alcance"  : alcance
            }
            hilo = threading.Thread(
                target=enviar_mensaje,
                args=(nombre_dest, ip_dest, payload),
                daemon=True
            )
            hilo.start()

        # Esperamos brevemente a que los hilos de envio impriman sus ACKs
        # antes de mostrar el menu de nuevo
        threading.Event().wait(timeout=6)


#PUNTO DE ENTRADA

if __name__ == "__main__":
    # Hilo servidor en background (daemon=True: muere con el proceso principal)
    hilo_srv = threading.Thread(target=servidor, daemon=True)
    hilo_srv.start()

    # CLI en el hilo principal
    cliente()
