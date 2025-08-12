# Sistema de Reanudación Automática de Misiones

Este proyecto contiene un script de Python (`auto_resume.py`) diseñado para monitorizar un robot de Energy Robotics. Su principal función es detectar cuándo una misión entra en estado `PAUSED` y, si la causa es una de las predefinidas como "recuperables", ejecutar automáticamente una secuencia de comandos para intentar reanudar la misión.

La secuencia de recuperación es:
1.  Enviar comando `ASLEEP`.
2.  Esperar un tiempo configurable.
3.  Enviar comando `AWAKE`.
4.  Esperar un tiempo configurable.
5.  Enviar comando `resumeMissionExecution`.

---

## Instalación

Para configurar el entorno y ejecutar el script, sigue estos pasos:

1.  **Clonar el Repositorio**
    ```bash
    git clone git@github.com:tu_usuario/tu-repositorio.git
    cd tu-repositorio
    ```

2.  **Crear Archivo de Dependencias**
    Crea un archivo llamado `requirements.txt` con el siguiente contenido:
    ```
    gql[requests]
    PyYAML
    ```

3.  **Instalar Dependencias**
    Se recomienda crear un entorno virtual de Python primero.
    ```bash
    pip install -r requirements.txt
    ```

4.  **Crear Archivos de GraphQL**
    Asegúrate de que la carpeta `queries` existe y contiene los siguientes archivos con su contenido correspondiente:
    * `queries/get_mission_status.graphql`
    * `queries/get_awake_status.graphql`
    * `queries/awake_command.graphql`
    * `queries/resume_mission.graphql`

---

## Configuración

Toda la configuración del script se gestiona a través del archivo `resume_config.yaml`. **Este archivo no debe subirse a GitHub**, ya que contiene información sensible.

### `resume_config.yaml`

```yaml
# Credenciales de acceso a la API
credentials:
  user: 'tu_usuario@example.com'
  key: 'tu_api_key'

# Información del robot a monitorizar
robot_info:
  id: "ID_DEL_ROBOT"

# Endpoints de la API
api_endpoints:
  graphql_url: "[https://api.graphql.energy-robotics.com/graphql](https://api.graphql.energy-robotics.com/graphql)"
  login_url: "[https://login.energy-robotics.com/api/loginApi](https://login.energy-robotics.com/api/loginApi)"

# Ajustes de tiempo del script
settings:
  check_interval_seconds: 60
  action_delay_seconds: 10

# Disparadores de la secuencia de recuperación
recovery_triggers:
  max_event_age_seconds: 120
  event_messages:
    - "notification.behaviorNavigationFailed"
    - "notification.behaviorPrincipalDriverNotSupervising"
    - "notification.behaviorDockingMaximumRetriesExceeded"
```

### Descripción de Parámetros Clave

* **`robot_info.id`**: Aquí debes poner el `ID` del robot que quieres que el script monitorice.
* **`settings.check_interval_seconds`**: Frecuencia (en segundos) con la que el script comprobará el estado del robot. Un valor de `60` significa una vez por minuto.
* **`settings.action_delay_seconds`**: La pausa en segundos entre los comandos de la secuencia de recuperación (entre `ASLEEP` y `AWAKE`, y entre `AWAKE` y `RESUME`).
* **`recovery_triggers.max_event_age_seconds`**: Para que un evento sea considerado la causa de la pausa, debe haber ocurrido en los últimos X segundos. Esto evita que un evento antiguo active una recuperación ahora.
* **`recovery_triggers.event_messages`**: **Esta es la lista más importante.** Contiene los mensajes de evento que son considerados "seguros" para intentar una recuperación. Si una misión se pausa y su último evento no está en esta lista, el script no hará nada.

#### Cómo Añadir un Nuevo Evento de Disparo

Simplemente añade una nueva línea a la lista `event_messages` en el archivo `resume_config.yaml`. Por ejemplo, para que el script también actúe ante un `softwareCollisionElevationMap`:

```yaml
  event_messages:
    - "notification.behaviorNavigationFailed"
    - "notification.behaviorPrincipalDriverNotSupervising"
    - "notification.behaviorDockingMaximumRetriesExceeded"
    - "notification.softwareCollisionElevationMap" # Nueva línea añadida
```
La comparación es insensible a mayúsculas/minúsculas.

---

## Uso

Para ejecutar el script en primer plano (ideal para pruebas):
```bash
python auto_resume.py
```

Para una ejecución permanente y desatendida, se recomienda configurar el script como un **servicio de `systemd`** en un servidor Linux, utilizando **Docker** para contenerizar la aplicación, tal y como se describió en guías anteriores.
