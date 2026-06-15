export type MesRouteStep = {
  id: number;
  route_layer_id: number;
  step_name: string;
  step_type: string;
  sequence_no: number;
  is_required: number;
  default_instruction: string;
  default_status: string;
  created_at: string;
  updated_at: string;
};

export type MesRouteLayer = {
  id: number;
  route_template_id: number;
  layer_name: string;
  layer_type: string;
  sequence_no: number;
  default_status: string;
  note: string;
  created_at: string;
  updated_at: string;
  steps: MesRouteStep[];
};

export type MesRouteTemplate = {
  id: number;
  project_code: string;
  route_name: string;
  version: string;
  status: string;
  description: string;
  created_at: string;
  updated_at: string;
  layers: MesRouteLayer[];
};

export type MesSampleStep = {
  id: number;
  sample_route_id: number;
  sample_id: number;
  route_layer_id: number | null;
  route_step_id: number | null;
  layer_name: string;
  step_name: string;
  layer_sequence_no: number;
  step_sequence_no: number;
  status: string;
  instruction: string;
  operator: string;
  started_at: string | null;
  completed_at: string | null;
  note: string;
  created_at: string;
  updated_at: string;
};

export type MesSampleRoute = {
  id: number;
  sample_id: number;
  route_template_id: number;
  route_version: string;
  status: string;
  current_sample_step_id: number | null;
  created_at: string;
  updated_at: string;
  sample_uid: string;
  sample_display_code: string;
  sample_code: string;
  name: string;
  category: string;
  batch: string;
  project_code: string;
  route_name: string;
  template_version: string;
  steps: MesSampleStep[];
};

export type CreateMesSampleRoutePayload = {
  sample_id: number;
  project_code?: string;
  route_template_id?: number;
  version?: string;
};

export type CreateMesRouteTemplatePayload = {
  project_code: string;
  route_name?: string;
  version?: string;
  status?: string;
  description?: string;
};

export type CreateMesRouteLayerPayload = {
  layer_name: string;
  layer_type?: string;
  sequence_no?: number;
  note?: string;
};

export type CreateMesRouteStepPayload = {
  step_name: string;
  step_type?: string;
  sequence_no?: number;
  is_required?: number;
  default_instruction?: string;
};

export type AdvanceMesSampleRoutePayload = {
  action: "skip";
  operator?: string;
  note?: string;
};

export type UpdateMesRouteStepPayload = {
  default_instruction: string;
};
