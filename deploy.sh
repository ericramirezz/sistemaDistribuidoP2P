#!/usr/bin/env bash
# ============================================================
#  deploy.sh — Copia node.py + config.json a las 4 VMs
#  y ajusta el hostname en cada una automáticamente.
#
#  USO:  bash deploy.sh <usuario_ssh>
#  EJ:   bash deploy.sh eric
# ============================================================

set -e   # Abortar si algo falla

USUARIO="${1:-eric}" #aquí poner el nombre de usuario que se usa para ssh en las VMs
PUERTO_SSH=22 #el puerto 22 es el predeterminado para ssh 
PROYECTO_DIR="~/mensajeria"
ARCHIVOS="node.py config.json"

# Mapa: nombre_nodo → IP
declare -A NODOS=(
    ["nodo1"]="192.168.122.248" #modificar dependiendo de la IP de cada nodo
    ["nodo2"]="192.168.122.11"
    ["nodo3"]="192.168.122.205"
    ["nodo4"]="192.168.122.39"
)

echo "=============================================="
echo "  SISTEMA DE MENSAJERIA P2P"
echo "  Usuario: $USUARIO"
echo "=============================================="

for NOMBRE in nodo1 nodo2 nodo3 nodo4; do
    IP="${NODOS[$NOMBRE]}"
    echo ""
    echo ">>> Desplegando en $NOMBRE ($IP)..."

    # 1. Crear directorio remoto
    ssh -p $PUERTO_SSH "${USUARIO}@${IP}" "mkdir -p $PROYECTO_DIR"

    # 2. Copiar archivos
    scp -P $PUERTO_SSH $ARCHIVOS "${USUARIO}@${IP}:${PROYECTO_DIR}/"

    # 3. Ajustar el hostname en config.json de esa VM
    ssh -p $PUERTO_SSH "${USUARIO}@${IP}" \
        "cd $PROYECTO_DIR && python3 -c \"
import json
with open('config.json','r') as f:
    c = json.load(f)
c['hostname'] = '${NOMBRE}'
with open('config.json','w') as f:
    json.dump(c, f, indent=4)
print('config.json actualizado: hostname =', c['hostname'])
\"
"
    echo "    [OK] $NOMBRE listo"
done

echo ""
echo "=============================================="
echo "  Despliegue completado. "
echo "Ruta para iniciar programa: python3 ~/mensajeria/node.py"
echo "=============================================="
