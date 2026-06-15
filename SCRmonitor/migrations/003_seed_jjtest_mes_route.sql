-- Seed a default JJtest MES route template for the sample maintenance flow UI.

INSERT OR IGNORE INTO mes_route_templates (
    project_code, route_name, version, status, description, created_at, updated_at
)
VALUES (
    'JJtest',
    'JJtest standard wafer route',
    'v1.0',
    'active',
    'Default route: issue material, CPW, UBM, JJs.',
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
);

INSERT OR IGNORE INTO mes_route_layers (
    route_template_id, layer_name, layer_type, sequence_no, default_status, note, created_at, updated_at
)
SELECT id, '发料', 'issue', 1, 'pending', '', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
FROM mes_route_templates
WHERE project_code = 'JJtest' AND version = 'v1.0';

INSERT OR IGNORE INTO mes_route_layers (
    route_template_id, layer_name, layer_type, sequence_no, default_status, note, created_at, updated_at
)
SELECT id, 'CPW', 'process_layer', 2, 'pending', '', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
FROM mes_route_templates
WHERE project_code = 'JJtest' AND version = 'v1.0';

INSERT OR IGNORE INTO mes_route_layers (
    route_template_id, layer_name, layer_type, sequence_no, default_status, note, created_at, updated_at
)
SELECT id, 'UBM', 'process_layer', 3, 'pending', '', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
FROM mes_route_templates
WHERE project_code = 'JJtest' AND version = 'v1.0';

INSERT OR IGNORE INTO mes_route_layers (
    route_template_id, layer_name, layer_type, sequence_no, default_status, note, created_at, updated_at
)
SELECT id, 'JJs', 'process_layer', 4, 'pending', '', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
FROM mes_route_templates
WHERE project_code = 'JJtest' AND version = 'v1.0';

INSERT OR IGNORE INTO mes_route_steps (
    route_layer_id, step_name, step_type, sequence_no, is_required, default_instruction, default_status, created_at, updated_at
)
SELECT id, '发料', 'issue', 1, 1, '', 'pending', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
FROM mes_route_layers
WHERE route_template_id = (
    SELECT id FROM mes_route_templates WHERE project_code = 'JJtest' AND version = 'v1.0'
)
AND layer_name = '发料';

INSERT OR IGNORE INTO mes_route_steps (
    route_layer_id, step_name, step_type, sequence_no, is_required, default_instruction, default_status, created_at, updated_at
)
SELECT id, '光刻', 'lithography', 1, 1, '仅涂胶', 'pending', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
FROM mes_route_layers
WHERE route_template_id = (
    SELECT id FROM mes_route_templates WHERE project_code = 'JJtest' AND version = 'v1.0'
)
AND layer_name = 'CPW';

INSERT OR IGNORE INTO mes_route_steps (
    route_layer_id, step_name, step_type, sequence_no, is_required, default_instruction, default_status, created_at, updated_at
)
SELECT id, '检测', 'inspection', 2, 1, '', 'pending', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
FROM mes_route_layers
WHERE route_template_id = (
    SELECT id FROM mes_route_templates WHERE project_code = 'JJtest' AND version = 'v1.0'
)
AND layer_name = 'CPW';

INSERT OR IGNORE INTO mes_route_steps (
    route_layer_id, step_name, step_type, sequence_no, is_required, default_instruction, default_status, created_at, updated_at
)
SELECT id, '刻蚀', 'etching', 3, 1, '', 'pending', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
FROM mes_route_layers
WHERE route_template_id = (
    SELECT id FROM mes_route_templates WHERE project_code = 'JJtest' AND version = 'v1.0'
)
AND layer_name = 'CPW';

INSERT OR IGNORE INTO mes_route_steps (
    route_layer_id, step_name, step_type, sequence_no, is_required, default_instruction, default_status, created_at, updated_at
)
SELECT id, '湿法', 'wet_process', 4, 1, '', 'pending', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
FROM mes_route_layers
WHERE route_template_id = (
    SELECT id FROM mes_route_templates WHERE project_code = 'JJtest' AND version = 'v1.0'
)
AND layer_name = 'CPW';

INSERT OR IGNORE INTO mes_route_steps (
    route_layer_id, step_name, step_type, sequence_no, is_required, default_instruction, default_status, created_at, updated_at
)
SELECT id, '检测', 'inspection', 5, 1, '', 'pending', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
FROM mes_route_layers
WHERE route_template_id = (
    SELECT id FROM mes_route_templates WHERE project_code = 'JJtest' AND version = 'v1.0'
)
AND layer_name = 'CPW';

INSERT OR IGNORE INTO mes_route_steps (
    route_layer_id, step_name, step_type, sequence_no, is_required, default_instruction, default_status, created_at, updated_at
)
SELECT id, '光刻', 'lithography', 1, 1, '', 'pending', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
FROM mes_route_layers
WHERE route_template_id = (
    SELECT id FROM mes_route_templates WHERE project_code = 'JJtest' AND version = 'v1.0'
)
AND layer_name = 'UBM';

INSERT OR IGNORE INTO mes_route_steps (
    route_layer_id, step_name, step_type, sequence_no, is_required, default_instruction, default_status, created_at, updated_at
)
SELECT id, '镀膜', 'deposition', 2, 1, '', 'pending', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
FROM mes_route_layers
WHERE route_template_id = (
    SELECT id FROM mes_route_templates WHERE project_code = 'JJtest' AND version = 'v1.0'
)
AND layer_name = 'UBM';

INSERT OR IGNORE INTO mes_route_steps (
    route_layer_id, step_name, step_type, sequence_no, is_required, default_instruction, default_status, created_at, updated_at
)
SELECT id, '湿法', 'wet_process', 3, 1, '', 'pending', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
FROM mes_route_layers
WHERE route_template_id = (
    SELECT id FROM mes_route_templates WHERE project_code = 'JJtest' AND version = 'v1.0'
)
AND layer_name = 'UBM';

INSERT OR IGNORE INTO mes_route_steps (
    route_layer_id, step_name, step_type, sequence_no, is_required, default_instruction, default_status, created_at, updated_at
)
SELECT id, '检测', 'inspection', 4, 1, '', 'pending', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
FROM mes_route_layers
WHERE route_template_id = (
    SELECT id FROM mes_route_templates WHERE project_code = 'JJtest' AND version = 'v1.0'
)
AND layer_name = 'UBM';

INSERT OR IGNORE INTO mes_route_steps (
    route_layer_id, step_name, step_type, sequence_no, is_required, default_instruction, default_status, created_at, updated_at
)
SELECT id, '光刻', 'lithography', 1, 1, '', 'pending', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
FROM mes_route_layers
WHERE route_template_id = (
    SELECT id FROM mes_route_templates WHERE project_code = 'JJtest' AND version = 'v1.0'
)
AND layer_name = 'JJs';

INSERT OR IGNORE INTO mes_route_steps (
    route_layer_id, step_name, step_type, sequence_no, is_required, default_instruction, default_status, created_at, updated_at
)
SELECT id, '刻蚀', 'etching', 2, 1, '', 'pending', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
FROM mes_route_layers
WHERE route_template_id = (
    SELECT id FROM mes_route_templates WHERE project_code = 'JJtest' AND version = 'v1.0'
)
AND layer_name = 'JJs';

INSERT OR IGNORE INTO mes_route_steps (
    route_layer_id, step_name, step_type, sequence_no, is_required, default_instruction, default_status, created_at, updated_at
)
SELECT id, '氧化', 'oxidation', 3, 1, '', 'pending', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
FROM mes_route_layers
WHERE route_template_id = (
    SELECT id FROM mes_route_templates WHERE project_code = 'JJtest' AND version = 'v1.0'
)
AND layer_name = 'JJs';

INSERT OR IGNORE INTO mes_route_steps (
    route_layer_id, step_name, step_type, sequence_no, is_required, default_instruction, default_status, created_at, updated_at
)
SELECT id, '检测', 'inspection', 4, 1, '', 'pending', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
FROM mes_route_layers
WHERE route_template_id = (
    SELECT id FROM mes_route_templates WHERE project_code = 'JJtest' AND version = 'v1.0'
)
AND layer_name = 'JJs';
