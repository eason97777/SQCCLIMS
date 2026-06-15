-- MES route template and sample route instance foundation.

CREATE TABLE IF NOT EXISTS mes_route_templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_code TEXT NOT NULL,
    route_name TEXT NOT NULL,
    version TEXT NOT NULL DEFAULT 'v1.0',
    status TEXT NOT NULL DEFAULT 'active',
    description TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (project_code, version)
);

CREATE TABLE IF NOT EXISTS mes_route_layers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    route_template_id INTEGER NOT NULL,
    layer_name TEXT NOT NULL,
    layer_type TEXT NOT NULL DEFAULT 'process_layer',
    sequence_no INTEGER NOT NULL,
    default_status TEXT NOT NULL DEFAULT 'pending',
    note TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (route_template_id) REFERENCES mes_route_templates(id) ON DELETE CASCADE,
    UNIQUE (route_template_id, sequence_no),
    UNIQUE (route_template_id, layer_name)
);

CREATE TABLE IF NOT EXISTS mes_route_steps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    route_layer_id INTEGER NOT NULL,
    step_name TEXT NOT NULL,
    step_type TEXT NOT NULL DEFAULT 'process_step',
    sequence_no INTEGER NOT NULL,
    is_required INTEGER NOT NULL DEFAULT 1,
    default_instruction TEXT NOT NULL DEFAULT '',
    default_status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (route_layer_id) REFERENCES mes_route_layers(id) ON DELETE CASCADE,
    UNIQUE (route_layer_id, sequence_no)
);

CREATE TABLE IF NOT EXISTS mes_sample_routes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sample_id INTEGER NOT NULL,
    route_template_id INTEGER NOT NULL,
    route_version TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'not_started',
    current_sample_step_id INTEGER,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (sample_id) REFERENCES samples(id) ON DELETE CASCADE,
    FOREIGN KEY (route_template_id) REFERENCES mes_route_templates(id) ON DELETE RESTRICT,
    FOREIGN KEY (current_sample_step_id) REFERENCES mes_sample_steps(id) ON DELETE SET NULL,
    UNIQUE (sample_id, route_template_id, route_version)
);

CREATE TABLE IF NOT EXISTS mes_sample_steps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sample_route_id INTEGER NOT NULL,
    sample_id INTEGER NOT NULL,
    route_layer_id INTEGER,
    route_step_id INTEGER,
    layer_name TEXT NOT NULL,
    step_name TEXT NOT NULL,
    layer_sequence_no INTEGER NOT NULL,
    step_sequence_no INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    instruction TEXT NOT NULL DEFAULT '',
    operator TEXT NOT NULL DEFAULT '',
    started_at TEXT,
    completed_at TEXT,
    note TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (sample_route_id) REFERENCES mes_sample_routes(id) ON DELETE CASCADE,
    FOREIGN KEY (sample_id) REFERENCES samples(id) ON DELETE CASCADE,
    FOREIGN KEY (route_layer_id) REFERENCES mes_route_layers(id) ON DELETE SET NULL,
    FOREIGN KEY (route_step_id) REFERENCES mes_route_steps(id) ON DELETE SET NULL,
    UNIQUE (sample_route_id, layer_sequence_no, step_sequence_no)
);

CREATE TABLE IF NOT EXISTS mes_step_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sample_route_id INTEGER NOT NULL,
    sample_step_id INTEGER,
    sample_id INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    from_status TEXT NOT NULL DEFAULT '',
    to_status TEXT NOT NULL DEFAULT '',
    operator TEXT NOT NULL DEFAULT '',
    note TEXT NOT NULL DEFAULT '',
    event_at TEXT NOT NULL,
    FOREIGN KEY (sample_route_id) REFERENCES mes_sample_routes(id) ON DELETE CASCADE,
    FOREIGN KEY (sample_step_id) REFERENCES mes_sample_steps(id) ON DELETE SET NULL,
    FOREIGN KEY (sample_id) REFERENCES samples(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_mes_route_templates_project
    ON mes_route_templates(project_code, status);

CREATE INDEX IF NOT EXISTS idx_mes_route_layers_template
    ON mes_route_layers(route_template_id, sequence_no);

CREATE INDEX IF NOT EXISTS idx_mes_route_steps_layer
    ON mes_route_steps(route_layer_id, sequence_no);

CREATE INDEX IF NOT EXISTS idx_mes_sample_routes_sample
    ON mes_sample_routes(sample_id, status);

CREATE INDEX IF NOT EXISTS idx_mes_sample_routes_template
    ON mes_sample_routes(route_template_id);

CREATE INDEX IF NOT EXISTS idx_mes_sample_steps_route
    ON mes_sample_steps(sample_route_id, layer_sequence_no, step_sequence_no);

CREATE INDEX IF NOT EXISTS idx_mes_sample_steps_status
    ON mes_sample_steps(status, layer_name, step_name);

CREATE INDEX IF NOT EXISTS idx_mes_sample_steps_sample
    ON mes_sample_steps(sample_id, status);

CREATE INDEX IF NOT EXISTS idx_mes_step_events_route
    ON mes_step_events(sample_route_id, event_at);

CREATE INDEX IF NOT EXISTS idx_mes_step_events_sample
    ON mes_step_events(sample_id, event_at);
