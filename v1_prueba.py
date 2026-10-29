import socket
import threading
import json
import datetime
import os

archivo_lock = threading.Lock()

def cargar_config():
    with open('config.json', 'r') as f:
        return json.load(f)

config = cargar_config()
my_hostname = config['hostname']
my_ip = config['nodos'][my_hostname]
port = config['puerto']

def guardar_en_json(data):
    historial_file = "historial.json"
    with archivo_lock:
        mensajes = []
        if os.path.exists(historial_file):
            with open(historial_file, 'r') as f:
                try:
                    mensajes = json.load(f)
                except:
                    mensajes = []
        mensajes.append(data)
        with open(historial_file, 'w') as f:
            json.dump(mensajes, f, indent=4)

def ver_historial():
    print(f"\n--- CONTENIDO DE HISTORIAL.JSON EN {my_hostname.upper()} ---")
    if os.path.exists("historial.json"):
        with open("historial.json", "r") as f:
            try:
                contenido = json.load(f)
                print(json.dumps(contenido, indent=4))
            except:
                print("[!] El archivo esta vacio o tiene errores.")
    else:
        print("[!] No existe el archivo historial.json todavia.")
    input("\nPresiona Enter para volver al menu...")

def servidor():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind((my_ip, port))
    s.listen(5)
    while True:
        conn, addr = s.accept()
        try:
            data = conn.recv(4096).decode()
            if not data: continue
            msg_recibido = json.loads(data)
            guardar_en_json(msg_recibido)
            tipo = "PERSONAL" if msg_recibido['alcance'] == "privado" else "GLOBAL"
            ts_crudo = msg_recibido.get('timestamp', str(datetime.datetime.now()))
            try:
                dt_obj = datetime.datetime.strptime(ts_crudo.split('.')[0], "%Y-%m-%d %H:%M:%S")
                fecha_formateada = dt_obj.strftime("%d-%m-%Y %H:%M:%S")
            except:
                fecha_formateada = ts_crudo
            print(f"\n" + "*"*50)
            print(f"[NUEVO MENSAJE {tipo}]")
            print(f"DE: {msg_recibido['sender']}")
            print(f"FECHA Y HORA: {fecha_formateada}")
            print(f"CONTENIDO: {msg_recibido['text']}")
            print("*"*50 + "\n")
            ack = {
                "tipo": "ACK",
                "emisor": my_hostname,
                "para": msg_recibido['sender'],
                "status": "recibido",
                "timestamp": str(datetime.datetime.now())
            }
            conn.send(json.dumps(ack).encode())
            guardar_en_json(ack)
            conn.close()
        except:
            pass

def cliente():
    while True:
        print(f"\n" + "="*30)
        print(f"   MENU {my_hostname.upper()}")
        print("="*30)
        opciones = {1: "all"}
        print("1. Enviar a TODOS (Broadcast)")
        vecinos = [n for n in config['nodos'] if n != my_hostname]
        idx = 2
        for nodo in vecinos:
            print(f"{idx}. Enviar solo a {nodo} (Privado)")
            opciones[idx] = nodo
            idx += 1
        opcion_ver = idx
        print(f"{opcion_ver}. VER HISTORIAL (JSON)")
        opcion_salir = idx + 1
        print(f"{opcion_salir}. Salir")
        try:
            sel = int(input(f"\nSeleccion (1-{opcion_salir}): "))
            if sel == opcion_salir: break
            if sel == opcion_ver:
                ver_historial()
                continue
            destino = opciones[sel]
        except:
            print("[!] Opcion invalida"); continue
        texto = input(f"Escribe el mensaje para {destino}: ")
        payload = {
            "tipo": "MENSAJE",
            "sender": my_hostname,
            "text": texto,
            "timestamp": str(datetime.datetime.now()),
            "alcance": "broadcast" if destino == "all" else "privado"
        }
        if destino == "all":
            objetivos = {n: ip for n, ip in config['nodos'].items() if n != my_hostname}
        else:
            objetivos = {destino: config['nodos'][destino]}
        for nombre, ip in objetivos.items():
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(3)
                s.connect((ip, port))
                s.send(json.dumps(payload).encode())
                respuesta = s.recv(4096).decode()
                ack = json.loads(respuesta)
                try:
                    ack_dt = datetime.datetime.strptime(ack['timestamp'].split('.')[0], "%Y-%m-%d %H:%M:%S")
                    ack_fecha = ack_dt.strftime("%d-%m-%Y %H:%M:%S")
                except:
                    ack_fecha = ack['timestamp']
                print(f"[*] {nombre} confirmo recepcion el {ack_fecha}")
                guardar_en_json(payload)
                guardar_en_json(ack)
                s.close()
            except:
                print(f"[!] No se pudo contactar a {nombre}")

if __name__ == "__main__":
    threading.Thread(target=servidor, daemon=True).start()
    cliente()