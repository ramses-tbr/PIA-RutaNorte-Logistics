# RutaNorte Logistics - PIA
# Equipo: 2
| Matrícula | Nombre |
|-----------|--------|
| 2049234 | Basurto Rivera Ramsés Tenosh |
| 2050864 | Cerda Herrera Juan Kristof |
| 2066053 | Esparza Torres Carlos Arturo |

Sistema para una empresa, RutaNorte Logistics la cual transporta mercancía entre distintas ciudades y cobra según distintos parametros. Atiende a clientes recurrentes y también ocasionales.  

---

## Estado del proyecto y CI/CD

[![CI Pipeline](https://github.com/ramses-tbr/PIA-RutaNorte-Logistics/actions/workflows/ci.yml/badge.svg)](https://github.com/ramses-tbr/PIA-RutaNorte-Logistics/actions)
- **Despliegue en Producción:** [https://pia-rutanorte-logistics.onrender.com](https://pia-rutanorte-logistics.onrender.com)
- **Documentación Interactiva (Swagger UI):** [https://pia-rutanorte-logistics.onrender.com/docs](https://pia-rutanorte-logistics.onrender.com/docs)
---

## Tecnologías utilizadas

- **Lenguaje:** Python 3.10+
- **Framework Web:** FastAPI (Uvicorn)
- **Pruebas y Cobertura:** Pytest + Pytest-Cov
- **Contenedores:** Docker & Docker Compose
- **CI/CD:** GitHub Actions (`ci.yml`)
- **Hosting / Nube:** Render (Free Tier)

---

## Arquitectura del proyecto

El sistema está estructurado respetando la separación de responsabilidades y arquitectura:

```text
.
├── .github/
│   └── workflows/
│       └── ci.yml   
├── .vscode/      
├── api/                   
├── aplicacion/                   
├── datos/   
├── docs/    
│   └── BPMN
│   └── BRD
│   └── Glosario
│   └── Informe de arquitectura
│   └── User Stories            
├── dominio/                
│   └── entidades/
│   └── errores/
│   └── servicios/
│   └── valores/
├── infraestructura/        
├── tests/     
├── Dockerfile 
├── docker-compose.yml      
├── main.py       
├── pytest.ini     
├── requirements.txt       
└── README.md
```

---

## Ejecución local

### Opción 1: Con Docker

Asegúrate de tener instalado **Docker Desktop** y ejecuta en la raíz del proyecto:

```bash
docker compose up --build
```

El despliegue estará disponible inmediatamente en `http://localhost:8000` y la documentación interactiva en `http://localhost:8000/docs`.

---

### Opción 2: Entorno virtual de python local

1. **Crear y activar el entorno virtual:**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate  # En macOS/Linux
   # .venv\Scripts\activate   # En Windows
   ```

2. **Instalar dependencias:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Ejecutar el servidor en modo desarrollo:**
   ```bash
   uvicorn api.api:app --reload
   ```

---

## Pruebas y cobertura

Para ejecutar la suite de pruebas unitarias y verificar la cobertura del código localmente:

```bash
pytest --cov=dominio --cov=aplicacion --cov-report=term-missing --cov-fail-under=80
```

---