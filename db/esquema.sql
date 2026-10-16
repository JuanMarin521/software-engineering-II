-- Esquema del historial. El rol de la aplicación solo puede insertar y consultar (RN010).
CREATE TABLE IF NOT EXISTS evento_alerta (
    id          BIGSERIAL PRIMARY KEY,
    alerta_id   UUID        NOT NULL,
    evento      TEXT        NOT NULL,
    actor       TEXT,
    t_utc       TIMESTAMPTZ NOT NULL
);
CREATE TABLE IF NOT EXISTS lectura (
    id          BIGSERIAL PRIMARY KEY,
    variable    TEXT             NOT NULL,
    valor       DOUBLE PRECISION,
    calidad     TEXT             NOT NULL,
    diferida    BOOLEAN          NOT NULL DEFAULT FALSE,
    t_utc       TIMESTAMPTZ      NOT NULL,
    duracion_ns BIGINT                      -- BIGINT: un INTEGER desbordaría con 2^31 ns (2,1 s)
);
CREATE TABLE IF NOT EXISTS auditoria (
    id          BIGSERIAL PRIMARY KEY,
    usuario     TEXT        NOT NULL,
    accion      TEXT        NOT NULL,
    resultado   TEXT        NOT NULL,
    t_utc       TIMESTAMPTZ NOT NULL
);

CREATE ROLE gemelo_app LOGIN;
GRANT SELECT, INSERT ON evento_alerta, lectura, auditoria TO gemelo_app;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO gemelo_app;
REVOKE UPDATE, DELETE, TRUNCATE ON evento_alerta, lectura, auditoria FROM gemelo_app;

-- Solo el trabajo de retención puede eliminar filas vencidas.
CREATE ROLE gemelo_retencion LOGIN;
GRANT SELECT, DELETE ON lectura, evento_alerta, auditoria TO gemelo_retencion;
