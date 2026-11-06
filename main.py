from aplicacion.casos_uso import construir_casos_de_uso
from infraestructura.repositorios.ordenes_repositorio import RepositorioOrdenesCSV

def main():
    # Le pasas la ruta del archivo CSV requerido por __init__
    ruta_archivo = "datos/operaciones.csv" # Ajusta la ruta si tu archivo CSV está en otra carpeta (ej. "operaciones.csv")
    repositorio = RepositorioOrdenesCSV(ruta_archivo)
    
    casos = construir_casos_de_uso(repositorio)
    
    while True:
        print("\n========================================")
        print("        RUTANORTE LOGISTICS - PIA       ")
        print("========================================")
        print("1. Avanzar Fase de Orden")
        print("2. Reportar Incidente (Operador)")
        print("3. Registrar Devolución (Cliente)")
        print("4. Generar y Mostrar Reporte Operativo")
        print("5. Mostrar Ordenes Devolución")
        print("6. Salir")
        print("----------------------------------------")
        
        opcion = input("Selecciona una opción (1-6): ").strip()
        
        if opcion == "1":
            print("\n--- [ Opción 1: Avanzar Fase ] ---")
            id_orden = input("Ingresa el ID de la orden (ej. ENV-O001): ").strip()
            nueva_fase = input("Ingresa la nueva fase (ej. EN_TRANSITO, ENTREGADO): ").strip()
            try:
                resultado = casos.transicionar_fase.ejecutar(id_orden, nueva_fase)
                print(f"ÉXITO: Orden {resultado.orden_id} pasó de {resultado.fase_anterior} a {resultado.fase_nueva}")
            except Exception as e:
                print(f"ERROR al avanzar fase: {e}")
                
        elif opcion == "2":
            print("\n--- [ Opción 2: Reportar Incidente ] ---")
            id_orden = input("Ingresa el ID de la orden: ").strip()
            descripcion = input("Describe el incidente: ").strip()
            severidad = input("Severidad (BAJA, MEDIA, CRITICA): ").strip() or "MEDIA"
            try:
                resultado = casos.reportar_incidente.ejecutar(id_orden, descripcion, severidad)
                print(f"ÉXITO: Incidente registrado con ID {resultado.incidente_id}")
            except Exception as e:
                print(f"ERROR al reportar incidente: {e}")
                
        elif opcion == "3":
            print("\n--- [ Opción 3: Registrar Devolución ] ---")
            id_orden = input("Ingresa el ID de la orden a devolver: ").strip()
            motivo = input("Motivo de la devolución: ").strip()
            try:
                resultado = casos.registrar_devolucion.ejecutar(id_orden, motivo)
                print(f"ÉXITO: Devolución registrada con ID {resultado.devolucion_id}")
            except Exception as e:
                print(f"ERROR al registrar devolución: {e}")
                
        elif opcion == "4":
            print("\n--- [ Opción 4: Reporte Operativo y Financiero ] ---")
            try:
                # Generamos el reporte usando tu caso de uso
                reporte = casos.generar_reporte.generar()
                print(f"Fecha del reporte: {reporte.generado_en}")
                print("\n--- Rendimiento por Operador ---")
                for op in reporte.rendimiento_por_operador:
                    print(f"  • Operador ID: {op.operador_id} | Total órdenes: {op.total_ordenes} | Entregadas: {op.entregadas} | Tasa de entrega: {op.tasa_entrega_pct}%")
                
                print("\n--- Estado de Cuenta por Cliente ---")
                for cliente in reporte.estado_cuenta_por_cliente:
                    print(f"  • Cliente: {cliente.cliente_id} | Total: ${cliente.total_ordenes} | Entregado: ${cliente.valor_entregado}")

                print("\n--- Incidencias Críticas por Ruta ---")
                for inc in reporte.incidencias_por_ruta:
                    print(f"  • Ruta/Destino: {inc.ruta} | Incidentes totales: {inc.incidentes_totales} | Críticos: {inc.incidentes_criticos}")
                print("\nReporte generado y mostrado con ÉXITO.")
            except Exception as e:
                print(f"ERROR al generar el reporte: {e}")

        elif opcion == "5":
            print("\n--- [ Opción 5: Devoluciones Registradas en la Sesión ] ---")
            try:
                todas_las_ordenes = repositorio.listar_todas()
                
                devoluciones = [
                    o for o in todas_las_ordenes 
                    if "DEVOLUCION" in str(o.fase).upper()
                ]
                
                if not devoluciones:
                    print("No hay órdenes con devolución registradas en esta ejecución.")
                else:
                    print(f"Se encontraron {len(devoluciones)} orden(es) devuelta(s):")
                    for ord in devoluciones:
                        print(f"  • ID Orden: {ord.orden_id} | Fase Actual: {ord.fase} | Cliente: {ord.cliente_id} | Dirección: {ord.direccion}")
                
                print("\nConsulta de devoluciones en vivo realizada con éxito.")
            except Exception as e:
                print(f"ERROR al consultar las devoluciones: {e}")
                
        elif opcion == "6":
            print("\n¡Gracias por usar RutaNorte Logistics! Saliendo...")
            break
        else:
            print("Opción no válida. Por favor, elige un número entre 1 y 5.")

if __name__ == "__main__":
    main()