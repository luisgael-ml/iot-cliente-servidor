-- =====================================================================
-- Servidor de base de datos: IoT Analytics Dashboard (NexoDev Solutions)
-- Esquema relacional para dispositivos, sensores, lecturas y alertas
-- =====================================================================

-- Dispositivos físicos instalados en la planta
CREATE TABLE dispositivos (
    id         SERIAL PRIMARY KEY,
    codigo     VARCHAR(20)  NOT NULL UNIQUE,
    nombre     VARCHAR(60)  NOT NULL,
    ubicacion  VARCHAR(60)  NOT NULL,
    estado     VARCHAR(15)  NOT NULL DEFAULT 'activo'
               CHECK (estado IN ('activo', 'mantenimiento', 'inactivo')),
    creado_en  TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- Cada dispositivo tiene uno o varios sensores
CREATE TABLE sensores (
    id              SERIAL PRIMARY KEY,
    dispositivo_id  INT          NOT NULL REFERENCES dispositivos(id) ON DELETE CASCADE,
    codigo          VARCHAR(20)  NOT NULL UNIQUE,
    tipo            VARCHAR(20)  NOT NULL,   -- temperatura, vibracion, energia
    unidad          VARCHAR(10)  NOT NULL,   -- °C, mm/s, kWh
    umbral_max      NUMERIC(10,2)            -- valor a partir del cual se genera una alerta
);

-- Historial de lecturas (solo inserciones)
CREATE TABLE lecturas (
    id          BIGSERIAL PRIMARY KEY,
    mensaje_id  UUID          NOT NULL UNIQUE,    -- evita duplicados si RabbitMQ reenvía un mensaje
    sensor_id   INT           NOT NULL REFERENCES sensores(id) ON DELETE CASCADE,
    valor       NUMERIC(10,2) NOT NULL,
    medido_en   TIMESTAMPTZ   NOT NULL,           -- hora en que el sensor tomó la lectura
    recibido_en TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);
-- Índice para consultar rápido las lecturas de un sensor en un rango de tiempo
CREATE INDEX idx_lecturas_sensor_fecha ON lecturas (sensor_id, medido_en DESC);

-- Alertas generadas por el propio servidor cuando una lectura supera el umbral
CREATE TABLE alertas (
    id          SERIAL PRIMARY KEY,
    lectura_id  BIGINT        NOT NULL REFERENCES lecturas(id) ON DELETE CASCADE,
    sensor_id   INT           NOT NULL REFERENCES sensores(id) ON DELETE CASCADE,
    valor       NUMERIC(10,2) NOT NULL,
    umbral      NUMERIC(10,2) NOT NULL,
    creada_en   TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    atendida    BOOLEAN       NOT NULL DEFAULT FALSE
);

-- ---------------------------------------------------------------------
-- Lógica del lado del servidor: trigger que crea alertas automáticamente
-- ---------------------------------------------------------------------
CREATE FUNCTION generar_alerta() RETURNS TRIGGER AS $$
DECLARE
    v_umbral NUMERIC(10,2);
BEGIN
    SELECT umbral_max INTO v_umbral FROM sensores WHERE id = NEW.sensor_id;
    IF v_umbral IS NOT NULL AND NEW.valor > v_umbral THEN
        INSERT INTO alertas (lectura_id, sensor_id, valor, umbral)
        VALUES (NEW.id, NEW.sensor_id, NEW.valor, v_umbral);
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_generar_alerta
AFTER INSERT ON lecturas
FOR EACH ROW EXECUTE FUNCTION generar_alerta();

-- Vista con la última lectura de cada sensor (usada por el cliente y Grafana)
CREATE VIEW v_ultima_lectura AS
SELECT DISTINCT ON (s.id)
       d.codigo AS dispositivo, d.ubicacion, s.codigo AS sensor, s.tipo, s.unidad,
       l.valor, s.umbral_max, l.medido_en
FROM sensores s
JOIN dispositivos d ON d.id = s.dispositivo_id
LEFT JOIN lecturas l ON l.sensor_id = s.id
ORDER BY s.id, l.medido_en DESC NULLS LAST;

-- ---------------------------------------------------------------------
-- Usuarios con permisos mínimos (cada cliente solo puede lo que necesita)
-- ---------------------------------------------------------------------
-- Consumidor de RabbitMQ: solo inserta lecturas
CREATE ROLE ingesta LOGIN PASSWORD 'ingesta123';
GRANT SELECT ON sensores TO ingesta;
GRANT INSERT ON lecturas, alertas TO ingesta;
GRANT USAGE ON SEQUENCE lecturas_id_seq, alertas_id_seq TO ingesta;
GRANT SELECT ON lecturas TO ingesta;   -- necesario para ON CONFLICT

-- Cliente de consultas (operador de planta): consulta y administra, pero no borra dispositivos
CREATE ROLE operador LOGIN PASSWORD 'operador123';
GRANT SELECT ON ALL TABLES IN SCHEMA public TO operador;
GRANT INSERT, UPDATE ON dispositivos, sensores TO operador;
GRANT UPDATE (atendida) ON alertas TO operador;
GRANT DELETE ON lecturas, alertas TO operador;
GRANT USAGE ON SEQUENCE dispositivos_id_seq, sensores_id_seq TO operador;

-- Grafana: solo lectura
CREATE ROLE grafana_ro LOGIN PASSWORD 'grafana123';
GRANT SELECT ON ALL TABLES IN SCHEMA public TO grafana_ro;

-- ---------------------------------------------------------------------
-- Datos iniciales: 3 dispositivos con 3 sensores cada uno
-- ---------------------------------------------------------------------
INSERT INTO dispositivos (codigo, nombre, ubicacion) VALUES
('PRE-03', 'Prensa hidráulica 3', 'Línea 1'),
('TOR-01', 'Torno CNC 1',         'Línea 2'),
('EMB-02', 'Embotelladora 2',     'Línea 3');

INSERT INTO sensores (dispositivo_id, codigo, tipo, unidad, umbral_max) VALUES
(1, 'PRE03-TEMP', 'temperatura', '°C',   85.00),
(1, 'PRE03-VIB',  'vibracion',   'mm/s',  7.00),
(1, 'PRE03-ENE',  'energia',     'kWh',  30.00),
(2, 'TOR01-TEMP', 'temperatura', '°C',   80.00),
(2, 'TOR01-VIB',  'vibracion',   'mm/s',  6.00),
(2, 'TOR01-ENE',  'energia',     'kWh',  25.00),
(3, 'EMB02-TEMP', 'temperatura', '°C',   75.00),
(3, 'EMB02-VIB',  'vibracion',   'mm/s',  5.00),
(3, 'EMB02-ENE',  'energia',     'kWh',  20.00);
