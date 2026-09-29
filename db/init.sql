DROP TABLE IF EXISTS movimientos, medicamentos, servicios, usuarios, roles CASCADE;

CREATE TABLE roles (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(30) NOT NULL UNIQUE
);

CREATE TABLE usuarios (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,
    usuario VARCHAR(30) NOT NULL UNIQUE,
    password_hash VARCHAR(100) NOT NULL,
    rol_id INT NOT NULL REFERENCES roles(id),
    estado VARCHAR(10) NOT NULL DEFAULT 'ACTIVO' CHECK (estado IN ('ACTIVO', 'INACTIVO'))
);

CREATE TABLE servicios (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(80) NOT NULL UNIQUE
);

CREATE TABLE medicamentos (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(80) NOT NULL,
    principio_activo VARCHAR(80) NOT NULL,
    presentacion VARCHAR(60) NOT NULL,
    cantidad_actual INT NOT NULL CHECK (cantidad_actual >= 0),
    stock_minimo INT NOT NULL CHECK (stock_minimo >= 0),
    fecha_vencimiento DATE NOT NULL,
    ubicacion VARCHAR(60) NOT NULL,
    estado VARCHAR(10) NOT NULL DEFAULT 'ACTIVO' CHECK (estado IN ('ACTIVO', 'INACTIVO'))
);

CREATE UNIQUE INDEX ux_medicamentos_nombre ON medicamentos (lower(nombre));

CREATE TABLE movimientos (
    id SERIAL PRIMARY KEY,
    medicamento_id INT NOT NULL REFERENCES medicamentos(id),
    tipo VARCHAR(7) NOT NULL CHECK (tipo IN ('ENTRADA', 'SALIDA')),
    cantidad INT NOT NULL CHECK (cantidad > 0),
    fecha TIMESTAMP NOT NULL DEFAULT now(),
    usuario_id INT NOT NULL REFERENCES usuarios(id),
    lote VARCHAR(40),
    fecha_vencimiento DATE,
    CHECK (tipo = 'ENTRADA' OR (lote IS NULL AND fecha_vencimiento IS NULL))
);
CREATE INDEX idx_movimientos_medicamento_fecha ON movimientos (medicamento_id, fecha);

INSERT INTO roles (nombre) VALUES ('ADMINISTRADOR'), ('FARMACIA'), ('ALMACENISTA');

INSERT INTO usuarios (nombre, usuario, password_hash, rol_id) VALUES
('Administrador Demo', 'admin', '$2b$10$tqRzyxhni0q4NIKAhMHixuHQqgAvZ8ZdwV4w0aJrJG0VbROymjGk2', 1),
('Responsable de Farmacia Demo', 'farmacia', '$2b$10$tqRzyxhni0q4NIKAhMHixuHQqgAvZ8ZdwV4w0aJrJG0VbROymjGk2', 2),
('Almacenista Demo', 'almacen', '$2b$10$tqRzyxhni0q4NIKAhMHixuHQqgAvZ8ZdwV4w0aJrJG0VbROymjGk2', 3);

INSERT INTO servicios (nombre) VALUES ('Farmacia'), ('Almacén de medicamentos'), ('Administración');

-- 3 bajo el mínimo (1,2,3) y 3 que vencen en menos de 30 días (4,5,6).
INSERT INTO medicamentos (nombre, principio_activo, presentacion, cantidad_actual, stock_minimo, fecha_vencimiento, ubicacion) VALUES
('Acetaminofén', 'Acetaminofén',        'Tabletas 500 mg',    15,  50, CURRENT_DATE + 400, 'Estante A1'),
('Amoxicilina',  'Amoxicilina',         'Cápsulas 500 mg',     8,  40, CURRENT_DATE + 200, 'Estante A2'),
('Losartán',     'Losartán potásico',   'Tabletas 50 mg',     12,  30, CURRENT_DATE + 300, 'Estante B1'),
('Ibuprofeno',   'Ibuprofeno',          'Tabletas 400 mg',   120,  40, CURRENT_DATE + 25,  'Estante A3'),
('Insulina',     'Insulina humana NPH', 'Vial 10 ml',         30,  10, CURRENT_DATE + 20,  'Nevera 1'),
('Omeprazol',    'Omeprazol',           'Cápsulas 20 mg',    200,  50, CURRENT_DATE + 15,  'Estante B2'),
('Metformina',   'Metformina',          'Tabletas 850 mg',   300,  80, CURRENT_DATE + 500, 'Estante B3'),
('Salbutamol',   'Salbutamol',          'Inhalador 100 mcg',  60,  20, CURRENT_DATE + 350, 'Estante C1'),
('Diclofenaco',  'Diclofenaco sódico',  'Ampolla 75 mg',      90,  30, CURRENT_DATE + 600, 'Estante C2'),
('Loratadina',   'Loratadina',          'Tabletas 10 mg',    150,  40, CURRENT_DATE + 250, 'Estante C3'),
('Enalapril',    'Enalapril',           'Tabletas 20 mg',     45,  30, CURRENT_DATE + 180, 'Estante D1'),
('Suero Oral',   'Sales de rehidratación', 'Sobre',          100,  60, CURRENT_DATE + 45,  'Estante D2');

-- (medicamento, tipo, cantidad, día relativo al inicio del mes, usuario)
-- Mes actual: 5 entradas y 7 salidas. Acetaminofén tiene 3 movimientos (el mayor).
-- Mes anterior (día negativo): 2 entradas y 1 salida, que NO deben contarse en "este mes".
INSERT INTO movimientos (medicamento_id, tipo, cantidad, fecha, usuario_id)
SELECT v.med, v.tipo, v.cant,
       LEAST((date_trunc('month', CURRENT_DATE)::date + v.dia) + time '09:00', date_trunc('minute', localtimestamp)), v.usr
FROM (VALUES
    (1, 'ENTRADA', 100,  2, 3),
    (1, 'SALIDA',   85,  5, 2),
    (1, 'SALIDA',   30,  9, 2),
    (2, 'ENTRADA',  50,  3, 3),
    (2, 'SALIDA',   42,  8, 2),
    (3, 'SALIDA',   18,  6, 2),
    (4, 'ENTRADA',  60,  4, 3),
    (4, 'SALIDA',   20, 10, 2),
    (5, 'ENTRADA',  20,  7, 3),
    (5, 'SALIDA',    5, 11, 2),
    (6, 'SALIDA',   40, 12, 2),
    (7, 'ENTRADA', 100, 13, 3),
    (1, 'ENTRADA', 200, -5, 3),
    (1, 'SALIDA',   60, -3, 2),
    (5, 'ENTRADA',  15, -10, 3)
) AS v(med, tipo, cant, dia, usr);
