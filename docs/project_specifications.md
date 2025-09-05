# Especificación General de Proyecto

## 0. Introducción General

### 0.1. Concepto del Proyecto

Sistema ligero de gestión de partes, inventario y operaciones para entornos de ingeniería/producción electrónica. Objetivos clave:

- Identificación única de partes (IPN) y variantes.
- Inventario multi-ubicación con reservas.
- Movimientos trazables y órdenes de negocio.
- Documentación asociada.
- Catálogo de proveedores y precios.
- Auditoría transversal.

### 0.2. Plataforma Tecnológica

- BD: SQLite 3 (embebida, transaccional, portable).
- Backend: FastAPI (REST, OpenAPI/Swagger).
- ORM: SQLAlchemy 2.x (declarativo, tipado moderno).
- Migraciones: Alembic (versionado de esquema).
- Ejecución: despliegue ligero (instancia única). Migración futura a PostgreSQL viable gracias a SQLAlchemy.

### 0.3. Arquitectura de Alto Nivel

1. Datos (SQLite + Alembic):
   Esquema normalizado; catálogos (`uom`, `part_type`, `document_role`, `distributor`), negocio (`part`, `inventory_item`, `movement`, `order_header`, `reservation`), transversales (`audit_log`, `code_seq`, `ipn_seq`), vistas (`part_inventory`).

2. Persistencia (ORM):
   SQLAlchemy 2.x, modelo declarativo, sesiones transaccionales.

   Invariantes (`on_hand ≥ 0`, IPN único, UoM discreta=enteros), procesos (variante IPN, movimientos atómicos, `CNT→ADJ`), auditoría y numeración en la misma transacción.

4. API (FastAPI):
   Endpoints REST homogéneos (`/parts`, `/inventory`, `/movements`, `/orders`, `/reservations`, `/documents`, `/pricing`), validación con Pydantic, manejo de errores.

5. Cliente (UI):

- Una UI simple y directa que permita operar la aplicación (altas/consultas/ediciones básicas, adjuntos, alertas mínimas).
- A libre implementación del desarrollador (stack/estilo a elegir).
- Requisitos no funcionales: tiempos de respuesta razonables, navegación clara, validaciones en cliente que complementen las de servidor.
- Ejemplos orientativos (no prescriptivos): formulario unificado de parte/variante, vista de inventario con totales y reservas, flujo de traslado con confirmación, adjuntar documentos a parte/movimiento/orden.

### 0.4. Filosofía de Diseño

- Consistencia transversal (auditoría, numeración, trazabilidad).
- Simplicidad primero, extensibilidad después (TODOs explícitos).
- Portabilidad (SQLite hoy, PostgreSQL posible).
- Trazabilidad total (reversas, soft-delete, auditoría en todas las mutaciones).

### 0.5. Alcance del proyecto.

Incluye:

- Partes/IPN.
- Inventario.
- Movimientos (`RCV`/`OUT`/`TRO`/`TRI`/`ADJ`).
- Órdenes (`PO`/`SO`/`WO`/`TO`/`CNT`/`QI`/`RMA`/`RTS`).
- Reservas manuales.
- Documentos.
- Auditoría.
- Proveedores/precios.
- UI simple operativa.

Pendiente futuro:
- Jerarquía de locations.
- Costing.
- Lotes/series/caducidad.
- Políticas de lifecycle.
- Duplicación/antivirus en documentos.
- Integración con APIs de distribuidores.
- Generación de PDF de reportes, movimientos, órdenes, etc.

## 1. Gestión de Partes

### 1.1. Objetivo

Modelar y gestionar partes simples y compuestas, su identificación (IPN y variantes), sus atributos básicos, su BOM de un nivel (encadenable a multinivel), sus UoM y su trazabilidad (auditoría). Basado en SQLite, servicios con reglas de negocio y auditoría genérica.

### 1.2. Identificación (IPN) y variantes

- Formato IPN: `NNNNNN-VV` (`^\d{6}-\d{2}$`).
- Semántica:

  - Número de parte (`NNNNNN`): 6 dígitos, autogenerado y secuencial, inmutable.
  - Variante (`VV`): 2 dígitos, configurable por el usuario al crear la parte; puede cambiarse posteriormente si no colisiona.
  - Sólo se guarda el `ipn` completo. Las consultas puntuales de base o variante se derivan por expresión (`substr(ipn,1,6)` y `substr(ipn,8,2)` en SQLite).

- Creación de nueva parte:

  - El sistema asigna el siguiente número base disponible (`NNNNNN`) y, si el usuario no indica variante, usar `00`.

- Creación de variante de una parte existente:

  - Se selecciona el número base existente y el usuario indica el nuevo `VV` (debe ser único para ese `NNNNNN`).

- Restricciones:

  - `ipn` **UNIQUE**.
  - El número base no cambia nunca; sólo `VV` puede cambiar si no entra en conflicto.
  - Validación del patrón en altas y cambios de `VV`.

### 1.3. Atributos y campos

#### 1.3.1. Campos obligatorios

- `ipn` (derivado de reglas de [1.2. Identificación (IPN) y variantes](#12-identificacion-ipn-y-variantes)).
- `uom` (por defecto `pcs`).
- `part_type_id`.
- `lifecycle` (por defecto `active`).
- `manufacturer` (texto).
- `manufacturer_pn` (texto).

#### 1.3.2. Campos opcionales

- `description` (texto corto/mediano).
- `notes` (texto corto).
- `minimum_qty` (`NUMERIC(18,6)`, `>= 0`, por defecto `0`).
- `receiving_location_id` (FK nullable, referencia a `locations.id`).

#### 1.3.3. Consideraciones de datos

- Tiempos en UTC.
- Numéricos en `NUMERIC(18,6)`; en UoM discretas (p. ej. `pcs`), se aplican reglas de enteros en la capa de servicio.
- `Lifecycle` informativo por ahora (ver TODO en [1.8. Ciclo de vida (`Lifecycle`)](18-ciclo-de-vida-lifecycle))

### 1.4. Tipos de parte (`PartType`)

- Catálogo gestionable por el usuario (CRUD completo), independiente de las partes existentes.
- Jerarquía en 3 niveles (categoría → subcategoría → tipo de parte).
- Solo los tipos hoja (nivel 3) son asignables a `Part`; los niveles 1–2 son para clasificación/filtrado.
- Modelo: `part_type(id, code, name, parent_id NULL, level TINYINT, active BOOLEAN)`.

  - `UNIQUE(parent_id, code)` recomendado; `code` corto (p. ej. `OPA`, `MCU`), `name` legible (p. ej. “Operational Amplifier”).
  - Integridad: evitar ciclos (servicio).

- Reglas:

  - Asignar a `Part` solo tipos con `level = 3`.
  - Eliminar: permitido si no tiene hijos; si está referenciado por partes, recomendado usar `active = 0` (desactivar) para mantener integridad.

- Importación inicial: la taxonomía puede cargarse desde el catálogo adjunto (fichero `part_types.yaml`) como semillas (opcional).

### 1.5. Unidades de medida (UoM)

- Catálogo gestionable por usuario (CRUD), con valores presembrados (`pcs`, `m`, `l`, `m2`, `g`, `kg`, ...).
- Regla de negocio: si la UoM es discreta (p. ej. `pcs`), todas las cantidades relacionadas con esa parte (BOM, movimientos, pedidos, etc.) deben ser enteras (validación en capa de servicios).
- Se debe marcar en el catálogo qué UoM son discretas o continuas para validar automáticamente.

### 1.6. Partes compuestas (BOM)

- BOM de un nivel en el dato, que habilita multinivel por composición (parte compuesta puede contener partes compuestas).
- Entidad `PartComponent(parent_part_id, child_part_id, quantity > 0, notes)`:
  - `UNIQUE(parent, child)`.
  - `parent != child`.
  - `quantity` positiva, respeta discretización si aplica.
- Validación de ciclos: cada inserción/modificación de `PartComponent` debe comprobar que no introduce ciclos (en capa de servicio).
- Borrado protegido: no se permite eliminar una parte si es child en cualquier BOM.

### 1.7. Mínimos y alertas

- `minimum_qty` es indicador visual: si `total_on_hand` < `minimum_qty`, el UI muestra una alerta (no bloquea operaciones).
- Es global por parte (no por localización).

TODO: valorar mínimos por `Location` y alertas específicas en una revisión posterior.

### 1.8. Ciclo de vida (`Lifecycle`)

- Estados: `active`, `nrnd`, `eol`, `obsolete`, `n/a`.
- Esta revisión: informativo; el usuario puede cambiarlo libremente.

TODO: en la próxima revisión, condicionar operaciones (p. ej. impedir uso en órdenes si `obsolete`) y definir políticas de transición.

### 1.9. Soft-delete y auditoría

- Borrado lógico de partes: se implementará un sistema de soft-delete que marcará las partes como inactivas en lugar de eliminarlas físicamente. Esto permitirá mantener un historial de auditoría y facilitar la recuperación de datos en caso de eliminación accidental. Las partes inactivas se ocultan en UI (salvo menús de recuperación) y se bloquean en usos futuros.
- Auditoría genérica: todas las operaciones de creación, modificación y eliminación (soft-delete) de partes se registrarán en una tabla de auditoría genérica y unificada para todas las entidades, en la que se incluirán detalles como el usuario que realizó la acción, la fecha y hora, el ID de solicitud (opcional, si procede) y los cambios específicos realizados (en casos de modificación):
  - CREATE/DELETE: registrar entrada en `AuditLog` (no requiere `diff_json`).
  - UPDATE: registrar entrada en `AuditLog` con cambios detallados en `diff_json` (`{<campo>: [<antes>, <después>]}`).

### 1.10. Reglas de negocio (servicios)

1. Alta de parte (nuevo número base)

- Transacción `BEGIN IMMEDIATE` para reservar siguiente `NNNNNN` (búsqueda del último `NNNNNN`).
- Validar variant (por defecto`00` si vacío) y `ipn` resultante (`UNIQUE`, patrón).
- Validar `part_type_id` es hoja.
- Auditar `CREATE`.

2. Alta de parte (variante de base existente)

- Derivar `NNNNNN` de `base_ipn` o selector de base.
- Validar que `VV` no exista para ese `NNNNNN` y formar `ipn`.
- Crear nueva parte independiente; auditar `CREATE`.

3. Cambio de variant (`UPDATE` del `ipn`)

- Verificar unicidad del nuevo `ipn` para el mismo `NNNNNN`.
- Actualizar `ipn`; auditar con `diff_json` (de → a).

4. Tipos de parte

- CRUD jerárquico con validación de no-ciclos.
- Asignación a `Part` solo si `level=3`.
- Eliminar: permitido si no tiene hijos; si está en uso por partes, preferible `active=0`.

5. Cambio de UoM:

- Permitir sólo si no impacta reglas anteriores (p. ej. si hay movimientos históricos, valorar política; recomendación: permitir con auditoría y advertencias).

6. BOM:

- En upsert de `PartComponent`: validar `quantity > 0`, discreción si aplica, unicidad, `parent != child` y no-ciclo.

7. Eliminación:

- `Part`: soft-delete; bloqueada si es child en BOM.
- `PartComponent`: permitir eliminar fila de BOM; pero no permitir eliminar la parte hija si está referenciada.

8. Lifecycle:

- Sin restricciones de cambio, no tiene impacto (ver TODO en [1.8. Ciclo de vida (`Lifecycle`)](#18-ciclo-de-vida-lifecycle)).

9. Minimum:

- Sólo alertas en UI (no bloquea) (ver TODO en [1.7. Mínimos y alertas](#17-minimos-y-alertas)).

### 1.11. API (borrador mínimo)

- `POST /parts/` — crear parte o variante (mismo formulario). Se admite:

  - `mode`: `"new_base"` | `"variant_of"`.
  - `base_ipn` (obligatorio si `mode="variant_of"`, se usa su `NNNNNN`).
  - `variant` (opcional si `new_base`, obligatorio si `variant_of`).
  - Resto de campos: `uom`, `part_type_id` (hoja), `lifecycle`, `manufacturer`, `manufacturer_pn`, `description`, `notes`, `minimum_qty`, `receiving_location_id`.

- `PATCH /parts/{ipn}` — actualizar (incluye cambio de variant ⇒ recalcula `ipn`; valida unicidad).
- `DELETE /parts/{ipn}` — soft-delete.
- `GET /parts/` — listar (filtros por `part_type`, `lifecycle`, `description`, `is_compound`, etc.).
- `GET /parts/{ipn}` — detalle.
- `GET /parts/{ipn}/bom` — listar BOM (un nivel).
- `PUT /parts/{ipn}/bom` — reemplazar BOM (transaccional, con validación de ciclos).
- `POST /parts/{ipn}/bom/items` — añadir ítem.
- `DELETE /parts/{ipn}/bom/items/{child_ipn}` — eliminar ítem.
- `CRUD /part-types` — catálogo de tipos.
- `CRUD /uom` — catálogo de unidades.

### 1.12. Esquema (DDL aproximado, SQLite)

- `PartType`:

```sql
CREATE TABLE part_type (
  id         INTEGER PRIMARY KEY,
  code       TEXT    NOT NULL,
  name       TEXT    NOT NULL,
  parent_id  INTEGER NULL,
  level      INTEGER NOT NULL,                -- 1=categoría, 2=subcategoría, 3=tipo (hoja)
  active     INTEGER NOT NULL DEFAULT 1,
  UNIQUE (parent_id, code),
  FOREIGN KEY (parent_id) REFERENCES part_type(id)
);

CREATE INDEX idx_part_type_parent ON part_type(parent_id);
CREATE INDEX idx_part_type_level  ON part_type(level);
```

- UoM:

```sql
CREATE TABLE uom (
  id       INTEGER PRIMARY KEY,
  code     TEXT    NOT NULL UNIQUE, -- p.ej., 'pcs','m','kg'
  discrete INTEGER NOT NULL         -- 1=discreta, 0=continua
);
```

- `Part`:

```sql
CREATE TABLE part (
  id                     INTEGER PRIMARY KEY,
  ipn                    TEXT NOT NULL UNIQUE,     -- 'NNNNNN-VV'
  uom_id                 INTEGER NOT NULL,
  part_type_id           INTEGER NOT NULL,
  lifecycle              TEXT NOT NULL DEFAULT 'active',
  manufacturer           TEXT NOT NULL,
  manufacturer_pn        TEXT NOT NULL,
  description            TEXT NULL,
  notes                  TEXT NULL,
  minimum_qty            NUMERIC(18,6) NOT NULL DEFAULT 0,
  receiving_location_id  INTEGER NULL,             -- FK a location
  is_deleted             INTEGER NOT NULL DEFAULT 0,
  created_at             TEXT NOT NULL,            -- UTC
  updated_at             TEXT NOT NULL,            -- UTC
  FOREIGN KEY (uom_id)                REFERENCES uom(id),
  FOREIGN KEY (part_type_id)          REFERENCES part_type(id),
  FOREIGN KEY (receiving_location_id) REFERENCES location(id),
  CHECK (ipn GLOB '[0-9][0-9][0-9][0-9][0-9][0-9]-[0-9][0-9]')
);
```

- `PartComponent`:

```sql
CREATE TABLE part_component (
  id               INTEGER PRIMARY KEY,
  parent_part_id   INTEGER NOT NULL,
  child_part_id    INTEGER NOT NULL,
  quantity         NUMERIC(18,6) NOT NULL CHECK (quantity > 0),
  notes            TEXT NULL,
  UNIQUE(parent_part_id, child_part_id),
  CHECK (parent_part_id <> child_part_id),
  FOREIGN KEY (parent_part_id) REFERENCES part(id),
  FOREIGN KEY (child_part_id)  REFERENCES part(id)
);

CREATE INDEX idx_pc_parent ON part_component(parent_part_id);
CREATE INDEX idx_pc_child  ON part_component(child_part_id);
```

### 1.13. Casos de uso y validaciones clave

1. Alta de parte simple:

- Input mínimo: `uom_id`, `part_type_id`, `manufacturer`, `manufacturer_pn`, `lifecycle?`.
- Sistema obtiene nuevo `base_number` (6 primeras cifras del IPN), setea la variante dada por usuario (por defecto, `00`).
- Audita `CREATE`.

2. Alta de variante:

- Input: `base_number` (primeras 6 cifras del IPN), `variant` (últimas 2 cifras del IPN) + input mínimo para parte simple.
- Verifica la unicidad (`ipn` resultante).
- Setea los campos de la parte (`uom_id`, `part_type_id`, `manufacturer`, ...).
- Audita `CREATE`.

3. Cambio de variante:

- Input: nuevo `variant` (2 últimas cifras del IPN).
- Verifica que el nuevo `ipn` es único.
- Actualiza `ipn`.
- Audita `UPDATE` con `diff_json`.

4. Definir BOM (nivel único):

- Input: lista de `{child_ipn, quantity}`.
- Validar UoM discreta → cantidades enteras.
- Validar no-ciclo (en servicio), unicidad y `> 0`.
- Upsert atómico; auditar `UPDATE` con `diff_json`.

5. Soft-delete de parte:

- Bloquear si la parte es child en cualquier BOM.
- Marcar `is_deleted = 1`.
- Auditar `DELETE` (sin `diff_json`).

6. Alertas de mínimo:

- Notificar a usuario si `part_inventory.total_on_hand < minimum_qty` es alcanzado (no bloquea).

## 2. Inventario

### 2.1. Modelo de localizaciones

- Estructura plana, no hay jerarquía.
  TODO: evaluar necesidad de jerarquía en el futuro.
- Entidad `location`: `code` (PK), `name`, `notes`.
  TODO: añadir atributo `kind` (p. ej., `stock`, `quarantine`, `scrap`).
- Ubicaciones por defecto de recepción (por parte): `Part.receiving_location_id` (FK a `location`, nullable); se usa cuando la recepción no especifica destino.

### 2.2. Semántica de inventario

- Entidad `InventoryItem(part_id, location_id, on_hand, reserved)`; `UNIQUE(part,location)`.
- Reglas:

  - `on_hand ≥ 0` siempre (bloqueo en `OUT`/`TRO` si no hay cantidad suficiente).
  - `reserved ≥ 0`. Se permite over-reservation (`shortage = reserved > on_hand`), solo señalización UI.
  - UoM discreta ⇒ cantidades enteras validadas en servicios.

### 2.3. Movimientos y efecto sobre stock

- Tipos: `RCV`, `OUT`, `TRO`, `TRI`, `ADJ`. `TRO`+`TRI` atómicos con `transfer_group_id` y `counterpart_id`.
- Políticas:

  - `OUT`/`TRO`: bloquean si `on_hand < qty`.
  - `ADJ`: no puede dejar `on_hand < 0`; requiere nota; no se permiten ajustes nulos.
  - `Reversa`: nunca se borra; se crea movimiento contrario con `reversal_of_id`.

- Numeración: `TT-YY-NNNN` usando tabla unificada `code_seq(prefix, year, next_seq)` para órdenes y movimientos (transacción `BEGIN IMMEDIATE`).
- Para más detalle, consulte el capítulo [3. Movimientos](#3-movimientos).

### 2.4. Vistas y consultas

- Vista agregada `part_inventory` (totales por parte): agrupa `on_hand` y `reserved`; campo derivado `pending_inbound` desde compras.
  TODO: valorar una vista adicional por `(part, location)` cuando sea necesario.
- `pending_inbound`: vista que agrega pendiente de recepción (pedido − cumplido) por parte y ubicación; unible con `part_inventory`.

### 2.5. Reservas (integración con inventario)

- Modelo: `reservation(order_line_id, part_id, location_id, qty, status)`; `InventoryItem.reserved = Σ OPEN` por `(parte, ubicación)`.
- Consumo de reservas:

  - `OUT`/`TRO` asociados a una reserva concreta ⇒ consumen esa reserva primero.
  - Si el movimiento no está asociado a ninguna reserva, no consume reservas existentes.
  - Se permite shortage (`reserved > on_hand`), pero no `on_hand` negativo.

### 2.6. Recepciones y sobre-recepción (PO)

- Política: no sobre-cumplir líneas. Si se recibe más que lo pendiente, se registra todo el `RCV` para exactitud de stock, se asigna a cumplimiento solo hasta el pendiente, y el exceso queda libre (contabilizado) pero vinculado al PO mediante `movement.order_id`.

### 2.7. Conteos de inventario (CNT)

- Regla: la línea almacena `count_target`; el servicio calcula `delta = count_target − on_hand` y emite un único `ADJ(delta)` (o ninguno si ya coincide).
- Ámbito: aplicado a `(parte, location)` exactos.

### 2.8. Calidad / cuarentena / devoluciones

- Se resuelve con convenciones en `Location.code` (p. ej., `QUARANTINE_*`, `SCRAP_*`).
  TODO: formalizar `Location.kind` y flujos `QI`/`RMA`/`RTS` en revisión posterior.

### 2.9. Lotes, series, caducidad

- No incluidos en esta revisión.
  TODO: evaluar `lot_id`/`serial`/`expiry_date` y su impacto en entidades y movimientos (trazabilidad por lote).

### 2.10. Valoración de stock (costing)

- Solo cantidades; la valoración se obtiene a partir de órdenes/precios para reporting si se necesita.
  TODO: definir política (FIFO/LIFO/AVG, multi-moneda) y su integración futura.

### 2.11. Esquemas (DDL aproximado, SQLite)

```sql
CREATE TABLE location (
  id           INTEGER PRIMARY KEY,
  code         TEXT NOT NULL UNIQUE,
  name         TEXT NOT NULL,
  notes        TEXT NULL,
  created_at   TEXT NOT NULL,
  updated_at   TEXT NOT NULL
);


CREATE TABLE inventory_item (
  id           INTEGER PRIMARY KEY,
  part_id      INTEGER NOT NULL,
  location_id  INTEGER NOT NULL,
  on_hand      NUMERIC(18,6) NOT NULL CHECK(on_hand >= 0),
  reserved     NUMERIC(18,6) NOT NULL CHECK(reserved >= 0),
  updated_at   TEXT NOT NULL,
  FOREIGN KEY (part_id) REFERENCES part(id),
  FOREIGN KEY (location_id) REFERENCES location(id),
  UNIQUE(part_id, location_id)
);


CREATE VIEW part_inventory AS
WITH po_open AS (
  SELECT
    ol.part_id,
    SUM(ol.qty)                          AS ordered_qty,
    COALESCE(SUM(of_fulfilled.qty), 0.0) AS fulfilled_qty
  FROM order_line ol
  JOIN order_header oh
    ON oh.id = ol.order_id AND oh.type = 'PO'
   AND oh.status IN ('APPROVED','IN_PROGRESS','PARTIAL')
  LEFT JOIN order_fulfillment of_fulfilled
    ON of_fulfilled.order_line_id = ol.id
  GROUP BY ol.part_id
)
SELECT
  p.id                                     AS part_id,
  COALESCE(SUM(i.on_hand),   0.0)          AS total_on_hand,
  COALESCE(SUM(i.reserved),  0.0)          AS total_reserved,
  COALESCE(po_open.ordered_qty - po_open.fulfilled_qty, 0.0)
                                           AS pending_inbound
FROM part p
LEFT JOIN inventory_item i ON i.part_id = p.id
LEFT JOIN po_open          ON po_open.part_id = p.id
GROUP BY p.id;
```

Para `reservation`, consulte [5.8. DDL preliminar (SQLite)](#58-ddl-preliminar-sqlite).

### 2.12. API (borrador mínimo)

- `GET /inventory/parts/{ipn}` → totales (y, opcionalmente, detalle por ubicación).
- `GET /inventory/locations/{location_id}` → stock por parte en esa ubicación.
- `GET /inventory/alerts` → partes por debajo de `minimum_qty` (solo UI; no bloquea).
- `GET /inventory/pending-inbound` → vista de pendientes de recepción.

### 2.13. Auditoría y concurrencia

- Auditoría: todas las operaciones que afecten a `InventoryItem`/`Movement` se registran en `AuditLog`; `diff_json` obligatorio en `UPDATE`.
- Concurrencia (SQLite): usar transacciones `BEGIN IMMEDIATE` en secciones críticas (asignación de códigos, actualizaciones de stock) para evitar colisiones y asegurar atomicidad (especialmente en transferencias).

## 3. Movimientos

### 3.1. Objetivo y alcance

El ledger de movimientos es la única fuente de verdad para los cambios de stock. Cubre entradas, salidas, traslados y ajustes, asegura la trazabilidad completa, y proporciona códigos humanos unificados para registro y auditoría. Los tipos soportados son: `RCV`, `OUT`, `TRO`, `TRI`, `ADJ`. Las transferencias (`TRO`+`TRI`) son atómicas y con vínculos cruzados; las anulaciones se implementan mediante reversas (no se borra).

### 3.2. Tipología y semántica

#### 3.2.1. `RCV` (Receipt)

Incrementa `on_hand` en la ubicación objetivo. Puede vincularse a una orden (p. ej., `PO`). En caso de sobre-recepción contra un `PO`, se registra toda la entrada, pero sólo se asigna hasta lo pendiente; el excedente queda libre y vinculado al `PO` vía `movement.order_id`.

#### 3.2.2. `OUT` (Issue)

Decrementa `on_hand` en la ubicación origen. Bloquea si `on_hand` < `qty`. Si está asociada a una reserva concreta, consume esa reserva; si no lo está, no consume reservas existentes. Shortage permitido solo a nivel de `reserved` (nunca `on_hand` negativo).

#### 3.2.3. `TRO/TRI` (Transfer Out/In)

Par de movimientos que materializan un traslado en una sola transacción. Se registran con el mismo `transfer_group_id` y referencias cruzadas `counterpart_id`. El sistema garantiza todo o nada.

#### 3.2.4. `ADJ` (Adjustment)

Ajuste manual (positivo o negativo), no nulo, y nunca puede llevar `on_hand` < 0. Requiere nota y opcionalmente `validated_by`/`at` (en futuras versiones será mandatorio).

### 3.3. Invariantes de stock (pre/post-condiciones)

- `on_hand ≥ 0` siempre (bloqueo en `OUT`/`TRO` si no alcanza).
- `reserved ≥ 0`. Over-reservation permitido: `reserved` puede exceder `on_hand` (sólo alerta en UI).
- UoM discreta ⇒ cantidades enteras a nivel de servicio (incluye `ADJ`).

### 3.4. Numeración humana (códigos `TT-YY-NNNN`)

Todos los movimientos comparten la tabla unificada `code_seq(prefix, year, next_seq)` con las órdenes. La asignación se realiza dentro de una única transacción SQLite (`BEGIN IMMEDIATE`) para evitar colisiones. Prefijos: `RCV`, `OUT`, `TRI`, `TRO`, `ADJ` (más los de órdenes).

### 3.5. Concurrencia y atomicidad

SQLite es la única base de datos. Las operaciones críticas (reserva de códigos, actualizaciones de stock, transferencias) se encapsulan en transacciones `BEGIN IMMEDIATE`. En transferencias, ambos movimientos (`TRO` y `TRI`) se confirman o ninguno.

### 3.6. Interacción con reservas

Las reservas se gestionan a nivel de línea de orden. `InventoryItem.reserved = Σ OPEN` por (parte, ubicación). Un `OUT`/`TRO` sólo consume reservas si está asociado explícitamente a esa reserva; de lo contrario, no reduce `reserved`. Se permite shortage (`reserved > on_hand`), pero nunca `on_hand` negativo.

### 3.7. Recepciones y sobre-recepción (`PO`)

Política de no sobre-cumplimiento de líneas: ante sobre-recepción, se registra íntegramente el `RCV` por precisión de stock, se asigna a `OrderFulfillment` sólo hasta lo pendiente, y el excedente queda no asignado (visible en UI) pero vinculado al PO mediante `movement.order_id`.

### 3.8. Conteos de inventario (`CNT`)

Las órdenes de conteo guardan `count_target` por (parte, ubicación), que es el número de ítems contabilizados en el inventario. El servicio se encarga de calcular `delta = count_target − on_hand` y emite un único `ADJ(delta)` (o ninguno si ya coincide).

### 3.9. Documentos y evidencias

Un modelo polimórfico (`Document` + `DocumentLink(entity_type, entity_id)`) permite adjuntar albaranes, fotos o informes a cada movimiento. Al quedar un `FILE` huérfano (sin enlaces), el servicio elimina el fichero local.

### 3.10. Auditoría

`AuditLog` único (polimórfico). `diff_json` obligatorio en `UPDATE`; opcional en `CREATE`/`DELETE`. Permite un rastro transversal y consultas con `JSON1`.

### 3.11. API (borrador mínimo)

- `POST /movements/rcv` — recibo simple (opcional `order_id`, `request_ref`).
- `POST /movements/out` — emisión simple (opcional `reservation_id`).
- `POST /movements/adj` — ajuste (requiere nota; `validated_by`/`at` opcional).
- `POST /movements/transfer` — crea `TRO`+`TRI` atómicos con `transfer_group_id` y `counterpart_id`.
- `POST /movements/{code}/reversal` — genera movimiento opuesto con `reversal_of_id` y validación de stock.
- `GET /movements` — filtros por `type`, `part_id`, `location_id`, `order_id`, `reason_code`, `date_from`/`to`.

> NOTA: `Movement.order_id` enlaza al header de orden (FK nullable) para trazabilidad (excesos `PO`, `TO`, etc.).

### 3.12. Algoritmos de servicio

#### 3.12.1 RCV

1. (Opcional) Vincular a `order_id`.
2. Reservar código.
3. Incrementar `on_hand`.
4. Insertar movimiento y, si aplica, `OrderFulfillment` hasta lo pendiente.
5. Excedente queda libre y trazado al `PO`.

#### 3.12.2 OUT

1. Validar `on_hand` ≥ `qty`.
2. Si hay `reservation_id` asociado, consumir esa reserva.
3. Decrementar `on_hand`.
4. Insertar movimiento.

#### 3.12.3 TRO+TRI (atómico)

1. Verificar `on_hand` en origen.
2. Generar `transfer_group_id`.
3. Decrementar origen + `TRO`.
4. Incrementar destino (UPSERT) + `TRI`.
5. Cruzar `counterpart_id`.
6. Confirmar transacción.

#### 3.12.4 ADJ

1. Verificar que no deja `on_hand` < 0.
2. Requerir nota.
3. Calcular y aplicar delta (±).
4. Insertar `ADJ`.

#### 3.12.5 Reversa

1. Cargar origen; comprobar que no está ya revertido.
2. Reservar código del tipo opuesto.
3. Validar que el inverso no viola `on_hand` ≥ 0.
4. Aplicar efecto contrario sobre stock.
5. Insertar con `reversal_of_id`.

### 3.13. Esquemas (DDL aproximado, SQLite)

#### 3.13.1 Tabla

```sql
CREATE TABLE movement (
  id                INTEGER PRIMARY KEY,
  code              TEXT NOT NULL UNIQUE,             -- TT-YY-NNNN
  type              TEXT NOT NULL,                    -- RCV|OUT|TRI|TRO|ADJ
  part_id           INTEGER NOT NULL,
  location_id       INTEGER NOT NULL,
  quantity          NUMERIC(18,6) NOT NULL,
  -- Control y trazas
  transfer_group_id TEXT NULL,                        -- UUID
  counterpart_id    INTEGER NULL,                     -- FK a movement (traslados)
  reversal_of_id    INTEGER NULL,                     -- FK a movement (reversas)
  order_id          INTEGER NULL,                     -- FK a order_header (excesos PO, TO…)
  reason_code       TEXT NULL,                        -- p.ej. 'PO','SO','TO','CNT','INV_COUNT','MANUAL_ADJ'
  validated_by      TEXT NULL,
  validated_at      TEXT NULL,                        -- UTC
  meta_json         TEXT NULL,
  note              TEXT NULL,                        -- <=240 chars
  request_ref       TEXT NULL,                        -- referencia externa opcional: albarán externo, etc.
  actor             TEXT NOT NULL,                    -- <=120 chars
  created_at        TEXT NOT NULL,                    -- UTC
  -- FKs
  FOREIGN KEY (part_id)     REFERENCES part(id),
  FOREIGN KEY (location_id) REFERENCES location(id),
  FOREIGN KEY (order_id)    REFERENCES order_header(id),
  FOREIGN KEY (counterpart_id) REFERENCES movement(id),
  FOREIGN KEY (reversal_of_id)  REFERENCES movement(id),
  -- Reglas mínimas (la regla de no-negativos se valida en servicio)
  CHECK (type IN ('RCV','OUT','TRI','TRO','ADJ')),
  CHECK (
    (type = 'ADJ'  AND quantity <> 0) OR
    (type <> 'ADJ' AND quantity  > 0)
  )
);

-- Índices de consulta
CREATE INDEX idx_movement_part_created   ON movement(part_id, created_at);
CREATE INDEX idx_movement_loc_created    ON movement(location_id, created_at);
CREATE INDEX idx_movement_type_created   ON movement(type, created_at);
CREATE INDEX idx_movement_order          ON movement(order_id);
CREATE INDEX idx_movement_transfer_group ON movement(transfer_group_id);
CREATE INDEX idx_movement_counterpart    ON movement(counterpart_id);
CREATE INDEX idx_movement_reversal_of    ON movement(reversal_of_id);
```

#### 3.13.2 Tabla `code_seq` (numeración unificada)

```sql
CREATE TABLE code_seq (
  prefix    TEXT NOT NULL,  -- e.g. 'RCV','OUT','TRI','TRO','ADJ','PO','SO',...
  year      INTEGER NOT NULL,
  next_seq  INTEGER NOT NULL,
  PRIMARY KEY (prefix, year)
);
```

### 3.14. Integración con órdenes

`Movement.order_id` enlaza con el header para trazabilidad (p. ej., exceso de un `RCV`), y `OrderFulfillment` crea el puente `M:N` entre líneas y movimientos, con `qty` con signo sólo negativo en reversas. Las líneas heredan la UoM de la parte.

### 3.15. Consideraciones de validación y datos

- UoM discreta: garantizar enteros en todas las cantidades relevantes (incluye `ADJ`).
- `UTC` & `NUMERIC(18,6)`: política global de tiempos y decimales.
- Concurrencia: aplicar `BEGIN IMMEDIATE` en contadores y actualizaciones de stock; optimiza para monousuario y evita colisiones.

### 3.16. TODOs

- Política de validación fuerte para `ADJ` (p. ej., requerir `validated_by`/`at` por umbral).
- Cambiar `reason_code` de texto libre (actualmente) a ser un catálogo (`movement_reason(code,name,active)` + FK).
- Formalizar `Location.kind` para flujos `QI`/`RMA`/`RTS` (hoy lo resolvemos por convención en `Location.code`).
- Vista por `(parte, ubicación)` si se requiere granularidad adicional (actualmente vista agregada por parte).

## 4. Órdenes

### 4.1.Objetivo y alcance

El módulo de órdenes articula las necesidades de negocio que implican movimientos de inventario. Define cabeceras y líneas, establece un ciclo de vida estandarizado, vincula movimientos a líneas mediante `OrderFulfillment`, y asegura trazabilidad completa con numeración unificada y auditoría genérica.

### 4.2. Tipología y semántica

Los tipos de orden contemplados son:

- `PO` (_Purchase Order_): órdenes de compra a proveedores.
- `SO` (_Sales Order_): órdenes de venta a clientes.
- `WO` (_Work Order_): órdenes de trabajo internas (producción, ensamblaje).
- `TO` (_Transfer Order_): traslados entre ubicaciones.
- `CNT` (_Count Order_): órdenes de conteo de inventario.
- `RMA` (_Return Merchandise Authorization_): devoluciones de clientes.
- `RTS` (_Return to Supplier_): devoluciones a proveedores.
- `QI` (_Quality Inspection_): órdenes de inspección de calidad.

Cada tipo define qué movimientos genera (ver [4.7 Interacción con inventario](#47-interaccion-con-inventario)).

### 4.3. Estructura de datos

- Cabecera (order_header):

  - `code`: numeración unificada (`TT-YY-NNNN`).
  - `type`: uno de los valores listados en [4.2 Tipología y semántica](#42-tipologia-y-semantica).
  - `status`: ciclo de vida (ver [4.4 Estados y transiciones](#44-estados-y-transiciones)).
  - `currency`: divisa aplicable a todas las líneas (no en `CNT`/`QI`).
  - `total`: importe total en la divisa definida (validado contra suma de líneas cuando proceda).
  - `created_at`, `updated_at`.

  TODO: incorporar campos de negocio como proveedor/cliente, condiciones de pago, dirección de envío, impuestos o incoterms se posponen.

- Línea (order_line):

  - `part_id`: referencia a parte.
  - `qty`: cantidad solicitada. En `CNT`, `qty` representa el `count_target` contra el que se comparará el stock real.
  - `uom_id`: UoM de la parte (heredada, validación de integridad).
  - `unit_price`, `line_total`: importes calculados en la divisa de la cabecera (no se almacena moneda a nivel de línea).
  - `from_location_id`, `to_location_id`: usado en órdenes de transferencia (`TO`).
  - `notes`: texto opcional.

- Cumplimiento (`order_fulfillment`):

  - Tabla puente `M:N` entre `order_line` y `movement`.
  - `qty` positivo o negativo (en reversas).
  - Garantiza trazabilidad entre órdenes y movimientos.

### 4.4. Estados y transiciones

- Cabecera: `DRAFT → APPROVED → IN_PROGRESS → PARTIAL → CLOSED | CANCELLED.`
- Líneas: `OPEN → PARTIAL → FULFILLED | CANCELLED.`

El estado de cabecera se deriva del estado de las líneas, pero puede ser gestionado manualmente en casos específicos (ej. cierre forzado).

### 4.5. Pricing

- La moneda y el importe total se registran en la cabecera.
- Todas las líneas expresan su importe en esa misma moneda.
- Tipos como `CNT` y `QI` pueden omitir moneda y precios, tratándose solo de cantidades.
- Se valida que el total de cabecera coincida con la suma de líneas cuando corresponda.

### 4.6. Cancelaciones y reversas

- No se eliminan órdenes ni líneas.
- Se permite reversa de movimientos asociados para garantizar trazabilidad.

TODO: en revisiones futuras se definirán políticas diferenciadas de cancelación para cada tipo de orden (p.ej. un conteo cancelado no debería generar reversas, pero un `PO` sí).

### 4.7. Interacción con inventario

Cada tipo de orden se traduce en movimientos de inventario específicos:

- `PO` → genera `RCV`.
- `SO` → genera `OUT`.
- `TO` → genera par `TRO`+`TRI`.
- `CNT` → genera `ADJ(delta)` comparando `count_target` con `on_hand`.
- `RMA` y `RTS` → generan `RCV` o `OUT` según flujo, asociados a la orden.
- `QI` → puede generar movimientos de traslado hacia/desde ubicaciones de cuarentena.

TODO: formalizar integración completa de `QI`/`RMA`/`RTS` en futuras versiones.

### 4.8. Numeración

Las órdenes comparten la tabla `code_seq(prefix, year, next_seq)` con los movimientos.
Formato: `TT-YY-NNNN`, donde `TT` es el tipo de orden (ej. `PO`, `SO`).
La reserva del siguiente número se hace dentro de una transacción (`BEGIN IMMEDIATE`).

### 4.9. Documentos asociados

Los documentos se pueden vincular tanto a cabeceras como a líneas de órdenes. Ejemplos:

- Cabecera: contrato marco, términos generales.
- Línea: hoja técnica, especificación particular.

El modelo polimórfico DocumentLink asegura trazabilidad homogénea con otras entidades.

### 4.10. Datos de negocio

Actualmente, sólo se almacenan:

- `currency`.
- `total`.

TODO: añadir en futuras versiones atributos como condiciones de pago, direcciones, impuestos, incoterms y contrapartes.

### 4.11. Auditoría

Todas las operaciones sobre órdenes (creación, modificación, cancelación) se registran en `AuditLog`.

- `CREATE` y `DELETE` no requieren `diff_json`.
- `UPDATE` requiere `diff_json` detallando cambios `{campo: [antes, después]}`.

### 4.12. API (borrador documental)

Los endpoints son genéricos (no separados por tipo de orden):

- `POST /orders/` — crear orden con cabecera y líneas.
- `PATCH /orders/{code}` — actualizar cabecera o líneas.
- `POST /orders/{code}/cancel` — cancelar orden (reversas automáticas cuando aplique).
- `POST /orders/{code}/close` — cerrar orden (manual o forzado).
- `GET /orders/` — listar órdenes (filtros por tipo, estado, fechas).
- `GET /orders/{code}` — detalle completo (cabecera + líneas).
- `GET /orders/{code}/fulfillments` — consultar movimientos asociados.

### 4.13. DDL preliminar (SQLite)

```sql
CREATE TABLE order_header (
id INTEGER PRIMARY KEY,
code TEXT NOT NULL UNIQUE, -- TT-YY-NNNN
type TEXT NOT NULL, -- PO|SO|WO|TO|CNT|RMA|RTS|QI
status TEXT NOT NULL, -- ciclo de vida
currency TEXT NULL, -- opcional en CNT/QI
total NUMERIC(18,6) NULL,
created_at TEXT NOT NULL, -- UTC
updated_at TEXT NOT NULL, -- UTC
is_deleted INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE order_line (
id INTEGER PRIMARY KEY,
order_id INTEGER NOT NULL,
part_id INTEGER NOT NULL,
qty NUMERIC(18,6) NOT NULL, -- en CNT: count_target
uom_id INTEGER NOT NULL,
unit_price NUMERIC(18,6) NULL,
line_total NUMERIC(18,6) NULL,
from_location_id INTEGER NULL,
to_location_id INTEGER NULL,
notes TEXT NULL,
FOREIGN KEY (order_id) REFERENCES order_header(id),
FOREIGN KEY (part_id) REFERENCES part(id),
FOREIGN KEY (uom_id) REFERENCES uom(id),
FOREIGN KEY (from_location_id) REFERENCES location(id),
FOREIGN KEY (to_location_id) REFERENCES location(id)
);

CREATE TABLE order_fulfillment (
id INTEGER PRIMARY KEY,
order_line_id INTEGER NOT NULL,
movement_id INTEGER NOT NULL,
qty NUMERIC(18,6) NOT NULL,
FOREIGN KEY (order_line_id) REFERENCES order_line(id),
FOREIGN KEY (movement_id) REFERENCES movement(id)
);

-- Índices de consulta
CREATE INDEX idx_order_header_code    ON order_header(code);
CREATE INDEX idx_order_header_type    ON order_header(type, status);
CREATE INDEX idx_order_line_order_id  ON order_line(order_id);
CREATE INDEX idx_order_line_part      ON order_line(part_id);
```

### 4.14. TODOs

- Definir políticas de cancelación específicas por tipo de orden.
- Incorporar datos de negocio avanzados (cliente, proveedor, impuestos, incoterms, direcciones, condiciones de pago).
- Formalizar integración completa de `QI`/`RMA`/`RTS` con ubicaciones de cuarentena y scrap.
- Añadir vista `order_status_summary` para reporting (ej. `PO` pendientes, `SO` atrasadas).

## 5. Reservas

### 5.1. Objetivo y alcance

El sistema de reservas permite apartar stock disponible para asegurar el cumplimiento de órdenes específicas.
Las reservas son siempre manuales (creadas por acción del usuario o servicio), nunca automáticas a partir de movimientos.
Pueden asociarse a cualquier tipo de orden (`PO`, `SO`, `TO`, `WO`, `CNT`, `QI`, `RMA`, `RTS`), aunque su impacto más común se da en órdenes de venta y de traslado.

### 5.2. Modelo y granularidad

- Cada reserva se vincula a una línea de orden (`order_line`), a una parte (`part_id`) y a una ubicación (`location_id`).
- La cantidad reservada (`qty`) debe ser `> 0` y sigue las reglas de la UoM de la parte:

  - UoM discreta → cantidades enteras.
  - UoM continua → cantidades decimales.

- El estado se mantiene a nivel de línea, nunca de cabecera.
- Se admite parcialidad: una reserva puede consumirse en varios movimientos, y se cierra cuando llega a cero.

### 5.3. Ciclo de vida y estados

- Estados válidos:

  - `OPEN`: reserva activa, con cantidad pendiente.
  - `CLOSED`: totalmente consumida.
  - `CANCELLED`: liberada manualmente o por cancelación de la orden/línea.

- Reglas de transición:

  - `OPEN → CLOSED` cuando `remaining_qty = 0`.
  - `OPEN → CANCELLED` cuando se libera manualmente o al cancelar la línea.
  - Una vez `CLOSED` o `CANCELLED`, no puede reabrirse.

### 5.4. Consumo y reversas

- Un movimiento (`OUT`, `TRO`) consume una reserva sólo si está explícitamente asociado a ella.
- Movimientos sin asociación no afectan reservas existentes.
- Es posible que `reserved > on_hand` (shortage), pero `on_hand` nunca puede ser negativo.
- Si un movimiento consumido se revierte, el sistema debe reponer también la reserva (si la línea sigue activa). Si la línea fue cerrada o cancelada, la reposición no se realiza; en su lugar se añade una nota de auditoría.

### 5.5. Liberación

- Las reservas pueden cancelarse manualmente desde UI o servicio.
- Al cancelar una línea u orden, todas sus reservas pendientes pasan a `CANCELLED`.
- El consumo parcial es válido: el saldo restante permanece en `OPEN` hasta consumirse o cancelarse.

### 5.6. Auditoría y validaciones

- Toda operación (`CREATE`, `UPDATE`, `CANCEL`) queda registrada en `AuditLog`.
- En `UPDATE`, se requiere `diff_json` detallando cambios de cantidad o estado.
- Validaciones mínimas:

  - `qty > 0`.
  - `status` válido.
  - `(part, location)` existentes.
  - Enteros en UoM discreta.

### 5.7. API (documental)

Endpoints genéricos para gestión de reservas:

- `POST /reservations/` — crear reserva (input: `order_line_id`, `part_id`, `location_id`, `qty`).
- `PATCH /reservations/{id}` — modificar cantidad o estado.
- `POST /reservations/{id}/consume` — registrar consumo parcial o total (vinculado a un movimiento).
- `POST /reservations/{id}/cancel` — cancelar manualmente lo pendiente.
- `GET /reservations/` — listar reservas, con filtros por `order_line`, `part`, `location`, `status`.

### 5.8. DDL preliminar (SQLite)

```sql
CREATE TABLE reservation (
  id            INTEGER PRIMARY KEY,
  order_line_id INTEGER NOT NULL,
  part_id       INTEGER NOT NULL,
  location_id   INTEGER NOT NULL,
  qty           NUMERIC(18,6) NOT NULL CHECK(qty > 0),
  remaining_qty NUMERIC(18,6) NOT NULL CHECK(remaining_qty >= 0),
  status        TEXT NOT NULL CHECK(status IN ('OPEN','CLOSED','CANCELLED')),
  created_at    TEXT NOT NULL,       -- UTC
  updated_at    TEXT NOT NULL,       -- UTC
  FOREIGN KEY (order_line_id) REFERENCES order_line(id),
  FOREIGN KEY (part_id) REFERENCES part(id),
  FOREIGN KEY (location_id) REFERENCES location(id)
);

CREATE INDEX idx_reservation_order_line ON reservation(order_line_id);
CREATE INDEX idx_reservation_part_loc   ON reservation(part_id, location_id);
CREATE INDEX idx_reservation_status     ON reservation(status);
```

### 5.9. TODOs

- Explorar reservas automáticas al aprobar órdenes (`SO`/`TO`).
- Evaluar reservas contra stock pendiente de recepción (`PO`).
- Añadir `priority` para decidir consumo cuando hay varias reservas elegibles.
- Añadir `expiry_date` para caducidad automática.
- Crear vistas de reporting (reservas pendientes por parte/ubicación).

## 6. Documentos

### 6.1. Objetivo y alcance

El subsistema de documentos permite asociar evidencia y referencias (ficheros locales y enlaces externos) a las entidades del dominio (partes, movimientos, órdenes y líneas de orden). Proporciona un modelo polimórfico de enlace, almacenamiento en disco organizado por entidad, controles básicos de integridad y una política de recolección de huérfanos para mantener el repositorio limpio.

### 6.2. Modelo conceptual

- `Document`: representación canónica del recurso:

  - `kind`: `FILE` (almacenado localmente) o `LINK` (URL externa).
  - Metadatos: nombre lógico, descripción, etiquetas, MIME, tamaño, hash (para `FILE`), autoría/fechas.

- `DocumentRole` (catálogo): vocabulario controlado que clasifica el propósito de un documento (`DATASHEET`, `SPEC`, `RECEIPT`, `PHOTO`, `CONTRACT`, `OTHER`). Es un catálogo gestionable (CRUD), similar a `PartType` pero no jerárquico. Se presiembra mediante un YAML con los roles básicos.
- `DocumentLink`: relación `N:M` entre `Document` y cualquier entidad enlazable, con:

  - `entity_type`: `part` | `movement` | `order` | `order_line`.
  - `entity_id`: identificador de la entidad.
  - `role_id`: referencia al catálogo `DocumentRole` (opcional).
  - `note`: anotación breve contextual (opcional).
  - Auditoría mínima (quién/cuándo).

> Racional: separar documento (recurso) del enlace (contexto) habilita reutilización del mismo documento en varias entidades y mantiene la trazabilidad local.

### 6.3. Almacenamiento y organización en disco (solo FILE)

- Ubicación base: `data/`.
- Estructura por entidad (rutas relativas a `data/`):

  - Partes: `parts/{ipn}/`
  - Movimientos: `movements/{movement-code}/`
  - Órdenes: `orders/{order-code}/`
  - Líneas de orden: `orders/{order-code}/lines/{line-id}/`

#### 6.3.1. Nombre de fichero y colisiones

- Se conserva el nombre original saneado (original*name), y se genera un nombre almacenado (stored_name) para evitar colisiones (recomendación: `YYYYMMDDhhmmss*{rand4}\_{original_name}`).
- Se guarda también `sha256` y `size_bytes` como metadatos (sirve para integridad/verificación y futura deduplicación).

#### 6.3.2. Saneamiento

- Se eliminan rutas y caracteres peligrosos; se limita longitud (p.ej., 120 chars).
- Whitelist de extensiones (ajustable): `pdf`, `png`, `jpg`, `jpeg`, `txt`, `csv`, `xlsx`, `docx`, `zip`.
- Tamaño máximo por fichero: 50 MB.

#### 6.3.3. Deduplicación

No se hace deduplicación automática (se admite mismo contenido en distintas rutas).

TODO: deduplicación por hash (tabla de blobs + hardlinks/symlinks) si el volumen crece.

### 6.4. Ciclo de vida: creación, enlace y limpieza

1. Alta de `FILE`:

- Validaciones (tamaño, extensión, MIME opcional).
- Cálculo de `sha256` y persistencia en disco en la ruta de entidad correspondiente.
- Inserción en `Document(kind='FILE', ...)` + creación de `DocumentLink`.

2. Alta de `LINK`:

- Validación de formato URL (no se exige accesibilidad en v1).
- Inserción en `Document(kind='LINK', url, ...)` + `DocumentLink`.

3. Borrado de enlaces y GC de huérfanos:

- Al eliminar un `DocumentLink`, el servicio verifica si el `Document` queda huérfano (sin enlaces).
- Si queda huérfano:

  - Para `LINK`: se elimina el registro `Document` (no hay FS que limpiar).
  - Para `FILE`: se elimina el fichero físico de su ruta, y después el `Document`.

- Tareas de GC periódicas pueden revalidar huérfanos (seguridad pasiva).

> Nota: si un documento está enlazado a múltiples entidades, no se elimina hasta que todos sus `DocumentLink` se hayan borrado.

### 6.5. Seguridad y privacidad (v1)

- No se integra antivirus/escaneo en esta versión.
  TODO: definir política de análisis (on-upload o batch).

- No se eliminan metadatos EXIF/ICC en imágenes por ahora.
  TODO: limpieza opcional de metadatos sensibles.

- Sin cuotas por usuario/entidad en esta versión.
  TODO: límites por uploaded_by/proyecto.

### 6.6. Reglas y validaciones

- `Document`:

  - `kind IN ('FILE','LINK')`.
  - `name` obligatorio; `description`, `tags` opcionales.
  - `mime` y `size_bytes` obligatorios en `FILE` (recomendado en `LINK` si se conoce).
  - `sha256` obligatorio en `FILE`, `NULL` en `LINK`.
  - Para `LINK`, `url` obligatoria (formato URL válido).

- `DocumentRole`:

  - `code` único (p.ej., `DATASHEET`, `SPEC`), `name` legible.
  - Activación/desactivación por `active` (no se borra si está en uso).

- `DocumentLink`:

  - `entity_type` en conjunto permitido.
  - `role_id` opcional; si se informa, FK válida.
  - Un mismo `Document` puede enlazarse múltiples veces a distintas entidades.
  - Auditoría mínima de creación.

### 6.7. API (documental, genérica)

- `POST /documents`

  - `FILE`: `kind='FILE'`, `entity_type`, `entity_id`, `role_code?`, `note?`, fichero binario.
  - `LINK`: `kind='LINK'`, `url`, `name`, `entity_type`, `entity_id`, `role_code?`, `note?`.
  - Respuesta: `document_id`, y `document_link_id`.

- `GET /documents/{id}` — metadatos del documento (sin binario).
- `DELETE /documents/{id}` — solo si no tiene enlaces; si los tiene, responder 409.
- `POST /document-links` — crear enlace adicional de un documento existente a otra entidad.
- `DELETE /document-links/{id}` — borra el enlace; si deja huérfano, elimina el `Document` (y el fichero si `FILE`).
- `GET /entities/{type}/{id}/documents` — lista documentos vinculados (incluye `role`, `note`).

> Observación: el upload/download del binario (`FILE`) se maneja en rutas específicas (p.ej., `POST /documents` para subida, `GET /documents/{id}/download` para descarga).

### 6.8. DDL (SQLite)

### 6.8.1. Catálogo de roles (document_role)

```sql
CREATE TABLE document_role (
  id         INTEGER PRIMARY KEY,
  code       TEXT NOT NULL UNIQUE,      -- p.ej., 'DATASHEET','SPEC','RECEIPT','PHOTO'
  name       TEXT NOT NULL,             -- legible
  active     INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL,             -- UTC
  updated_at TEXT NOT NULL              -- UTC
);
```

### 6.8.2. Documentos (document)

```sql
CREATE TABLE document (
  id          INTEGER PRIMARY KEY,
  kind        TEXT NOT NULL CHECK (kind IN ('FILE','LINK')),
  name        TEXT NOT NULL,                 -- nombre lógico mostrado en UI
  description TEXT NULL,
  tags        TEXT NULL,                     -- CSV opcional (p.ej., 'spec,revA')
  mime        TEXT NULL,                     -- recomendado (obligatorio en FILE)
  size_bytes  INTEGER NULL,                  -- obligatorio en FILE
  sha256      TEXT NULL,                     -- obligatorio en FILE; NULL en LINK
  url         TEXT NULL,                     -- obligatorio en LINK; NULL en FILE
  stored_dir  TEXT NULL,                     -- relativo a data/  (solo FILE)
  stored_name TEXT NULL,                     -- nombre saneado en disco (solo FILE)
  original_name TEXT NULL,                   -- nombre original (solo FILE)
  uploaded_by TEXT NOT NULL,                 -- actor
  created_at  TEXT NOT NULL,                 -- UTC
  updated_at  TEXT NOT NULL                  -- UTC
);

-- Reglas (reforzadas a nivel de servicio):
-- FILE  => url IS NULL AND sha256,size_bytes,stored_dir,stored_name,original_name NOT NULL
-- LINK  => url NOT NULL AND sha256,size_bytes,stored_dir,stored_name,original_name IS NULL

CREATE INDEX idx_document_kind_created ON document(kind, created_at);
CREATE INDEX idx_document_sha256       ON document(sha256);
```

### 6.8.3. Enlaces (document_link)

```sql
CREATE TABLE document_link (
  id           INTEGER PRIMARY KEY,
  document_id  INTEGER NOT NULL,
  entity_type  TEXT NOT NULL CHECK (entity_type IN ('part','movement','order','order_line')),
  entity_id    INTEGER NOT NULL,
  role_id      INTEGER NULL,
  note         TEXT NULL,                 -- <=240 chars
  created_at   TEXT NOT NULL,             -- UTC
  created_by   TEXT NOT NULL,             -- actor
  FOREIGN KEY (document_id) REFERENCES document(id),
  FOREIGN KEY (role_id) REFERENCES document_role(id)
);

CREATE INDEX idx_document_link_doc          ON document_link(document_id);
CREATE INDEX idx_document_link_entity       ON document_link(entity_type, entity_id);
CREATE INDEX idx_document_link_role         ON document_link(role_id);
```

> Integridad referencial: las FKs a entidades enlazadas (`part`, `movement`, `order_header`, `order_line`) se validan en servicio (no se declara FK dura aquí para mantener el polimorfismo). Se pueden añadir checks de existencia si se implementa una vista/materialización por tipo.

### 6.9. Operativa de servicio (resumen)

#### 6.9.1. Alta de FILE

1. Validar `entity_type`/`entity_id`, `role_code?`, tamaño/extensión.
2. Saneado de nombre, cálculo de `sha256`.
3. Determinar `stored_dir` por entidad (`parts/{ipn}`, `movements/{code}`, `orders/{code}`, `orders/{code}/lines/{line_id}`) y crear árbol si no existe.
4. Persistir fichero como `stored_name` en `stored_dir`.
5. Insertar `Document` + `DocumentLink`.

#### 6.9.2. Alta de LINK

1. Validar URL.
2. Insertar `Document(kind='LINK', url, …)` + `DocumentLink`.

#### 6.9.3. Borrado de enlace y GC

1. Eliminar `DocumentLink`.
2. Comprobar si el `document_id` quedó sin enlaces:

- Si queda sin enlaces:

  - `LINK` → borrar fila `document`.
  - `FILE` → borrar fichero en `data/...`, luego borrar `document`.

- Si aún quedan enlaces: no se borra el documento.

### 6.10. TODOs

- Antivirus/escaneo de ficheros y validación de accesibilidad para `LINK`.
- Deduplicación por `sha256` (tabla de blobs + hardlinks).
- Miniaturas/preview para imágenes/PDF.
- Cuotas por usuario/entidad y políticas de retención (GDPR/archivado).
- Metadatos sensibles (EXIF): anonimización opcional.
- Validaciones cruzadas de enlaces (FK polimórfica materializada o triggers por tipo).

## 7. Auditoría

### 7.1. Objetivo y alcance

El subsistema de auditoría garantiza trazabilidad completa de todas las operaciones que modifican el estado del sistema. Cada mutación queda registrada con actor, fecha/hora, acción y detalle de los cambios. Esto permite reconstruir la historia de cualquier entidad, verificar responsabilidades y cumplir con posibles exigencias regulatorias.

Se auditan todas las entidades principales (`part`, `movement`, `order_header`, `order_line`, `reservation`, `document`, `document_link`, `catálogos`) y se deja abierto a incluir eventos transversales como `IMPORT`/`EXPORT`.

### 7.2. Eventos auditados

- `CREATE`: creación de entidad.
- `UPDATE`: modificación de campos existentes (requiere `diff_json`).
- `DELETE`: borrado (lógico o físico). En soft-delete se registra `meta_json.soft=true`.
- `RESTORE`: recuperación de entidad previamente eliminada.
- `REVERSAL`: operación de anulación vinculada a otra (ej. movimiento revertido).
- `STATUS_CHANGE`: cambio explícito de estado (p.ej., `order.status`).
- `IMPORT` / `EXPORT`: cargas y extracciones de datos.
- Otros: se podrán añadir en el futuro según necesidades.

No se auditan lecturas (`READ`), salvo en operaciones de exportación por motivos de trazabilidad.

### 7.3. Datos registrados

Cada entrada en el log incluye:

- `entity_type`: tipo de entidad afectada.
- `entity_id`: identificador único de la entidad.
- `action`: acción realizada (de la lista anterior).
- `actor`: usuario/servicio que ejecuta la acción.
- `ts_utc`: fecha/hora en UTC (ISO-8601).
- `request_id`: opcional, para correlacionar varios eventos de una misma operación.
- `ip`, `user_agent`: opcionales, para auditar contexto de la petición.
- `note`: comentario libre breve (opcional).
- `diff_json`: obligatorio en `UPDATE`, describe los cambios `{campo: {from: x, to: y}}`.
- `meta_json`: datos contextuales adicionales (ej. `reversal_of`).

### 7.4. Reglas operativas

- La inserción en `audit_log` forma parte de la misma transacción que la operación de negocio. Si falla el registro de auditoría, la operación no se confirma.
- `UPDATE` debe siempre incluir `diff_json`.
- `REVERSAL` debe incluir referencia a la operación revertida (`meta_json.reversal_of`).
- `DELETE` lógico se registra con `meta_json.soft=true`.
- `RESTORE` se registra de forma explícita como evento independiente.
- En reintentos, si se reaprovecha un mismo `request_id`, el sistema debe evitar duplicar eventos.
- Campos largos en `diff_json` pueden truncarse (> 1 KB). Los datos binarios no se registran.

### 7.5. Retención y volumen

- Para esta revisión, no se define purga automática; el log es permanente.
  TODO: política de retención (p. ej., 24 meses) y exportación periódica a ficheros firmados.
- Índices optimizados para consultas por entidad, acción, actor y rango temporal.
- Se recomienda `VACUUM` y `PRAGMA` de mantenimiento en SQLite para mitigar crecimiento.

### 7.6. Consultas típicas

Algunas consultas típicas esperadas son:

- Historial de un `part.ipn` o `order.code`.
- Cambios de estado de una orden en un intervalo.
- Reconstrucción de una operación compleja (ej. `request_id` de un traslado `TRO`+`TRI`).
- Acciones de un actor específico en un periodo.

### 7.7. API documental

- `GET /audit?entity_type=&entity_id=&action=&from=&to=&actor=&request_id=`

  - Respuesta paginada con filtros.

  - No se devuelven datos binarios ni campos sensibles.

  TODO: `GET /audit/export` (CSV/JSONL), con firma de integridad.

### 7.8. DDL (SQLite)

```sql
CREATE TABLE audit_log (
  id          INTEGER PRIMARY KEY,
  entity_type TEXT NOT NULL,   -- 'part','movement','order_header',...
  entity_id   INTEGER NOT NULL,
  action      TEXT NOT NULL,   -- 'CREATE','UPDATE','DELETE','RESTORE','REVERSAL','STATUS_CHANGE','IMPORT','EXPORT'
  actor       TEXT NOT NULL,   -- quién ejecuta
  ts_utc      TEXT NOT NULL,   -- ISO-8601 UTC
  request_id  TEXT NULL,       -- correlación multi-evento
  ip          TEXT NULL,
  user_agent  TEXT NULL,
  note        TEXT NULL,
  diff_json   TEXT NULL,       -- obligatorio en UPDATE
  meta_json   TEXT NULL        -- datos contextuales
);

CREATE INDEX idx_audit_entity_ts   ON audit_log(entity_type, entity_id, ts_utc);
CREATE INDEX idx_audit_request_ts  ON audit_log(request_id, ts_utc);
CREATE INDEX idx_audit_actor_ts    ON audit_log(actor, ts_utc);
CREATE INDEX idx_audit_action_ts   ON audit_log(action, ts_utc);
```

### 7.9. TODOs

- Definir política de retención y exportación (firmada).
- Ampliar `meta_json` para trazas de procesos compuestos.
- Catálogo de campos sensibles a anonimizar (cuando se incluyan datos de terceros).
- Soporte de auditoría a nivel de sesión/login.

## 8. Proveedores y Precios

### 8.1. Objetivo y alcance

El módulo de proveedores y precios permite vincular cada parte a uno o varios distribuidores, capturar sus condiciones de compra (SKU del distribuidor, cantidades mínimas y múltiplos, lead time) y mantener estructuras de precios escalonados por cantidad (`price_breaks`).

Este subsistema soporta la preparación de órdenes de compra (`PO`) seleccionando automáticamente los precios aplicables y asegurando que siempre exista un distribuidor preferido para cada parte, cuando haya varios.

### 8.2. Entidades principales

- `Distributor`: catálogo de distribuidores/proveedores disponibles.
- `PartDistributor`: relación entre una parte y un distribuidor, incluyendo SKU y condiciones de suministro.
- `PriceBreak`: desglose de precios por cantidad mínima, expresado en una moneda determinada y con vigencia temporal opcional.

### 8.3. Distributor

- Catálogo gestionable por el usuario (CRUD completo).
- Atributos principales:

  - `code`: identificador corto único (`digikey`, `mouser`, …).
  - `name`: nombre legible.
  - `active`: booleano para habilitar/deshabilitar sin perder histórico.

- Integridad:

  - `code` único.
  - Se recomienda normalizar códigos en minúsculas.

### 8.4. PartDistributor

- Relación entre una parte y un distribuidor.
- Campos clave:

  - `part_id`, `distributor_id`.
  - `supplier_pn`: número de parte asignado por el distribuidor.
  - `packaging`: texto opcional (ej. "Reel 2500 pcs").
  - `moq`, `mpq`, `spq`: mínimos de compra, múltiplos y tamaño de paquete.
  - `lead_time_days`: plazo estimado en días.
  - `preferred`: booleano; a lo sumo uno por parte.
  - `active`: estado de vigencia.

- Reglas:

  - Una parte puede tener varios distribuidores, pero sólo uno preferido (`preferred=1`).
  - Se recomienda definir un distribuidor preferido en todas las partes críticas para compras.
  - Desactivación (`active=0`) mantiene histórico sin permitir nuevos usos.

### 8.5. PriceBreak

- Desglose de precios escalonados, asociados a un `part_id` + `distributor_id`.
- Atributos:

  - `currency`: divisa (ej. EUR, USD).
  - `min_qty`: cantidad mínima para aplicar el precio.
  - `unit_price`: precio unitario en la moneda indicada.
  - `valid_from`, `valid_to`: vigencia temporal opcional.
  - `active`: estado del registro.

- Reglas de negocio:

  - `min_qty > 0`, `unit_price ≥ 0`.
  - Para un mismo `part_id` + `distributor_id` + `currency`, puede haber varios escalones diferenciados por `min_qty`.
  - En la creación de un `PO`, el sistema selecciona automáticamente el break válido con mayor `min_qty ≤ qty`.
  - Si la orden no cumple `moq`/`mpq`/`spq`, se genera una advertencia en la capa de servicio pero no se bloquea.

### 8.6. Interacción con órdenes

- Al crear una línea de `PO`, el sistema:

  - Permite seleccionar un `distributor_id` asociado a la parte.
  - Calcula automáticamente `unit_price` a partir del `price_break` aplicable.
  - Congela `unit_price` y `line_total` en la orden (aunque cambien los catálogos después).

- Los atributos `moq`/`mpq`/`spq` se validan y, si no se cumplen, el sistema notifica al usuario.

### 8.7. API (documental)

- Distribuidores

  - `GET /distributors` — listar.
  - `POST /distributors` — crear.
  - `PATCH /distributors/{id}` — modificar.
  - `DELETE /distributors/{id}` — desactivar.

- Parte–Distribuidor

  - `GET /parts/{ipn}/distributors` — lista de distribuidores asociados a una parte.
  - `POST /parts/{ipn}/distributors` — crear vínculo (part_distributor).
  - `PATCH /parts/{ipn}/distributors/{id}` — modificar condiciones (MOQ, preferred, etc.).
  - `DELETE /parts/{ipn}/distributors/{id}` — desactivar vínculo.

- Price breaks

  - `POST /parts/{ipn}/distributors/{dist_id}/price-breaks` — alta.
  - `PATCH /price-breaks/{id}` — modificar.
  - `DELETE /price-breaks/{id}` — desactivar.

- Ayuda al PO

  - `GET /pricing/suggestion?part_id=&distributor_id=&qty=&currency=` — Devuelve el price_break aplicable y el cálculo total.

### 8.8. DDL preliminar (SQLite)

```sql
CREATE TABLE distributor (
  id         INTEGER PRIMARY KEY,
  code       TEXT NOT NULL UNIQUE,
  name       TEXT NOT NULL,
  active     INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE part_distributor (
  id              INTEGER PRIMARY KEY,
  part_id         INTEGER NOT NULL,
  distributor_id  INTEGER NOT NULL,
  supplier_pn     TEXT NOT NULL,
  packaging       TEXT NULL,
  moq             NUMERIC(18,6) NULL,
  mpq             NUMERIC(18,6) NULL,
  spq             NUMERIC(18,6) NULL,
  lead_time_days  INTEGER NULL,
  preferred       INTEGER NOT NULL DEFAULT 0,
  active          INTEGER NOT NULL DEFAULT 1,
  created_at      TEXT NOT NULL,
  updated_at      TEXT NOT NULL,
  FOREIGN KEY (part_id) REFERENCES part(id),
  FOREIGN KEY (distributor_id) REFERENCES distributor(id),
  UNIQUE(part_id, distributor_id, supplier_pn)
);

-- Regla de servicio: a lo sumo un preferred=1 por part_id

CREATE TABLE price_break (
  id             INTEGER PRIMARY KEY,
  part_id        INTEGER NOT NULL,
  distributor_id INTEGER NOT NULL,
  currency       TEXT NOT NULL,
  min_qty        NUMERIC(18,6) NOT NULL,
  unit_price     NUMERIC(18,6) NOT NULL,
  valid_from     TEXT NULL,
  valid_to       TEXT NULL,
  active         INTEGER NOT NULL DEFAULT 1,
  created_at     TEXT NOT NULL,
  updated_at     TEXT NOT NULL,
  FOREIGN KEY (part_id) REFERENCES part(id),
  FOREIGN KEY (distributor_id) REFERENCES distributor(id)
);

CREATE INDEX idx_price_break_lookup
  ON price_break(part_id, distributor_id, currency, min_qty);
```

### 8.9. Auditoría

Todas las operaciones (`CREATE`, `UPDATE`, `DELETE`) sobre `distributor`, `part_distributor` y `price_break` se registran en `AuditLog`.

- En `UPDATE`, se guarda `diff_json`.
- Cambios de preferred en `part_distributor` generan evento explícito.

### 8.10. TODOs

- Integración con APIs externas de distribuidores (Mouser, DigiKey, etc.).
- Políticas de validación de `moq`/`mpq`/`spq` más estrictas en órdenes de compra.
- Vistas de reporting: mejores precios por parte, histórico de vigencias, alertas de caducidad.
- Constraint a nivel de base de datos para garantizar un único `preferred=1` por `part_id` (requiere índice parcial).

## 9. Tests recomendados (`pytest`)

### 9.1. Partes (IPN, variantes, tipos, reglas)

- `test_part_post_creates_new_base_or_variant_in_same_endpoint()`: Crea parte con nueva base y variante de base existente desde el mismo endpoint `POST /parts/`. Valida patrón IPN `^\d{6}-\d{2}$` y unicidad.
- `test_ipn_update_when_variant_changes_audited_with_diff()`: Cambiar `VV` ⇒ recalcula `ipn` y registra `UPDATE` con `diff_json` obligatorio.
- `test_part_type_is_leaf_required_for_assignment()`: Rechaza asignar part_type no hoja (niveles 1–2 solo clasificación).
- `test_part_type_hierarchy_crud_no_cycles_and_delete_rules()`: CRUD jerárquico 3 niveles; sin ciclos; no delete si tiene hijos, permitir `active=0`.
- `test_part_soft_delete_and_list_filters_exclude_deleted()`: Soft-delete (`is_deleted=1`) oculta en listados, mantiene integridad de referencias.
- `test_uom_discrete_enforces_integers_in_services()`: Si UoM es discreta (p. ej., `pcs`), cantidades enteras en BOM/movimientos/órdenes (validación de servicio).
- `test_part_receiving_location_nullable_fk()`: `receiving_location_id` es FK nullable y se persiste en `Part`.

### 9.2. Auditoría y numeración

- `test_auditlog_update_requires_diff_json()`: En `UPDATE`, `diff_json` es obligatorio en `AuditLog`.
- `test_auditlog_create_delete_without_diff_ok()`: `CREATE`/`DELETE` se audita sin `diff_json`.
- `test_code_seq_increments_per_prefix_and_year_unified()`: Un único `code_seq(prefix,year,next_seq)` para órdenes y movimientos con reserva en transacción.

### 9.3. Inventario y movimientos

- `test_rcv_increments_on_hand_and_audits()`: RCV suma stock y deja rastro (ledger único).
- `test_out_requires_sufficient_on_hand()`: Prohíbe OUT si origen `on_hand < qty`.
- `test_adj_negative_fails_if_drives_below_zero()`: ADJ no puede llevar `on_hand` por debajo de `0`; nota requerida.

- `test_reversal_creates_compensating_movement_and_restores_stock()`: Reversas mediante movimiento opuesto con `reversal_of_id`.
- `test_code_seq_for_movement_prefixes()`: Códigos humanos `TT-YY-NNNN` para RCV/OUT/TRI/TRO/ADJ.
- `test_transfer_creates_tro_and_tri_atomically()`: TRO + TRI en una sola transacción, con `transfer_group_id` y `counterpart_id`.

### 9.4. Vista agregada y mínimos

- `test_part_inventory_view_aggregates_totals()`: La vista part_inventory agrega `on_hand`/`reserved` sin desnormalizar.
- `test_below_minimum_flag_in_ui_only()`: La alerta por `minimum_qty` es visual, no bloquea operaciones (comportamiento documentado).

### 9.5. Órdenes y pricing

- `test_order_code_seq_uses_unified_table()`: Las órdenes usan el mismo code_seq unificado.
- `test_header_total_matches_sum_of_lines_when_both_present()`: Si hay precio en cabecera y líneas, validar suma y misma moneda.
- `test_status_transitions_by_line_and_header()`: Transiciones `DRAFT→APPROVED→IN_PROGRESS→PARTIAL→CLOSED`|`CANCELLED`.
- `test_cnt_line_uses_count_target_to_post_adj_delta()`: CNT aplica ADJ(delta) con count_target.
- `test_po_over_receipt_keeps_unassigned_remainder_and_links_to_po()`: No sobre-cumplir líneas; exceso queda libre y vinculado al PO.

### 9.6. Reservas

- `test_create_reservation_increases_reserved_total()`: `InventoryItem.reserved = Σ OPEN reservations` por `(parte, ubicación)`.
- `test_issue_consumes_associated_reservation_only()`: Verifica que OUT/TRO sólo consumen la reserva asociada; OUT sin asociación no toca reserved.
- `test_shortage_allowed_when_reserved_exceeds_on_hand()`: Se permite shortage (`reservado > on_hand`), pero no `on_hand` negativo.

### 9.7. Documentos

- `test_link_document_to_part_and_movement()`: Modelo polimórfico `Document + DocumentLink` (multi-entidad).
- `test_orphan_file_document_deletes_local_blob()`: Limpieza de huérfanos cuando un FILE queda sin enlaces.

### 9.8. Infra/entorno de tests

- `test_db_starts_with_foreign_keys_on_and_wal()`: Arranque SQLite con `PRAGMA foreign_keys=ON` y `journal_mode=WAL`.
- `test_begin_immediate_smoke_for_counters()`: Se puede abrir transacción `BEGIN IMMEDIATE` para contadores/secuencias.
