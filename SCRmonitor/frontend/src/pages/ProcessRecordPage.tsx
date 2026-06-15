import { useEffect, useMemo, useRef, useState } from "react";
import {
  getProcessFieldSuggestions,
  getProcessLayerSuggestions,
  getProcessSampleSuggestions,
  lookupProcessSample,
  saveProcessRecord,
} from "../api/processRecordsApi";
import type { Sample } from "../types/sample";
import type { ProcessRecord, ProcessRecordStatus, ProcessStage } from "../types/processRecord";
import { PROCESS_STAGES } from "../utils/processStages";

const processTabs = PROCESS_STAGES;

type WaferForm = {
  substrate_type: string;
  resistance_type: string;
  wafer_thickness: string;
};

type WaferFieldKey = keyof WaferForm;

type ExposureTool = "" | "MLA150" | "DWL66" | "MA8" | "DUV" | "EBL";

type LithographyForm = {
  layer: string;
  coatTool: string;
  photoresist: string;
  resistThickness: string;
  coatRemark: string;
  exposureTool: ExposureTool;
  mask: string;
  power: string;
  focus: string;
  dose: string;
  intensity: string;
  filter: string;
  gap: string;
  l7Dose: string;
  l12Dose: string;
  l14Dose: string;
  l16Dose: string;
  beamCurrent: string;
  exposureRemark: string;
  developTool: string;
  developerType: string;
  developTime: string;
  developRemark: string;
  skippedDevelop: boolean;
};

type LithographySectionStatus = "done" | "editing" | "pending" | "skipped";

type LithographySectionState = {
  coat: LithographySectionStatus;
  exposure: LithographySectionStatus;
  develop: LithographySectionStatus;
};

type DetectionPointKey =
  | "point1"
  | "point2"
  | "point3"
  | "point4"
  | "point5"
  | "point6"
  | "point7"
  | "point8"
  | "point9";

type DetectionForm = {
  layer: string;
  tool: string;
  project: string;
  unit: string;
  points: Record<DetectionPointKey, string>;
  remark: string;
};

type CoatingForm = {
  layer: string;
  machineTemplate: string;
  inTime: string;
  inOperator: string;
  programName: string;
  outTime: string;
  outOperator: string;
  crucibleMaterial: string;
  crystalFrequency: string;
  rotationSpeed: string;
  transferVacuum: string;
  crystalMonitor: string;
  ionSource: string;
  ionSourceArPcPressure: string;
  bombardCoolingTime: string;
  processVacuum: string;
  parameterValues: Record<string, string>;
};

type CoatingScalarField = Exclude<keyof CoatingForm, "parameterValues">;

type CoatingFieldLocks = Partial<Record<CoatingScalarField, boolean>> & {
  parameterValues?: Record<string, boolean>;
};

type EtchingForm = {
  layer: string;
  machineTemplate: string;
  inTime: string;
  operator: string;
  programName: string;
  outTime: string;
  machineStatus: string;
  remark: string;
  upperPower: string;
  upperReflectPower: string;
  lowerPower: string;
  lowerReflectPower: string;
  gasFlow: string;
  chamberPressure: string;
  backsideHelium: string;
  dcBiasMax: string;
  lowerTemperature: string;
  chamberTemperature: string;
  etchingTime: string;
  etchingLoop: string;
  beamGridVoltage: string;
  beamGridCurrent: string;
  acceleratorGridVoltage: string;
  neutralizerOutputCurrent: string;
  stageAngle: string;
};

type EtchingFieldLocks = Partial<Record<keyof EtchingForm, boolean>>;

type WetProcessName = "自动去胶" | "镀膜前清洗" | "RCA清洗" | "干法剥离" | "研磨后清洗";

type WetProcessForm = {
  layer: string;
  processTemplate: WetProcessName | "";
  equipmentName: string;
  operator: string;
  inTime: string;
  outTime: string;
  parameterValues: Record<string, string>;
};

type WetProcessScalarField = Exclude<keyof WetProcessForm, "parameterValues">;

type WetProcessFieldLocks = Partial<Record<WetProcessScalarField, boolean>> & {
  parameterValues?: Record<string, boolean>;
};

type TextFieldProps = {
  label: string;
  value: string;
  disabled?: boolean;
  placeholder?: string;
  onChange?: (value: string) => void;
};

const defaultWaferForm: WaferForm = {
  substrate_type: "",
  resistance_type: "",
  wafer_thickness: "",
};

const defaultLithographyForm: LithographyForm = {
  layer: "",
  coatTool: "",
  photoresist: "",
  resistThickness: "",
  coatRemark: "",
  exposureTool: "",
  mask: "",
  power: "",
  focus: "",
  dose: "",
  intensity: "",
  filter: "",
  gap: "",
  l7Dose: "",
  l12Dose: "",
  l14Dose: "",
  l16Dose: "",
  beamCurrent: "",
  exposureRemark: "",
  developTool: "",
  developerType: "",
  developTime: "",
  developRemark: "",
  skippedDevelop: false,
};

const defaultLithographySectionState: LithographySectionState = {
  coat: "editing",
  exposure: "pending",
  develop: "pending",
};

const detectionPointKeys: DetectionPointKey[] = [
  "point1",
  "point2",
  "point3",
  "point4",
  "point5",
  "point6",
  "point7",
  "point8",
  "point9",
];

const detectionMachineTemplates: Array<{
  name: string;
  projectOptions: string[];
  pointLabels: string[];
  calculationRule: string;
}> = [
  {
    name: "台阶仪",
    projectOptions: ["显影胶厚", "镀膜膜厚", "刻蚀深度"],
    pointLabels: detectionPointKeys.map((_, index) => `测试点${index + 1}`),
    calculationRule: "填写几个测试点就计算几个",
  },
];

const defaultDetectionForm: DetectionForm = {
  layer: "",
  tool: "",
  project: "",
  unit: "",
  points: {
    point1: "",
    point2: "",
    point3: "",
    point4: "",
    point5: "",
    point6: "",
    point7: "",
    point8: "",
    point9: "",
  },
  remark: "",
};

const defaultCoatingForm: CoatingForm = {
  layer: "",
  machineTemplate: "",
  inTime: "",
  inOperator: "",
  programName: "",
  outTime: "",
  outOperator: "",
  crucibleMaterial: "",
  crystalFrequency: "",
  rotationSpeed: "",
  transferVacuum: "",
  crystalMonitor: "",
  ionSource: "",
  ionSourceArPcPressure: "",
  bombardCoolingTime: "",
  processVacuum: "",
  parameterValues: {},
};

const coatingCommonParameterLabels = new Set([
  "进样时间",
  "进样人",
  "操作人",
  "进样时间/操作人",
  "程序名称",
  "镀膜程序",
  "出样时间",
  "出样人",
  "出样时间/出样人",
]);

const coatingMachineTemplates: Array<{
  name: string;
  fields: Array<{ key: string; label: string; unit?: string }>;
}> = [
  {
    name: "加热Sputter",
    fields: [
      { key: "coatingThickness", label: "镀膜厚度", unit: "nm" },
      { key: "sampleRotationSpeed", label: "样品台旋转速度", unit: "rpm" },
      { key: "sputterPressure", label: "溅射压力", unit: "mTorr" },
      { key: "arFlow", label: "Ar流量", unit: "sccm" },
      { key: "baseVacuum", label: "本底真空", unit: "Torr" },
      { key: "vacuumBeforeNb", label: "镀Nb前真空度", unit: "Torr" },
      { key: "vacuumBeforeTa", label: "镀Ta前真空度", unit: "Torr" },
      { key: "current", label: "电流", unit: "A" },
      { key: "voltage", label: "电压", unit: "V" },
      { key: "power", label: "功率", unit: "W" },
      { key: "coolingTemperature", label: "冷却温度", unit: "℃" },
      { key: "coolingTime", label: "冷却时间", unit: "s" },
    ],
  },
  {
    name: "ProLine PVD200",
    fields: [
      { key: "transferVacuum", label: "传样真空度", unit: "Torr" },
      { key: "crystalMonitor", label: "晶振（膜厚晶振/速率晶振）", unit: "MHz" },
      { key: "sampleStageSpeed", label: "样品台转速", unit: "rpm" },
      { key: "ionSource", label: "离子源（程序/时间）", unit: "min" },
      { key: "ionSourceArPcPressure", label: "离子源Ar流量和PC压强（前、中、后）", unit: "sccm/Torr" },
      { key: "bombardCoolingTime", label: "轰击后冷却时间", unit: "min" },
      { key: "processVacuum", label: "程序运行时真空度", unit: "Torr" },
      { key: "coatingVoltage", label: "镀膜电压", unit: "kV" },
      { key: "crucibleMaterial", label: "坩埚/材料" },
      { key: "tooling", label: "Tooling" },
      { key: "coatingThickness", label: "镀膜厚度", unit: "nm" },
      { key: "depositionRate", label: "沉积速率", unit: "A/s" },
      { key: "depositionCurrent", label: "沉积电流", unit: "mA" },
      { key: "postCoatingCoolingTime", label: "镀膜后冷却时间", unit: "min" },
    ],
  },
  {
    name: "镀结机",
    fields: [
      { key: "transferVacuum", label: "传样时真空度", unit: "Torr" },
      { key: "crystalMonitor", label: "晶振(名称/频率)", unit: "MHz" },
      { key: "crucibleMaterial", label: "坩埚/材料" },
      { key: "sampleStageSpeed", label: "样品台转速", unit: "rpm" },
      { key: "ionBombardment", label: "离子源轰击", unit: "min" },
      { key: "coatingVoltage", label: "镀膜电压", unit: "kV" },
      { key: "firstAlFilm", label: "第一层铝膜(膜厚、倾斜角度)" },
      { key: "junctionOxidation", label: "结氧化条件", unit: "Torr" },
      { key: "secondAlFilm", label: "第二层铝膜(膜厚、倾斜角度)" },
      { key: "totalThickness", label: "累积厚度" },
      { key: "depositionRate", label: "沉积速率", unit: "A/s" },
      { key: "depositionCurrent", label: "沉积电流", unit: "mA" },
    ],
  },
  {
    name: "Integrity",
    fields: [
      { key: "coolingTemperature", label: "冷却温度", unit: "℃" },
      { key: "sampleStageSpeed", label: "样品台转速", unit: "rpm" },
      { key: "coatingThickness", label: "镀膜厚度", unit: "KA" },
      { key: "crystalMonitor", label: "晶振(名称/频率)", unit: "MHz" },
      { key: "baseVacuum", label: "本底真空", unit: "Torr" },
      { key: "coatingVacuum", label: "镀膜真空", unit: "Torr" },
      { key: "coatingCurrent", label: "镀膜电流", unit: "A" },
      { key: "coatingRate", label: "镀膜速率", unit: "A/s" },
      { key: "postCoatingCoolingTime", label: "镀膜后冷却时间", unit: "h" },
      { key: "loadingMaterial", label: "加料", unit: "g" },
    ],
  },
  {
    name: "SENTECH",
    fields: [
      { key: "depositionTemperature", label: "沉积温度", unit: "℃" },
      { key: "sih4Flow", label: "SiH4流量", unit: "sccm" },
      { key: "n2oFlow", label: "N2O流量", unit: "sccm" },
      { key: "n2Flow", label: "N2流量", unit: "sccm" },
      { key: "actualPressure", label: "实际气压", unit: "mTorr" },
      { key: "icpPower", label: "ICP功率", unit: "W" },
      { key: "reflectedPower", label: "Reflected功率", unit: "W" },
      { key: "wetCleanAccumulatedThickness", label: "湿法clean后累计镀膜厚度", unit: "um" },
    ],
  },
  {
    name: "ICPECVD",
    fields: [
      { key: "usePressureRing", label: "是否使用压环" },
      { key: "transferStatus", label: "传样状态" },
      { key: "depositionTemperature", label: "沉积温度", unit: "℃" },
      { key: "sih4Flow", label: "SiH4流量", unit: "sccm" },
      { key: "o2Flow", label: "O2流量", unit: "sccm" },
      { key: "arFlow", label: "Ar流量", unit: "sccm" },
      { key: "actualPressure", label: "实际气压", unit: "Pa" },
      { key: "icpPower", label: "ICP功率", unit: "W" },
      { key: "reflectedPower", label: "Reflected功率", unit: "W" },
      { key: "plasmaIgnitionStatus", label: "启辉状态" },
      { key: "growthDuration", label: "生长时长" },
      { key: "accumulatedThickness", label: "累计镀膜厚度", unit: "um" },
      { key: "loadLockCoolingTime", label: "镀膜后在LL的冷却时间" },
    ],
  },
  {
    name: "PEALD",
    fields: [
      { key: "samplePosition", label: "样品位置" },
      { key: "sourceBottleNumber", label: "源瓶编号" },
      { key: "sourceBottlePressure", label: "源瓶压力", unit: "Torr" },
      { key: "cycleCount", label: "循环次数" },
      { key: "depositionTemperature", label: "沉积温度", unit: "℃" },
      { key: "power", label: "功率", unit: "W" },
      { key: "nh3Flow", label: "NH3流量", unit: "sccm" },
      { key: "arFlow", label: "Ar流量", unit: "sccm" },
      { key: "sourceBottleOpenTime", label: "源瓶开启时间", unit: "ms" },
      { key: "processPressure", label: "工艺气压", unit: "Torr" },
      { key: "accumulatedWaferCount", label: "累计片数" },
      { key: "postCoatingCoolingTime", label: "镀膜后冷却时间", unit: "h" },
      { key: "resistivity", label: "电阻率", unit: "μΩ·cm@100nm TiN" },
    ],
  },
  {
    name: "JN 镀导电铝",
    fields: [
      { key: "transferVacuum", label: "传样时真空度", unit: "Torr" },
      { key: "crystalMonitor", label: "晶振(名称/频率)", unit: "MHz" },
      { key: "crucibleMaterial", label: "坩埚/材料" },
      { key: "sampleRotationSpeed", label: "样品台旋转速度", unit: "rpm" },
      { key: "coatingVoltage", label: "镀膜电压", unit: "kV" },
      { key: "coatingThickness", label: "镀膜厚度", unit: "nm" },
      { key: "totalThickness", label: "累积厚度" },
      { key: "depositionRate", label: "沉积速率", unit: "A/s" },
      { key: "depositionCurrent", label: "沉积电流", unit: "mA" },
    ],
  },
  {
    name: "700SL4",
    fields: [
      { key: "transferVacuum", label: "传样时真空度", unit: "Torr" },
      { key: "crystalMonitor", label: "晶振(名称/频率)", unit: "MHz" },
      { key: "crucibleMaterial", label: "坩埚/材料" },
      { key: "sampleRotationSpeed", label: "样品台旋转速度", unit: "rpm" },
      { key: "ionBombardment", label: "离子源轰击", unit: "min" },
      { key: "coatingVoltage", label: "镀膜电压", unit: "kV" },
      { key: "coatingThickness", label: "镀膜厚度", unit: "nm" },
      { key: "totalThickness", label: "累积厚度" },
      { key: "depositionRate", label: "沉积速率", unit: "A/s" },
      { key: "depositionCurrent", label: "沉积电流", unit: "mA" },
    ],
  },
  {
    name: "多腔溅射",
    fields: [
      { key: "cleanTime", label: "Clean 时间", unit: "min" },
      { key: "reverseSputterPressure", label: "反溅射压力", unit: "mTorr" },
      { key: "baseVacuumClean", label: "本底真空", unit: "Torr" },
      { key: "loadingPower", label: "加载功率", unit: "W" },
      { key: "arFlow", label: "Ar流量", unit: "sccm" },
      { key: "biasVoltage", label: "偏压", unit: "V" },
      { key: "reverseSputterFinishTime", label: "反溅射完成时间" },
      { key: "coatingThickness", label: "镀膜厚度", unit: "nm" },
      { key: "sputterPressure", label: "溅射压力", unit: "mTorr" },
      { key: "baseVacuumCoating", label: "本底真空", unit: "Torr" },
      { key: "current", label: "电流", unit: "A" },
      { key: "voltage", label: "电压", unit: "V" },
      { key: "power", label: "功率", unit: "W" },
      { key: "sampleRotationSpeed", label: "样品旋转转速", unit: "rpm/min" },
    ],
  },
].map((template) => ({
  ...template,
  fields: template.fields.filter((field) => !coatingCommonParameterLabels.has(field.label)),
}));

const defaultEtchingForm: EtchingForm = {
  layer: "",
  machineTemplate: "",
  inTime: "",
  operator: "",
  programName: "",
  outTime: "",
  machineStatus: "",
  remark: "",
  upperPower: "",
  upperReflectPower: "",
  lowerPower: "",
  lowerReflectPower: "",
  gasFlow: "",
  chamberPressure: "",
  backsideHelium: "",
  dcBiasMax: "",
  lowerTemperature: "",
  chamberTemperature: "",
  etchingTime: "",
  etchingLoop: "",
  beamGridVoltage: "",
  beamGridCurrent: "",
  acceleratorGridVoltage: "",
  neutralizerOutputCurrent: "",
  stageAngle: "",
};

const defaultWetProcessForm: WetProcessForm = {
  layer: "",
  processTemplate: "自动去胶",
  equipmentName: "",
  operator: "",
  inTime: "",
  outTime: "",
  parameterValues: {},
};

const wetProcessTemplates: Array<{
  name: WetProcessName;
  fields: Array<{ key: string; label: string; unit?: string }>;
}> = [
  {
    name: "自动去胶",
    fields: [
      { key: "recipe", label: "Recipe" },
      { key: "megasonicReflectPower", label: "兆声反射功率" },
      { key: "dmsoFlow", label: "DMSO流量", unit: "mL/min" },
      { key: "dmsoTemperature", label: "DMSO温度", unit: "℃" },
    ],
  },
  {
    name: "镀膜前清洗",
    fields: [{ key: "recipe", label: "Recipe" }],
  },
  {
    name: "RCA清洗",
    fields: [{ key: "recipe", label: "Recipe" }],
  },
  {
    name: "干法剥离",
    fields: [
      { key: "vacuumConfirmation", label: "真空确认" },
      { key: "filmType", label: "膜类型" },
      { key: "bubbleObservation", label: "气泡观察" },
    ],
  },
  {
    name: "研磨后清洗",
    fields: [{ key: "recipe", label: "Recipe" }],
  },
];

const etchingMachineTemplates: Array<{
  name: string;
  fields: Array<{ field: keyof EtchingForm; label: string; unit?: string }>;
}> = [
  {
    name: "Synapse",
    fields: [
      { field: "upperPower", label: "上电极功率", unit: "W" },
      { field: "upperReflectPower", label: "上电极反射功率", unit: "W" },
      { field: "lowerPower", label: "下电极功率", unit: "W" },
      { field: "lowerReflectPower", label: "下电极反射功率", unit: "W" },
      { field: "gasFlow", label: "气体流量", unit: "sccm" },
      { field: "chamberPressure", label: "腔室压力", unit: "mTorr" },
      { field: "backsideHelium", label: "背氦(压力/流量)", unit: "Torr/sccm" },
      { field: "lowerTemperature", label: "下电极温度", unit: "℃" },
      { field: "chamberTemperature", label: "腔室温度", unit: "℃" },
      { field: "etchingTime", label: "刻蚀时间", unit: "S" },
    ],
  },
  {
    name: "Rapier",
    fields: [
      { field: "upperPower", label: "上电极功率（E2步）", unit: "W" },
      { field: "upperReflectPower", label: "上电极反射功率（E2步）", unit: "W" },
      { field: "lowerPower", label: "下电极功率（E2步）", unit: "W" },
      { field: "lowerReflectPower", label: "下电极反射功率（E2步）", unit: "W" },
      { field: "gasFlow", label: "气体流量（E2步）", unit: "sccm" },
      { field: "chamberPressure", label: "腔室压力（E2步）", unit: "mTorr" },
      { field: "backsideHelium", label: "背氦(压力/流量)", unit: "mTorr/sccm" },
      { field: "lowerTemperature", label: "下电极温度", unit: "℃" },
      { field: "chamberTemperature", label: "腔室温度", unit: "℃" },
      { field: "etchingLoop", label: "刻蚀loop", unit: "loop" },
    ],
  },
  {
    name: "GSE C200",
    fields: [
      { field: "upperPower", label: "上电极功率", unit: "W" },
      { field: "upperReflectPower", label: "上电极反射功率", unit: "W" },
      { field: "lowerPower", label: "下电极功率", unit: "W" },
      { field: "lowerReflectPower", label: "下电极反射功率", unit: "W" },
      { field: "gasFlow", label: "气体流量", unit: "sccm" },
      { field: "chamberPressure", label: "腔室压力", unit: "mTorr" },
      { field: "backsideHelium", label: "背氦(压力/流量)", unit: "Torr/sccm" },
      { field: "lowerTemperature", label: "下电极温度", unit: "℃" },
      { field: "chamberTemperature", label: "腔室温度", unit: "℃" },
      { field: "etchingTime", label: "刻蚀时间", unit: "S" },
    ],
  },
  {
    name: "PP100-28",
    fields: [
      { field: "upperPower", label: "上电极功率", unit: "W" },
      { field: "upperReflectPower", label: "上电极反射功率", unit: "W" },
      { field: "lowerPower", label: "下电极功率", unit: "W" },
      { field: "lowerReflectPower", label: "下电极反射功率", unit: "W" },
      { field: "gasFlow", label: "气体流量", unit: "sccm" },
      { field: "chamberPressure", label: "腔室压力", unit: "mTorr" },
      { field: "backsideHelium", label: "背氦(压力/流量)", unit: "Torr/sccm" },
      { field: "dcBiasMax", label: "DC Bias（max）", unit: "V" },
      { field: "lowerTemperature", label: "下电极温度", unit: "℃" },
      { field: "etchingTime", label: "刻蚀时间+过刻时间", unit: "S" },
    ],
  },
  {
    name: "PP100-25",
    fields: [
      { field: "upperPower", label: "上电极功率", unit: "W" },
      { field: "upperReflectPower", label: "上电极反射功率", unit: "W" },
      { field: "lowerPower", label: "下电极功率", unit: "W" },
      { field: "lowerReflectPower", label: "下电极反射功率", unit: "W" },
      { field: "gasFlow", label: "气体流量", unit: "sccm" },
      { field: "chamberPressure", label: "腔室压力", unit: "mTorr" },
      { field: "chamberTemperature", label: "腔室温度", unit: "℃" },
      { field: "backsideHelium", label: "背氦(压力/流量)", unit: "Torr/sccm" },
      { field: "dcBiasMax", label: "DC Bias（max）", unit: "V" },
      { field: "lowerTemperature", label: "下电极温度", unit: "℃" },
      { field: "etchingTime", label: "刻蚀时间+过刻时间", unit: "S" },
    ],
  },
  {
    name: "离子束刻蚀（300）",
    fields: [
      { field: "beamGridVoltage", label: "Beam栅网电压", unit: "V" },
      { field: "beamGridCurrent", label: "Beam栅网电流", unit: "mA" },
      { field: "acceleratorGridVoltage", label: "加速栅网电压", unit: "V" },
      { field: "neutralizerOutputCurrent", label: "中和器输出电流", unit: "mA" },
      { field: "stageAngle", label: "样品台角度", unit: "°" },
      { field: "gasFlow", label: "气体流量", unit: "sccm" },
    ],
  },
  {
    name: "打底膜（100）",
    fields: [
      { field: "lowerPower", label: "下电极功率", unit: "W" },
      { field: "lowerReflectPower", label: "下电极反射功率", unit: "W" },
      { field: "gasFlow", label: "气体流量", unit: "sccm" },
      { field: "chamberPressure", label: "腔室压力", unit: "mTorr" },
      { field: "backsideHelium", label: "背氦(压力/流量)", unit: "Torr/sccm" },
      { field: "lowerTemperature", label: "下电极温度", unit: "℃" },
      { field: "chamberTemperature", label: "腔室温度", unit: "℃" },
      { field: "etchingTime", label: "刻蚀时间", unit: "S" },
    ],
  },
];

const waferFields: Array<{
  key: WaferFieldKey;
  label: string;
  placeholder: string;
}> = [
  { key: "substrate_type", label: "衬底类型", placeholder: "" },
  { key: "resistance_type", label: "电阻类型", placeholder: "" },
  { key: "wafer_thickness", label: "硅片厚度", placeholder: "" },
];

const exposureToolOptions: Exclude<ExposureTool, "">[] = ["MLA150", "DWL66", "MA8", "DUV", "EBL"];

const exposureParamMap: Record<
  Exclude<ExposureTool, "">,
  Array<{ key: keyof LithographyForm; label: string; placeholder?: string }>
> = {
  MLA150: [
    { key: "power", label: "Power" },
    { key: "focus", label: "Focus" },
  ],
  DWL66: [
    { key: "dose", label: "Dose" },
    { key: "focus", label: "Focus" },
    { key: "intensity", label: "Intensity" },
    { key: "filter", label: "Filter" },
  ],
  MA8: [
    { key: "dose", label: "Dose" },
    { key: "gap", label: "Gap" },
  ],
  DUV: [
    { key: "dose", label: "Dose" },
    { key: "focus", label: "Focus" },
  ],
  EBL: [
    { key: "l7Dose", label: "L7 Dose" },
    { key: "l12Dose", label: "L12 Dose" },
    { key: "l14Dose", label: "L14 Dose" },
    { key: "l16Dose", label: "L16 Dose" },
    { key: "beamCurrent", label: "束流" },
  ],
};

function sampleLabel(sample: Sample | null) {
  if (!sample) {
    return "未关联建档样品";
  }
  return sample.sample_display_code || sample.sample_uid || sample.name;
}

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function asString(value: unknown, fallback = "") {
  return typeof value === "string" ? value : fallback;
}

function hasMeaningfulRecordDetails(record: ProcessRecord | null) {
  const details = isObject(record?.details) ? record.details : {};
  return Object.values(details).some((value) => {
    if (typeof value === "string") {
      return value.trim().length > 0;
    }
    if (typeof value === "boolean") {
      return value;
    }
    if (Array.isArray(value)) {
      return value.length > 0;
    }
    if (isObject(value)) {
      return Object.values(value).some((nestedValue) =>
        typeof nestedValue === "string" ? nestedValue.trim().length > 0 : Boolean(nestedValue),
      );
    }
    return Boolean(value);
  });
}

function normalizeRecordLayer(layer: string) {
  return layer.trim() || "默认图层";
}

function fillWaferRecord(record: ProcessRecord | null) {
  return {
    substrate_type: record?.substrate_type || "",
    resistance_type: record?.resistance_type || "",
    wafer_thickness: record?.wafer_thickness || "",
  };
}

function fillLithographyRecord(record: ProcessRecord | null) {
  const details = isObject(record?.details) ? record.details : {};
  const exposureTool = exposureToolOptions.includes(details.exposureTool as Exclude<ExposureTool, "">)
    ? (details.exposureTool as ExposureTool)
    : defaultLithographyForm.exposureTool;

  return {
    ...defaultLithographyForm,
    layer: asString(details.layer, record?.layer_name || defaultLithographyForm.layer),
    coatTool: asString(details.coatTool, defaultLithographyForm.coatTool),
    photoresist: asString(details.photoresist, defaultLithographyForm.photoresist),
    resistThickness: asString(details.resistThickness, defaultLithographyForm.resistThickness),
    coatRemark: asString(details.coatRemark, defaultLithographyForm.coatRemark),
    exposureTool,
    mask: asString(details.mask, defaultLithographyForm.mask),
    power: asString(details.power),
    focus: asString(details.focus, defaultLithographyForm.focus),
    dose: asString(details.dose, defaultLithographyForm.dose),
    intensity: asString(details.intensity, defaultLithographyForm.intensity),
    filter: asString(details.filter, defaultLithographyForm.filter),
    gap: asString(details.gap),
    l7Dose: asString(details.l7Dose),
    l12Dose: asString(details.l12Dose),
    l14Dose: asString(details.l14Dose),
    l16Dose: asString(details.l16Dose),
    beamCurrent: asString(details.beamCurrent),
    exposureRemark: asString(details.exposureRemark, defaultLithographyForm.exposureRemark),
    developTool: asString(details.developTool, defaultLithographyForm.developTool),
    developerType: asString(details.developerType, defaultLithographyForm.developerType),
    developTime: asString(details.developTime, defaultLithographyForm.developTime),
    developRemark: asString(details.developRemark, defaultLithographyForm.developRemark),
    skippedDevelop:
      typeof details.skippedDevelop === "boolean" ? details.skippedDevelop : defaultLithographyForm.skippedDevelop,
  };
}

function fillLithographySectionState(record: ProcessRecord | null, form: LithographyForm): LithographySectionState {
  const details = isObject(record?.details) ? record.details : {};
  const savedState = isObject(details.sectionState) ? details.sectionState : {};
  const hasDetails = hasMeaningfulRecordDetails(record);

  const coat = savedState.coat === "done" ? "done" : "editing";
  const exposure =
    savedState.exposure === "done"
      ? "done"
      : coat === "done" && (savedState.exposure === "editing" || hasDetails)
        ? "editing"
        : "pending";
  const develop =
    form.skippedDevelop || savedState.develop === "skipped"
      ? "skipped"
      : savedState.develop === "done"
        ? "done"
        : exposure === "done" && savedState.develop === "editing"
          ? "editing"
          : "pending";

  return { coat, exposure, develop };
}

function fillDetectionRecord(record: ProcessRecord | null) {
  const details = isObject(record?.details) ? record.details : {};
  const rawPoints = isObject(details.points) ? details.points : {};
  const points = detectionPointKeys.reduce(
    (nextPoints, key) => ({
      ...nextPoints,
      [key]: asString(rawPoints[key], defaultDetectionForm.points[key]),
    }),
    {} as Record<DetectionPointKey, string>,
  );

  return {
    ...defaultDetectionForm,
    layer: asString(details.layer, record?.layer_name || defaultDetectionForm.layer),
    tool: asString(details.tool, defaultDetectionForm.tool),
    project: asString(details.project, defaultDetectionForm.project),
    unit: asString(details.unit, defaultDetectionForm.unit),
    points,
    remark: asString(details.remark, defaultDetectionForm.remark),
  };
}

function fillDetectionLocked(record: ProcessRecord | null) {
  const details = isObject(record?.details) ? record.details : {};
  return typeof details.locked === "boolean" ? details.locked : hasMeaningfulRecordDetails(record);
}

function fillCoatingRecord(record: ProcessRecord | null) {
  const details = isObject(record?.details) ? record.details : {};
  const rawParameterValues = isObject(details.parameterValues) ? details.parameterValues : {};
  const parameterValues: Record<string, string> = {};
  Object.entries(rawParameterValues).forEach(([key, value]) => {
    parameterValues[key] = asString(value);
  });

  const legacyParameterMap: Array<[CoatingScalarField, string]> = [
    ["transferVacuum", "transferVacuum"],
    ["crystalMonitor", "crystalMonitor"],
    ["ionSource", "ionSource"],
    ["ionSourceArPcPressure", "ionSourceArPcPressure"],
    ["bombardCoolingTime", "bombardCoolingTime"],
    ["processVacuum", "processVacuum"],
    ["crucibleMaterial", "crucibleMaterial"],
    ["crystalFrequency", "crystalMonitor"],
    ["rotationSpeed", "sampleStageSpeed"],
  ];
  legacyParameterMap.forEach(([legacyKey, parameterKey]) => {
    const value = asString(details[legacyKey]);
    if (value && !parameterValues[parameterKey]) {
      parameterValues[parameterKey] = value;
    }
  });

  return {
    ...defaultCoatingForm,
    layer: asString(details.layer, record?.layer_name || defaultCoatingForm.layer),
    machineTemplate: asString(details.machineTemplate, defaultCoatingForm.machineTemplate),
    inTime: asString(details.inTime, defaultCoatingForm.inTime),
    inOperator: asString(details.inOperator, defaultCoatingForm.inOperator),
    programName: asString(details.programName, defaultCoatingForm.programName),
    outTime: asString(details.outTime, defaultCoatingForm.outTime),
    outOperator: asString(details.outOperator, defaultCoatingForm.outOperator),
    crucibleMaterial: asString(details.crucibleMaterial, defaultCoatingForm.crucibleMaterial),
    crystalFrequency: asString(details.crystalFrequency, defaultCoatingForm.crystalFrequency),
    rotationSpeed: asString(details.rotationSpeed, defaultCoatingForm.rotationSpeed),
    transferVacuum: asString(details.transferVacuum, defaultCoatingForm.transferVacuum),
    crystalMonitor: asString(details.crystalMonitor, defaultCoatingForm.crystalMonitor),
    ionSource: asString(details.ionSource, defaultCoatingForm.ionSource),
    ionSourceArPcPressure: asString(details.ionSourceArPcPressure, defaultCoatingForm.ionSourceArPcPressure),
    bombardCoolingTime: asString(details.bombardCoolingTime, defaultCoatingForm.bombardCoolingTime),
    processVacuum: asString(details.processVacuum, defaultCoatingForm.processVacuum),
    parameterValues,
  };
}

function getCoatingStageStatus(form: CoatingForm) {
  if (form.outTime.trim()) {
    return "已完成";
  }
  if (form.inTime.trim()) {
    return "进行中";
  }
  return "未开始";
}

function getCoatingFieldLocks(record: ProcessRecord | null): CoatingFieldLocks {
  const details = isObject(record?.details) ? record.details : {};
  const parameterValues = isObject(details.parameterValues) ? details.parameterValues : {};
  const locks: CoatingFieldLocks = {};
  (Object.keys(defaultCoatingForm) as Array<keyof CoatingForm>)
    .filter((field): field is CoatingScalarField => field !== "parameterValues")
    .forEach((field) => {
    if (typeof details[field] === "string" && details[field].trim()) {
      locks[field] = true;
    }
  });
  const parameterLocks: Record<string, boolean> = {};
  Object.entries(parameterValues).forEach(([key, value]) => {
    if (typeof value === "string" && value.trim()) {
      parameterLocks[key] = true;
    }
  });
  if (Object.keys(parameterLocks).length > 0) {
    locks.parameterValues = parameterLocks;
  }
  return locks;
}

function fillEtchingRecord(record: ProcessRecord | null) {
  const details = isObject(record?.details) ? record.details : {};

  return {
    ...defaultEtchingForm,
    layer: asString(details.layer, record?.layer_name || defaultEtchingForm.layer),
    machineTemplate: asString(details.machineTemplate, defaultEtchingForm.machineTemplate),
    inTime: asString(details.inTime, defaultEtchingForm.inTime),
    operator: asString(details.operator, defaultEtchingForm.operator),
    programName: asString(details.programName, defaultEtchingForm.programName),
    outTime: asString(details.outTime, defaultEtchingForm.outTime),
    machineStatus: asString(details.machineStatus, defaultEtchingForm.machineStatus),
    remark: asString(details.remark, defaultEtchingForm.remark),
    upperPower: asString(details.upperPower, defaultEtchingForm.upperPower),
    upperReflectPower: asString(details.upperReflectPower, defaultEtchingForm.upperReflectPower),
    lowerPower: asString(details.lowerPower, defaultEtchingForm.lowerPower),
    lowerReflectPower: asString(details.lowerReflectPower, defaultEtchingForm.lowerReflectPower),
    gasFlow: asString(details.gasFlow, defaultEtchingForm.gasFlow),
    chamberPressure: asString(details.chamberPressure, defaultEtchingForm.chamberPressure),
    backsideHelium: asString(details.backsideHelium, defaultEtchingForm.backsideHelium),
    dcBiasMax: asString(details.dcBiasMax, defaultEtchingForm.dcBiasMax),
    lowerTemperature: asString(details.lowerTemperature, defaultEtchingForm.lowerTemperature),
    chamberTemperature: asString(details.chamberTemperature, defaultEtchingForm.chamberTemperature),
    etchingTime: asString(details.etchingTime, defaultEtchingForm.etchingTime),
    etchingLoop: asString(details.etchingLoop, defaultEtchingForm.etchingLoop),
    beamGridVoltage: asString(details.beamGridVoltage, defaultEtchingForm.beamGridVoltage),
    beamGridCurrent: asString(details.beamGridCurrent, defaultEtchingForm.beamGridCurrent),
    acceleratorGridVoltage: asString(details.acceleratorGridVoltage, defaultEtchingForm.acceleratorGridVoltage),
    neutralizerOutputCurrent: asString(
      details.neutralizerOutputCurrent,
      defaultEtchingForm.neutralizerOutputCurrent,
    ),
    stageAngle: asString(details.stageAngle, defaultEtchingForm.stageAngle),
  };
}

function getEtchingStageStatus(form: EtchingForm) {
  if (form.outTime.trim()) {
    return "已完成";
  }
  if (form.inTime.trim()) {
    return "进行中";
  }
  return "未开始";
}

function getEtchingFieldLocks(record: ProcessRecord | null): EtchingFieldLocks {
  const details = isObject(record?.details) ? record.details : {};
  const locks: EtchingFieldLocks = {};
  (Object.keys(defaultEtchingForm) as Array<keyof EtchingForm>).forEach((field) => {
    if (typeof details[field] === "string" && details[field].trim()) {
      locks[field] = true;
    }
  });
  return locks;
}

function fillWetProcessRecord(record: ProcessRecord | null) {
  const details = isObject(record?.details) ? record.details : {};
  const rawParameterValues = isObject(details.parameterValues) ? details.parameterValues : {};
  const parameterValues: Record<string, string> = {};
  Object.entries(rawParameterValues).forEach(([key, value]) => {
    parameterValues[key] = asString(value);
  });
  const processTemplate = wetProcessTemplates.some((template) => template.name === details.processTemplate)
    ? (details.processTemplate as WetProcessName)
    : defaultWetProcessForm.processTemplate;

  return {
    ...defaultWetProcessForm,
    layer: asString(details.layer, record?.layer_name || defaultWetProcessForm.layer),
    processTemplate,
    equipmentName: asString(details.equipmentName, defaultWetProcessForm.equipmentName),
    operator: asString(details.operator, defaultWetProcessForm.operator),
    inTime: asString(details.inTime, defaultWetProcessForm.inTime),
    outTime: asString(details.outTime, defaultWetProcessForm.outTime),
    parameterValues,
  };
}

function getWetProcessStageStatus(form: WetProcessForm) {
  if (form.outTime.trim()) {
    return "已完成";
  }
  if (form.inTime.trim()) {
    return "进行中";
  }
  return "未开始";
}

function getWetProcessFieldLocks(record: ProcessRecord | null): WetProcessFieldLocks {
  const details = isObject(record?.details) ? record.details : {};
  const parameterValues = isObject(details.parameterValues) ? details.parameterValues : {};
  const locks: WetProcessFieldLocks = {};
  (Object.keys(defaultWetProcessForm) as Array<keyof WetProcessForm>)
    .filter((field): field is WetProcessScalarField => field !== "parameterValues")
    .forEach((field) => {
      if (typeof details[field] === "string" && details[field].trim()) {
        locks[field] = true;
      }
    });
  const parameterLocks: Record<string, boolean> = {};
  Object.entries(parameterValues).forEach(([key, value]) => {
    if (typeof value === "string" && value.trim()) {
      parameterLocks[key] = true;
    }
  });
  if (Object.keys(parameterLocks).length > 0) {
    locks.parameterValues = parameterLocks;
  }
  return locks;
}

function getDetectionResult(form: DetectionForm) {
  const values = detectionPointKeys
    .map((key, index) => ({
      index: index + 1,
      value: Number.parseFloat(form.points[key].trim()),
    }))
    .filter((point) => Number.isFinite(point.value));

  const average = values.length
    ? values.reduce((sum, point) => sum + point.value, 0) / values.length
    : null;

  return {
    filledLabels: values.map((point) => String(point.index)).join(", "),
    averageText: average === null ? "-" : average.toFixed(2).replace(/\.?0+$/, ""),
  };
}

function ReadonlyField({ label, value }: { label: string; value: string }) {
  return (
    <label className="process-record-field">
      <span>{label}</span>
      <input value={value} readOnly />
    </label>
  );
}

function ProcessTextField({ label, value, disabled, placeholder, onChange }: TextFieldProps) {
  return (
    <label className="process-record-field">
      <span>{label}</span>
      <input
        disabled={disabled}
        placeholder={placeholder}
        value={value}
        onChange={(event) => onChange?.(event.target.value)}
      />
    </label>
  );
}

function LayerCombobox({
  value,
  disabled,
  sampleId,
  onChange,
  onCommit,
}: {
  value: string;
  disabled: boolean;
  sampleId?: number;
  onChange: (value: string) => void;
  onCommit: (value: string) => void;
}) {
  const fieldRef = useRef<HTMLLabelElement | null>(null);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [suggestions, setSuggestions] = useState<string[]>([]);

  function commitLayer(nextValue = value) {
    const normalized = normalizeRecordLayer(nextValue);
    onCommit(normalized === "默认图层" ? "" : normalized);
  }

  useEffect(() => {
    function handlePointerDown(event: PointerEvent) {
      if (fieldRef.current && !fieldRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    }

    window.addEventListener("pointerdown", handlePointerDown);
    return () => window.removeEventListener("pointerdown", handlePointerDown);
  }, []);

  useEffect(() => {
    if (!sampleId || disabled || !open) {
      setSuggestions([]);
      setLoading(false);
      return;
    }

    let cancelled = false;
    setLoading(true);
    const timer = window.setTimeout(async () => {
      try {
        const rows = await getProcessLayerSuggestions(sampleId, value);
        if (!cancelled) {
          setSuggestions(rows);
        }
      } catch {
        if (!cancelled) {
          setSuggestions([]);
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }, 180);

    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [disabled, open, sampleId, value]);

  return (
    <label className="process-record-field process-sample-combobox" ref={fieldRef}>
      <span>工艺图层</span>
      <input
        disabled={disabled}
        placeholder="请选择或输入工艺图层"
        value={value}
        onBlur={() => {
          window.setTimeout(() => setOpen(false), 120);
          commitLayer();
        }}
        onChange={(event) => {
          onChange(event.target.value);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        onKeyDown={(event) => {
          if (event.key === "Enter") {
            event.preventDefault();
            commitLayer();
            setOpen(false);
          }
        }}
      />
      {open && !disabled && (loading || suggestions.length > 0) && (
        <SuggestionPopover
          loading={loading}
          suggestions={suggestions}
          onPick={(pickedValue) => {
            onChange(pickedValue);
            onCommit(pickedValue);
            setOpen(false);
          }}
        />
      )}
    </label>
  );
}

function ProcessSelectField({
  label,
  value,
  disabled,
  options,
  placeholder = "请选择",
  onChange,
}: TextFieldProps & { options: string[] }) {
  return (
    <label className="process-record-field">
      <span>{label}</span>
      <select disabled={disabled} value={value} onChange={(event) => onChange?.(event.target.value)}>
        <option value="">{placeholder}</option>
        {options.map((option) => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
      </select>
    </label>
  );
}

function SuggestionPopover({
  suggestions,
  loading,
  onPick,
}: {
  suggestions: string[];
  loading?: boolean;
  onPick: (value: string) => void;
}) {
  return (
    <div className="process-suggestion-popover" role="listbox">
      {loading && <div className="process-suggestion-muted">查找中...</div>}
      {suggestions.map((value) => (
        <button
          key={value}
          role="option"
          type="button"
          onMouseDown={(event) => event.preventDefault()}
          onClick={() => onPick(value)}
        >
          <strong>{value}</strong>
        </button>
      ))}
    </div>
  );
}

function WaferSuggestField({
  field,
  label,
  value,
  disabled,
  placeholder,
  onChange,
}: {
  field: WaferFieldKey;
  label: string;
  value: string;
  disabled: boolean;
  placeholder: string;
  onChange: (value: string) => void;
}) {
  const fieldRef = useRef<HTMLLabelElement | null>(null);
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (disabled) {
      setSuggestions([]);
      setOpen(false);
      return;
    }

    let cancelled = false;
    setLoading(true);
    const timer = window.setTimeout(async () => {
      try {
        const rows = await getProcessFieldSuggestions(field, value);
        if (!cancelled) {
          setSuggestions(rows);
        }
      } catch {
        if (!cancelled) {
          setSuggestions([]);
          setOpen(false);
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }, 180);

    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [disabled, field, value]);

  useEffect(() => {
    function handlePointerDown(event: PointerEvent) {
      if (fieldRef.current && !fieldRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    }

    window.addEventListener("pointerdown", handlePointerDown);
    return () => window.removeEventListener("pointerdown", handlePointerDown);
  }, []);

  return (
    <label className="process-record-field process-sample-combobox" ref={fieldRef}>
      <span>{label}</span>
      <input
        disabled={disabled}
        placeholder={placeholder}
        value={value}
        onBlur={() => window.setTimeout(() => setOpen(false), 120)}
        onChange={(event) => {
          onChange(event.target.value);
          setOpen(true);
        }}
        onFocus={() => {
          if (suggestions.length > 0) {
            setOpen(true);
          }
        }}
      />
      {open && (
        <SuggestionPopover
          loading={loading}
          suggestions={suggestions}
          onPick={(pickedValue) => {
            onChange(pickedValue);
            setOpen(false);
          }}
        />
      )}
    </label>
  );
}

function sectionStatusMeta(status: LithographySectionStatus, pendingLabel = "待填写/可略过") {
  if (status === "done") {
    return { className: "done", label: "已完成" };
  }
  if (status === "editing") {
    return { className: "active", label: "填写中" };
  }
  if (status === "skipped") {
    return { className: "skipped", label: "已略过" };
  }
  return { className: "pending", label: pendingLabel };
}

function getLithographyStageStatus(sectionState: LithographySectionState) {
  return sectionState.coat === "done" && sectionState.exposure === "done" && sectionState.develop === "done"
    ? "已完成"
    : "填写中";
}

function LithographyFormView({
  form,
  sectionState,
  disabled,
  sampleId,
  onChange,
  onLayerCommit,
  onEditSection,
  onSaveSection,
}: {
  form: LithographyForm;
  sectionState: LithographySectionState;
  disabled: boolean;
  sampleId?: number;
  onChange: <K extends keyof LithographyForm>(key: K, value: LithographyForm[K]) => void;
  onLayerCommit: (value: string) => void;
  onEditSection: (section: keyof LithographySectionState) => void;
  onSaveSection: (section: keyof LithographySectionState) => void;
}) {
  const exposureParams = form.exposureTool ? exposureParamMap[form.exposureTool] : [];
  const coatLocked = sectionState.coat === "done";
  const exposureLocked = sectionState.exposure === "done";
  const developLocked = sectionState.develop === "done";
  const developSkipped = sectionState.develop === "skipped" || form.skippedDevelop;
  const exposurePending = sectionState.exposure === "pending";
  const developPending = sectionState.develop === "pending";
  const fieldsDisabled = disabled;
  const filledCount = Object.entries(form).filter(([key, value]) => key !== "skippedDevelop" && String(value).trim()).length;

  return (
    <div className="process-lithography-body process-coating-body">
      <div className="process-coating-top-row">
        <LayerCombobox
          disabled={disabled}
          sampleId={sampleId}
          value={form.layer}
          onChange={(value) => onChange("layer", value)}
          onCommit={onLayerCommit}
        />
        <ReadonlyField label="自动状态" value={getLithographyStageStatus(sectionState)} />
      </div>

      <section className={`process-coating-section process-lithography-section${coatLocked ? " locked" : ""}`}>
        <header className="process-lithography-section-header">
          <div>
            <h4>涂胶信息</h4>
            <span>{coatLocked ? "已完成，信息已锁定" : "填写中"}</span>
          </div>
          <div className="process-section-actions">
            <button
              className="process-text-action"
              disabled={disabled || coatLocked}
              type="button"
              onClick={() => onSaveSection("coat")}
            >
              保存
            </button>
            <button
              className="process-text-action"
              disabled={disabled || !coatLocked}
              type="button"
              onClick={() => onEditSection("coat")}
            >
              {coatLocked ? "编辑" : "编辑中"}
            </button>
          </div>
        </header>
        <div className="process-grid process-coating-grid">
          <ProcessTextField
            disabled={fieldsDisabled || coatLocked}
            label="涂胶机台"
            value={form.coatTool}
            onChange={(value) => onChange("coatTool", value)}
          />
          <ProcessTextField
            disabled={fieldsDisabled || coatLocked}
            label="光刻胶"
            value={form.photoresist}
            onChange={(value) => onChange("photoresist", value)}
          />
          <ProcessTextField
            disabled={fieldsDisabled || coatLocked}
            label="胶厚"
            value={form.resistThickness}
            onChange={(value) => onChange("resistThickness", value)}
          />
          <ProcessTextField
            disabled={fieldsDisabled || coatLocked}
            label="备注"
            value={form.coatRemark}
            onChange={(value) => onChange("coatRemark", value)}
          />
        </div>
      </section>

      <section className={`process-coating-section process-lithography-section${exposureLocked ? " locked" : ""}`}>
        <header className="process-lithography-section-header">
          <div>
            <h4>曝光信息</h4>
            <span>{exposureLocked ? "已完成，信息已锁定" : exposurePending ? "待填写" : "选择曝光机台后自动显示对应参数"}</span>
          </div>
          <div className="process-section-actions">
            <button
              className="process-text-action"
              disabled={disabled || exposureLocked || exposurePending}
              type="button"
              onClick={() => onSaveSection("exposure")}
            >
              保存
            </button>
            <button
              className="process-text-action"
              disabled={disabled || (!exposureLocked && !exposurePending)}
              type="button"
              onClick={() => onEditSection("exposure")}
            >
              {exposureLocked || exposurePending ? "编辑" : "编辑中"}
            </button>
          </div>
        </header>
        <div className="process-grid process-coating-grid">
          <ProcessSelectField
            disabled={fieldsDisabled || exposureLocked || exposurePending}
            label="曝光机台"
            options={exposureToolOptions}
            value={form.exposureTool}
            onChange={(value) => onChange("exposureTool", value as ExposureTool)}
          />
          <ProcessTextField
            disabled={fieldsDisabled || exposureLocked || exposurePending}
            label="版图"
            value={form.mask}
            onChange={(value) => onChange("mask", value)}
          />
          {exposureParams.map((param) => (
            <ProcessTextField
              disabled={fieldsDisabled || exposureLocked || exposurePending}
              key={String(param.key)}
              label={param.label}
              placeholder={param.placeholder}
              value={String(form[param.key] ?? "")}
              onChange={(value) => onChange(param.key, value)}
            />
          ))}
          <ProcessTextField
            disabled={fieldsDisabled || exposureLocked || exposurePending}
            label="备注"
            value={form.exposureRemark}
            onChange={(value) => onChange("exposureRemark", value)}
          />
        </div>
      </section>

      <section className={`process-coating-section process-lithography-section${developLocked || developSkipped ? " locked" : ""}`}>
        <header className="process-lithography-section-header">
          <div>
            <h4>显影信息</h4>
            <span>{developSkipped ? "已略过，信息已锁定" : developLocked ? "已完成，信息已锁定" : developPending ? "待填写/可略过" : "填写中"}</span>
          </div>
          <div className="process-section-actions">
            <button
              className="process-text-action"
              disabled={disabled || developLocked || developSkipped || developPending}
              type="button"
              onClick={() => onSaveSection("develop")}
            >
              保存
            </button>
            <button
              className="process-text-action"
              disabled={disabled || (!developLocked && !developSkipped && !developPending)}
              type="button"
              onClick={() => {
                if (developSkipped) {
                  onEditSection("develop");
                } else if (developLocked) {
                  onEditSection("develop");
                } else if (developPending) {
                  onEditSection("develop");
                }
              }}
            >
              {developLocked || developSkipped || developPending ? "编辑" : "编辑中"}
            </button>
          </div>
        </header>
        <div className="process-grid process-coating-grid">
          <ProcessTextField
            disabled={fieldsDisabled || developLocked || developSkipped || developPending}
            label="显影机台"
            value={form.developTool}
            onChange={(value) => onChange("developTool", value)}
          />
          <ProcessTextField
            disabled={fieldsDisabled || developLocked || developSkipped || developPending}
            label="显影液类型"
            value={form.developerType}
            onChange={(value) => onChange("developerType", value)}
          />
          <ProcessTextField
            disabled={fieldsDisabled || developLocked || developSkipped || developPending}
            label="显影时间"
            value={form.developTime}
            onChange={(value) => onChange("developTime", value)}
          />
          <ProcessTextField
            disabled={fieldsDisabled || developLocked || developSkipped || developPending}
            label="备注"
            value={form.developRemark}
            onChange={(value) => onChange("developRemark", value)}
          />
        </div>
      </section>

      <section className="process-coating-summary" aria-label="光刻填写摘要">
        <strong>当前图层：{form.layer || "-"}</strong>
        <strong>工艺段：3项</strong>
        <strong>已填写：{filledCount}项</strong>
        <strong>显影状态：{developSkipped ? "已略过" : sectionStatusMeta(sectionState.develop).label}</strong>
      </section>
    </div>
  );
}

function DetectionMachineField({
  value,
  disabled,
  locked,
  onChange,
}: {
  value: string;
  disabled: boolean;
  locked?: boolean;
  onChange: (value: string) => void;
}) {
  const fieldRef = useRef<HTMLLabelElement | null>(null);
  const [open, setOpen] = useState(false);
  const keyword = value.trim().toLowerCase();
  const suggestions = detectionMachineTemplates
    .map((template) => template.name)
    .filter((name) => !keyword || name.toLowerCase().includes(keyword));

  useEffect(() => {
    function handlePointerDown(event: PointerEvent) {
      if (fieldRef.current && !fieldRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    }

    window.addEventListener("pointerdown", handlePointerDown);
    return () => window.removeEventListener("pointerdown", handlePointerDown);
  }, []);

  return (
    <label className="process-record-field process-sample-combobox" ref={fieldRef}>
      <span>测量机台</span>
      <input
        disabled={disabled || locked}
        value={value}
        onBlur={() => window.setTimeout(() => setOpen(false), 120)}
        onChange={(event) => {
          onChange(event.target.value);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
      />
      {open && !disabled && !locked && suggestions.length > 0 && (
        <SuggestionPopover
          suggestions={suggestions}
          onPick={(pickedValue) => {
            onChange(pickedValue);
            setOpen(false);
          }}
        />
      )}
    </label>
  );
}

function DetectionFormView({
  form,
  locked,
  disabled,
  sampleId,
  onChange,
  onLayerCommit,
  onPointChange,
}: {
  form: DetectionForm;
  locked: boolean;
  disabled: boolean;
  sampleId?: number;
  onChange: <K extends keyof Omit<DetectionForm, "points">>(key: K, value: DetectionForm[K]) => void;
  onLayerCommit: (value: string) => void;
  onPointChange: (key: DetectionPointKey, value: string) => void;
}) {
  const result = getDetectionResult(form);
  const fieldsDisabled = disabled || locked;
  const currentTemplate = detectionMachineTemplates.find((template) => template.name === form.tool);
  const projectOptions = currentTemplate?.projectOptions ?? [];
  const pointLabels = currentTemplate?.pointLabels ?? [];
  const calculationRule = currentTemplate?.calculationRule ?? "填写几个测试点就计算几个";
  const hasTemplate = Boolean(currentTemplate);
  const parameterCount = hasTemplate ? detectionPointKeys.length : 0;
  const filledCount = detectionPointKeys.filter((key) => form.points[key].trim()).length;

  return (
    <div className="process-lithography-body process-coating-body process-detection-body">
      <div className="process-coating-top-row">
        <LayerCombobox
          disabled={disabled}
          sampleId={sampleId}
          value={form.layer}
          onChange={(value) => onChange("layer", value)}
          onCommit={onLayerCommit}
        />
        <ReadonlyField label="自动状态" value={locked ? "已完成" : "填写中"} />
      </div>

      <section className="process-coating-section process-coating-template-section">
        <h4>机台参数模板</h4>
        <div className="process-grid process-coating-template-grid">
          <DetectionMachineField
            disabled={false}
            locked={locked}
            value={form.tool}
            onChange={(value) => onChange("tool", value)}
          />
        </div>
      </section>

      <section className="process-coating-section">
        <h4>通用信息</h4>
        <div className="process-grid process-coating-grid">
          <ProcessSelectField
            disabled={fieldsDisabled || !hasTemplate}
            label="测量项目"
            options={projectOptions}
            value={form.project}
            onChange={(value) => onChange("project", value)}
          />
          <ProcessTextField
            disabled={fieldsDisabled}
            label="数据单位"
            value={form.unit}
            onChange={(value) => onChange("unit", value)}
          />
          <ReadonlyField label="计算规则" value={calculationRule} />
          <ProcessTextField
            disabled={fieldsDisabled}
            label="备注"
            value={form.remark}
            onChange={(value) => onChange("remark", value)}
          />
        </div>
      </section>

      <section className="process-coating-section">
        <h4>{form.tool || "台阶仪"} 参数</h4>
        <div className="process-grid process-coating-grid process-coating-param-grid">
          {hasTemplate ? (
            detectionPointKeys.map((key, index) => (
              <ProcessTextField
                disabled={fieldsDisabled}
                key={key}
                label={pointLabels[index] ?? `测试点${index + 1}`}
                value={form.points[key]}
                onChange={(value) => onPointChange(key, value)}
              />
            ))
          ) : (
            <p className="process-suggestion-muted process-coating-empty-template">
              未匹配到检测机台模板，可先输入机台名称后保存。
            </p>
          )}
        </div>
      </section>

      <section className="process-coating-section process-measurement-result">
        <header className="process-measurement-result-header">
          <h4>测量结果</h4>
          <span>仅计算已填写的测试点，填写几个计算几个</span>
        </header>
        <div className="process-measurement-table" role="table" aria-label="测量结果">
          <div className="process-measurement-row header" role="row">
            <span role="columnheader">测量项目</span>
            <span role="columnheader">已填点位</span>
            <span role="columnheader">平均值</span>
            <span role="columnheader">单位</span>
          </div>
          <div className="process-measurement-row" role="row">
            <span role="cell">{form.project}</span>
            <span role="cell">{result.filledLabels || "-"}</span>
            <strong role="cell">{result.averageText}</strong>
            <span role="cell">{form.unit || "-"}</span>
          </div>
        </div>
      </section>

      <section className="process-coating-summary" aria-label="检测填写摘要">
        <strong>当前机台：{form.tool || "-"}</strong>
        <strong>模板字段：{parameterCount}项</strong>
        <strong>已填写：{filledCount}项</strong>
        <strong>平均值：{result.averageText}</strong>
      </section>
    </div>
  );
}

function CoatingTextField({
  form,
  field,
  label,
  disabled,
  locked = false,
  placeholder,
  unit,
  onChange,
}: {
  form: CoatingForm;
  field: CoatingScalarField;
  label: string;
  disabled: boolean;
  locked?: boolean;
  placeholder?: string;
  unit?: string;
  onChange: (key: CoatingScalarField, value: string) => void;
}) {
  return (
    <label className={`process-record-field${unit ? " process-unit-field" : ""}`}>
      <span>{label}</span>
      <div className="process-unit-input">
        <input
          disabled={disabled || locked}
          placeholder={placeholder}
          value={form[field]}
          onChange={(event) => onChange(field, event.target.value)}
        />
        {unit && <span>{unit}</span>}
      </div>
    </label>
  );
}

function CoatingParameterField({
  value,
  label,
  disabled,
  locked = false,
  unit,
  onChange,
}: {
  value: string;
  label: string;
  disabled: boolean;
  locked?: boolean;
  unit?: string;
  onChange: (value: string) => void;
}) {
  return (
    <label className={`process-record-field${unit ? " process-unit-field" : ""}`}>
      <span>{label}</span>
      <div className="process-unit-input">
        <input disabled={disabled || locked} value={value} onChange={(event) => onChange(event.target.value)} />
        {unit && <span>{unit}</span>}
      </div>
    </label>
  );
}

function CoatingMachineField({
  value,
  disabled,
  locked,
  onChange,
}: {
  value: string;
  disabled: boolean;
  locked?: boolean;
  onChange: (value: string) => void;
}) {
  const fieldRef = useRef<HTMLLabelElement | null>(null);
  const [open, setOpen] = useState(false);
  const keyword = value.trim().toLowerCase();
  const suggestions = coatingMachineTemplates
    .map((template) => template.name)
    .filter((name) => !keyword || name.toLowerCase().includes(keyword));

  useEffect(() => {
    function handlePointerDown(event: PointerEvent) {
      if (fieldRef.current && !fieldRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    }

    window.addEventListener("pointerdown", handlePointerDown);
    return () => window.removeEventListener("pointerdown", handlePointerDown);
  }, []);

  return (
    <label className="process-record-field process-sample-combobox" ref={fieldRef}>
      <span>机台名称</span>
      <input
        disabled={disabled || locked}
        value={value}
        onBlur={() => window.setTimeout(() => setOpen(false), 120)}
        onChange={(event) => {
          onChange(event.target.value);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
      />
      {open && !disabled && !locked && suggestions.length > 0 && (
        <SuggestionPopover
          suggestions={suggestions}
          onPick={(pickedValue) => {
            onChange(pickedValue);
            setOpen(false);
          }}
        />
      )}
    </label>
  );
}

function CoatingFormView({
  form,
  lockedFields,
  disabled,
  sampleId,
  onChange,
  onLayerCommit,
}: {
  form: CoatingForm;
  lockedFields: CoatingFieldLocks;
  disabled: boolean;
  sampleId?: number;
  onChange: <K extends keyof CoatingForm>(key: K, value: CoatingForm[K]) => void;
  onLayerCommit: (value: string) => void;
}) {
  const status = getCoatingStageStatus(form);
  const currentTemplate = coatingMachineTemplates.find((template) => template.name === form.machineTemplate);
  const parameterFields = currentTemplate?.fields ?? [];
  const parameterCount = parameterFields.length;
  const filledCount =
    Object.entries(form)
      .filter(([key]) => key !== "parameterValues")
      .filter(([, value]) => typeof value === "string" && value.trim()).length +
    Object.values(form.parameterValues).filter((value) => value.trim()).length;

  return (
    <div className="process-lithography-body process-coating-body">
      <div className="process-coating-top-row">
        <LayerCombobox
          disabled={disabled}
          sampleId={sampleId}
          value={form.layer}
          onChange={(value) => onChange("layer", value)}
          onCommit={onLayerCommit}
        />
        <ReadonlyField label="自动状态" value={status} />
      </div>

      <section className="process-coating-section process-coating-template-section">
        <h4>机台参数模板</h4>
        <div className="process-grid process-coating-template-grid">
          <CoatingMachineField
            disabled={false}
            locked={Boolean(lockedFields.machineTemplate)}
            value={form.machineTemplate}
            onChange={(value) => onChange("machineTemplate", value)}
          />
        </div>
      </section>

      <section className="process-coating-section">
        <h4>通用信息</h4>
        <div className="process-grid process-coating-grid">
          <CoatingTextField
            disabled={disabled}
            field="inTime"
            form={form}
            label="进样时间"
            locked={Boolean(lockedFields.inTime)}
            placeholder="YYYY-MM-DD HH:mm"
            onChange={onChange}
          />
          <CoatingTextField
            disabled={disabled}
            field="inOperator"
            form={form}
            label="进样人"
            locked={Boolean(lockedFields.inOperator)}
            placeholder="请输入姓名"
            onChange={onChange}
          />
          <CoatingTextField
            disabled={disabled}
            field="programName"
            form={form}
            label="程序名称 / 镀膜程序"
            locked={Boolean(lockedFields.programName)}
            placeholder="请输入程序"
            onChange={onChange}
          />
          <CoatingTextField
            disabled={disabled}
            field="outTime"
            form={form}
            label="出样时间"
            locked={Boolean(lockedFields.outTime)}
            placeholder="YYYY-MM-DD HH:mm"
            onChange={onChange}
          />
          <CoatingTextField
            disabled={disabled}
            field="outOperator"
            form={form}
            label="出样人"
            locked={Boolean(lockedFields.outOperator)}
            placeholder="请输入姓名"
            onChange={onChange}
          />
          <CoatingTextField
            disabled={disabled}
            field="crucibleMaterial"
            form={form}
            label="坩埚 / 材料"
            locked={Boolean(lockedFields.crucibleMaterial)}
            placeholder="按机台填写"
            onChange={onChange}
          />
        </div>
      </section>

      <section className="process-coating-section">
        <h4>{form.machineTemplate || "ProLine PVD200"} 参数</h4>
        <div className="process-grid process-coating-grid process-coating-param-grid">
          {parameterFields.length > 0 ? (
            parameterFields.map((parameter) => (
              <CoatingParameterField
                disabled={disabled}
                key={`${form.machineTemplate}-${parameter.key}-${parameter.label}`}
                label={parameter.label}
                locked={Boolean(lockedFields.parameterValues?.[parameter.key])}
                unit={parameter.unit}
                value={form.parameterValues[parameter.key] ?? ""}
                onChange={(value) => onChange("parameterValues", { ...form.parameterValues, [parameter.key]: value })}
              />
            ))
          ) : (
            <p className="process-suggestion-muted process-coating-empty-template">未匹配到机台模板，可先输入机台名称后保存。</p>
          )}
        </div>
      </section>

      <section className="process-coating-summary" aria-label="镀膜填写摘要">
        <strong>当前机台：{form.machineTemplate || "-"}</strong>
        <strong>模板字段：{parameterCount}项</strong>
        <strong>已填写：{filledCount}项</strong>
        <strong>缺失必填：待校验</strong>
      </section>
    </div>
  );
}

function EtchingTextField({
  form,
  field,
  label,
  disabled,
  locked = false,
  placeholder,
  unit,
  onChange,
}: {
  form: EtchingForm;
  field: keyof EtchingForm;
  label: string;
  disabled: boolean;
  locked?: boolean;
  placeholder?: string;
  unit?: string;
  onChange: (key: keyof EtchingForm, value: string) => void;
}) {
  return (
    <label className={`process-record-field${unit ? " process-unit-field" : ""}`}>
      <span>{label}</span>
      <div className="process-unit-input">
        <input
          disabled={disabled || locked}
          placeholder={placeholder}
          value={form[field]}
          onChange={(event) => onChange(field, event.target.value)}
        />
        {unit && <span>{unit}</span>}
      </div>
    </label>
  );
}

function EtchingMachineField({
  value,
  disabled,
  locked,
  onChange,
}: {
  value: string;
  disabled: boolean;
  locked?: boolean;
  onChange: (value: string) => void;
}) {
  const fieldRef = useRef<HTMLLabelElement | null>(null);
  const [open, setOpen] = useState(false);
  const keyword = value.trim().toLowerCase();
  const suggestions = etchingMachineTemplates
    .map((template) => template.name)
    .filter((name) => !keyword || name.toLowerCase().includes(keyword));

  useEffect(() => {
    function handlePointerDown(event: PointerEvent) {
      if (fieldRef.current && !fieldRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    }

    window.addEventListener("pointerdown", handlePointerDown);
    return () => window.removeEventListener("pointerdown", handlePointerDown);
  }, []);

  return (
    <label className="process-record-field process-sample-combobox" ref={fieldRef}>
      <span>机台名称</span>
      <input
        disabled={disabled || locked}
        value={value}
        onBlur={() => window.setTimeout(() => setOpen(false), 120)}
        onChange={(event) => {
          onChange(event.target.value);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
      />
      {open && !disabled && !locked && suggestions.length > 0 && (
        <SuggestionPopover
          suggestions={suggestions}
          onPick={(pickedValue) => {
            onChange(pickedValue);
            setOpen(false);
          }}
        />
      )}
    </label>
  );
}

function EtchingFormView({
  form,
  lockedFields,
  disabled,
  sampleId,
  onChange,
  onLayerCommit,
}: {
  form: EtchingForm;
  lockedFields: EtchingFieldLocks;
  disabled: boolean;
  sampleId?: number;
  onChange: (key: keyof EtchingForm, value: string) => void;
  onLayerCommit: (value: string) => void;
}) {
  const status = getEtchingStageStatus(form);
  const filledCount = Object.values(form).filter((value) => value.trim()).length;
  const currentTemplate = etchingMachineTemplates.find((template) => template.name === form.machineTemplate);
  const parameterFields = currentTemplate?.fields ?? etchingMachineTemplates[0].fields;
  const parameterCount = parameterFields.length;

  return (
    <div className="process-lithography-body process-coating-body">
      <div className="process-coating-top-row">
        <LayerCombobox
          disabled={disabled}
          sampleId={sampleId}
          value={form.layer}
          onChange={(value) => onChange("layer", value)}
          onCommit={onLayerCommit}
        />
        <ReadonlyField label="自动状态" value={status} />
      </div>

      <section className="process-coating-section process-coating-template-section">
        <h4>机台参数模板</h4>
        <div className="process-grid process-coating-template-grid">
          <EtchingMachineField
            disabled={false}
            locked={Boolean(lockedFields.machineTemplate)}
            value={form.machineTemplate}
            onChange={(value) => onChange("machineTemplate", value)}
          />
        </div>
      </section>

      <section className="process-coating-section">
        <h4>通用信息</h4>
        <div className="process-grid process-coating-grid">
          <EtchingTextField
            disabled={disabled}
            field="inTime"
            form={form}
            label="进样时间"
            locked={Boolean(lockedFields.inTime)}
            placeholder="YYYY-MM-DD HH:mm"
            onChange={onChange}
          />
          <EtchingTextField
            disabled={disabled}
            field="operator"
            form={form}
            label="操作人"
            locked={Boolean(lockedFields.operator)}
            placeholder="请输入姓名"
            onChange={onChange}
          />
          <EtchingTextField
            disabled={disabled}
            field="programName"
            form={form}
            label="程序"
            locked={Boolean(lockedFields.programName)}
            placeholder="请输入程序"
            onChange={onChange}
          />
          <EtchingTextField
            disabled={disabled}
            field="outTime"
            form={form}
            label="出样时间"
            locked={Boolean(lockedFields.outTime)}
            placeholder="YYYY-MM-DD HH:mm"
            onChange={onChange}
          />
          <EtchingTextField
            disabled={disabled}
            field="machineStatus"
            form={form}
            label="机台运行情况"
            locked={Boolean(lockedFields.machineStatus)}
            onChange={onChange}
          />
          <EtchingTextField
            disabled={disabled}
            field="remark"
            form={form}
            label="备注"
            locked={Boolean(lockedFields.remark)}
            onChange={onChange}
          />
        </div>
      </section>

      <section className="process-coating-section">
        <h4>{form.machineTemplate || "Synapse"} 参数</h4>
        <div className="process-grid process-coating-grid process-coating-param-grid">
          {parameterFields.map((parameter) => (
            <EtchingTextField
              disabled={disabled}
              field={parameter.field}
              form={form}
              key={`${form.machineTemplate}-${parameter.field}-${parameter.label}`}
              label={parameter.label}
              locked={Boolean(lockedFields[parameter.field])}
              unit={parameter.unit}
              onChange={onChange}
            />
          ))}
        </div>
      </section>

      <section className="process-coating-summary" aria-label="刻蚀填写摘要">
        <strong>当前机台：{form.machineTemplate || "-"}</strong>
        <strong>模板字段：{parameterCount}项</strong>
        <strong>已填写：{filledCount}项</strong>
        <strong>缺失必填：待校验</strong>
      </section>
    </div>
  );
}

function EditableWetProcessTextField({
  form,
  field,
  label,
  disabled,
  locked = false,
  placeholder,
  onChange,
}: {
  form: WetProcessForm;
  field: WetProcessScalarField;
  label: string;
  disabled: boolean;
  locked?: boolean;
  placeholder?: string;
  onChange: (key: WetProcessScalarField, value: string) => void;
}) {
  return (
    <label className="process-record-field">
      <span>{label}</span>
      <input
        disabled={disabled || locked}
        placeholder={placeholder}
        value={form[field]}
        onChange={(event) => onChange(field, event.target.value)}
      />
    </label>
  );
}

function WetProcessParameterField({
  value,
  label,
  disabled,
  locked = false,
  unit,
  onChange,
}: {
  value: string;
  label: string;
  disabled: boolean;
  locked?: boolean;
  unit?: string;
  onChange: (value: string) => void;
}) {
  return (
    <label className={`process-record-field${unit ? " process-unit-field" : ""}`}>
      <span>{label}</span>
      <div className="process-unit-input">
        <input disabled={disabled || locked} value={value} onChange={(event) => onChange(event.target.value)} />
        {unit && <span>{unit}</span>}
      </div>
    </label>
  );
}

function WetProcessTemplateDropdown({
  value,
  disabled,
  locked,
  onChange,
}: {
  value: WetProcessName | "";
  disabled: boolean;
  locked?: boolean;
  onChange: (value: WetProcessName) => void;
}) {
  const rootRef = useRef<HTMLDivElement | null>(null);
  const [open, setOpen] = useState(false);
  const label = value || "请选择工艺";

  useEffect(() => {
    function handlePointerDown(event: PointerEvent) {
      if (rootRef.current && !rootRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    }

    window.addEventListener("pointerdown", handlePointerDown);
    return () => window.removeEventListener("pointerdown", handlePointerDown);
  }, []);

  return (
    <label className="process-record-field process-wet-template-field">
      <span>工艺选择模板</span>
      <div className="select-combobox" ref={rootRef}>
        <button
          className="select-combobox-trigger"
          disabled={disabled || locked}
          type="button"
          aria-expanded={open}
          onClick={() => setOpen((current) => !current)}
        >
          <span className={value ? "" : "placeholder"}>{label}</span>
          <span className="select-combobox-arrow" aria-hidden="true" />
        </button>
        {open && !disabled && !locked && (
          <div className="select-combobox-dropdown">
            {wetProcessTemplates.map((template) => (
              <button
                className={`select-combobox-option ${template.name === value ? "is-selected" : ""}`}
                key={template.name}
                type="button"
                onMouseDown={(event) => event.preventDefault()}
                onClick={() => {
                  onChange(template.name);
                  setOpen(false);
                }}
              >
                {template.name}
              </button>
            ))}
          </div>
        )}
      </div>
    </label>
  );
}

function WetProcessFormView({
  form,
  lockedFields,
  disabled,
  sampleId,
  onChange,
  onLayerCommit,
}: {
  form: WetProcessForm;
  lockedFields: WetProcessFieldLocks;
  disabled: boolean;
  sampleId?: number;
  onChange: <K extends keyof WetProcessForm>(key: K, value: WetProcessForm[K]) => void;
  onLayerCommit: (value: string) => void;
}) {
  const status = getWetProcessStageStatus(form);
  const currentTemplate = wetProcessTemplates.find((template) => template.name === form.processTemplate) ?? wetProcessTemplates[0];
  const parameterFields = currentTemplate.fields;
  const parameterCount = parameterFields.length;
  const filledCount =
    Object.entries(form)
      .filter(([key]) => key !== "parameterValues")
      .filter(([, value]) => typeof value === "string" && value.trim()).length +
    Object.values(form.parameterValues).filter((value) => value.trim()).length;

  return (
    <div className="process-lithography-body process-coating-body">
      <div className="process-coating-top-row">
        <LayerCombobox
          disabled={disabled}
          sampleId={sampleId}
          value={form.layer}
          onChange={(value) => onChange("layer", value)}
          onCommit={onLayerCommit}
        />
        <ReadonlyField label="自动状态" value={status} />
      </div>

      <section className="process-coating-section process-coating-template-section">
        <h4>工艺选择</h4>
        <div className="process-grid process-coating-template-grid">
          <WetProcessTemplateDropdown
            disabled={false}
            locked={Boolean(lockedFields.processTemplate)}
            value={form.processTemplate}
            onChange={(value) => onChange("processTemplate", value)}
          />
        </div>
      </section>

      <section className="process-coating-section">
        <h4>通用信息</h4>
        <div className="process-grid process-coating-grid">
          <EditableWetProcessTextField
            disabled={disabled}
            field="equipmentName"
            form={form}
            label="设备名称"
            locked={Boolean(lockedFields.equipmentName)}
            onChange={onChange}
          />
          <EditableWetProcessTextField
            disabled={disabled}
            field="operator"
            form={form}
            label="操作人"
            locked={Boolean(lockedFields.operator)}
            placeholder="请输入姓名"
            onChange={onChange}
          />
          <EditableWetProcessTextField
            disabled={disabled}
            field="inTime"
            form={form}
            label="进样时间"
            locked={Boolean(lockedFields.inTime)}
            placeholder="YYYY-MM-DD HH:mm"
            onChange={onChange}
          />
          <EditableWetProcessTextField
            disabled={disabled}
            field="outTime"
            form={form}
            label="出样时间"
            locked={Boolean(lockedFields.outTime)}
            placeholder="YYYY-MM-DD HH:mm"
            onChange={onChange}
          />
        </div>
      </section>

      <section className="process-coating-section">
        <h4>{form.processTemplate || currentTemplate.name} 工艺参数</h4>
        <div className="process-grid process-coating-grid process-coating-param-grid">
          {parameterFields.map((parameter) => (
            <WetProcessParameterField
              disabled={disabled}
              key={`${currentTemplate.name}-${parameter.key}-${parameter.label}`}
              label={parameter.label}
              locked={Boolean(lockedFields.parameterValues?.[parameter.key])}
              unit={parameter.unit}
              value={form.parameterValues[parameter.key] ?? ""}
              onChange={(value) => onChange("parameterValues", { ...form.parameterValues, [parameter.key]: value })}
            />
          ))}
        </div>
      </section>

      <section className="process-coating-summary" aria-label="湿法填写摘要">
        <strong>当前工艺：{form.processTemplate || "-"}</strong>
        <strong>模板字段：{parameterCount}项</strong>
        <strong>已填写：{filledCount}项</strong>
        <strong>状态：{status}</strong>
      </section>
    </div>
  );
}

export function ProcessRecordPage() {
  const [activeStage, setActiveStage] = useState<ProcessStage>("光刻");
  const lookupRef = useRef<HTMLLabelElement | null>(null);
  const sampleSuggestionRequestRef = useRef(0);
  const [query, setQuery] = useState("");
  const [selectedSample, setSelectedSample] = useState<Sample | null>(null);
  const [savedRecord, setSavedRecord] = useState<ProcessRecord | null>(null);
  const [waferForm, setWaferForm] = useState<WaferForm>(defaultWaferForm);
  const [lithographyForm, setLithographyForm] = useState<LithographyForm>(defaultLithographyForm);
  const [lithographySectionState, setLithographySectionState] = useState<LithographySectionState>(
    defaultLithographySectionState,
  );
  const [detectionForm, setDetectionForm] = useState<DetectionForm>(defaultDetectionForm);
  const [detectionLocked, setDetectionLocked] = useState(false);
  const [coatingForm, setCoatingForm] = useState<CoatingForm>(defaultCoatingForm);
  const [coatingFieldLocks, setCoatingFieldLocks] = useState<CoatingFieldLocks>({});
  const [etchingForm, setEtchingForm] = useState<EtchingForm>(defaultEtchingForm);
  const [etchingFieldLocks, setEtchingFieldLocks] = useState<EtchingFieldLocks>({});
  const [wetProcessForm, setWetProcessForm] = useState<WetProcessForm>(defaultWetProcessForm);
  const [wetProcessFieldLocks, setWetProcessFieldLocks] = useState<WetProcessFieldLocks>({});
  const [sampleSuggestions, setSampleSuggestions] = useState<Sample[]>([]);
  const [sampleSuggestionsOpen, setSampleSuggestionsOpen] = useState(false);
  const [sampleSuggesting, setSampleSuggesting] = useState(false);
  const [stageReloadToken, setStageReloadToken] = useState(0);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [confirmedLayerName, setConfirmedLayerName] = useState("默认图层");

  const isLithography = activeStage === "光刻";
  const isDetection = activeStage === "检测";
  const isEtching = activeStage === "刻蚀";
  const isCoating = activeStage === "镀膜";
  const isWetProcess = activeStage === "湿法";
  const currentRecordLabel = isLithography
    ? "光刻信息"
    : isDetection
      ? "检测信息"
      : isEtching
        ? "刻蚀信息"
        : isCoating
          ? "镀膜信息"
          : isWetProcess
            ? "湿法信息"
            : "发料信息";

  const currentLayerName = normalizeRecordLayer(
    isLithography
      ? lithographyForm.layer
      : isDetection
        ? detectionForm.layer
        : isEtching
        ? etchingForm.layer
        : isCoating
          ? coatingForm.layer
          : isWetProcess
            ? wetProcessForm.layer
            : "",
  );
  const savedRecordMatchesCurrentScope =
    Boolean(selectedSample && savedRecord) &&
    savedRecord?.sample.id === selectedSample?.id &&
    savedRecord?.stage === activeStage &&
    normalizeRecordLayer(savedRecord?.layer_name || "") === currentLayerName &&
    (savedRecord?.record_no || 1) === 1;

  function commitLayer(value: string) {
    const nextLayer = value.trim();
    setConfirmedLayerName(nextLayer ? normalizeRecordLayer(nextLayer) : "");
  }

  function getLayerByStage(stage: ProcessStage) {
    if (stage === "光刻") {
      return normalizeRecordLayer(lithographyForm.layer);
    }
    if (stage === "检测") {
      return normalizeRecordLayer(detectionForm.layer);
    }
    if (stage === "刻蚀") {
      return normalizeRecordLayer(etchingForm.layer);
    }
    if (stage === "镀膜") {
      return normalizeRecordLayer(coatingForm.layer);
    }
    if (stage === "湿法") {
      return normalizeRecordLayer(wetProcessForm.layer);
    }
    return "默认图层";
  }

  function resetFormByStage(stage: ProcessStage, layerName = "默认图层") {
    setSavedRecord(null);
    if (stage === "发料") {
      setWaferForm(defaultWaferForm);
      return;
    }
    if (stage === "光刻") {
      setLithographyForm({ ...defaultLithographyForm, layer: layerName === "默认图层" ? "" : layerName });
      setLithographySectionState(defaultLithographySectionState);
      return;
    }
    if (stage === "检测") {
      setDetectionForm({ ...defaultDetectionForm, layer: layerName === "默认图层" ? "" : layerName });
      setDetectionLocked(false);
      return;
    }
    if (stage === "刻蚀") {
      setEtchingForm({ ...defaultEtchingForm, layer: layerName === "默认图层" ? "" : layerName });
      setEtchingFieldLocks({});
      return;
    }
    if (stage === "镀膜") {
      setCoatingForm({ ...defaultCoatingForm, layer: layerName === "默认图层" ? "" : layerName });
      setCoatingFieldLocks({});
      return;
    }
    if (stage === "湿法") {
      setWetProcessForm({ ...defaultWetProcessForm, layer: layerName === "默认图层" ? "" : layerName });
      setWetProcessFieldLocks({});
    }
  }

  function applyRecordByStage(stage: ProcessStage, record: ProcessRecord | null, fallbackLayerName = "默认图层") {
    setSavedRecord(record);
    if (stage === "发料") {
      setWaferForm(fillWaferRecord(record));
      return;
    }
    if (stage === "光刻") {
      const nextLithographyForm = record
        ? fillLithographyRecord(record)
        : { ...defaultLithographyForm, layer: fallbackLayerName === "默认图层" ? "" : fallbackLayerName };
      setLithographyForm(nextLithographyForm);
      setLithographySectionState(record ? fillLithographySectionState(record, nextLithographyForm) : defaultLithographySectionState);
      return;
    }
    if (stage === "检测") {
      setDetectionForm(
        record ? fillDetectionRecord(record) : { ...defaultDetectionForm, layer: fallbackLayerName === "默认图层" ? "" : fallbackLayerName },
      );
      setDetectionLocked(record ? fillDetectionLocked(record) : false);
      return;
    }
    if (stage === "刻蚀") {
      setEtchingForm(
        record ? fillEtchingRecord(record) : { ...defaultEtchingForm, layer: fallbackLayerName === "默认图层" ? "" : fallbackLayerName },
      );
      setEtchingFieldLocks(record ? getEtchingFieldLocks(record) : {});
      return;
    }
    if (stage === "镀膜") {
      setCoatingForm(
        record ? fillCoatingRecord(record) : { ...defaultCoatingForm, layer: fallbackLayerName === "默认图层" ? "" : fallbackLayerName },
      );
      setCoatingFieldLocks(record ? getCoatingFieldLocks(record) : {});
      return;
    }
    if (stage === "湿法") {
      setWetProcessForm(
        record
          ? fillWetProcessRecord(record)
          : { ...defaultWetProcessForm, layer: fallbackLayerName === "默认图层" ? "" : fallbackLayerName },
      );
      setWetProcessFieldLocks(record ? getWetProcessFieldLocks(record) : {});
      return;
    }
    resetFormByStage(stage, fallbackLayerName);
  }

  const statusText = useMemo(() => {
    if (selectedSample) {
      const recordStatus = savedRecord?.status === "submitted" ? "已提交" : "待提交";
      const infoLabel = isLithography
        ? "光刻信息"
        : isDetection
          ? "检测信息"
          : isEtching
            ? "刻蚀信息"
            : isCoating
              ? "镀膜信息"
              : isWetProcess
                ? "湿法信息"
                : "硅片信息";
      return `当前：${activeStage}段 · 已找到建档样品 · ${recordStatus}${infoLabel}`;
    }
    return `当前：${activeStage}段 · 请输入样品编号查询`;
  }, [activeStage, isCoating, isDetection, isEtching, isLithography, isWetProcess, savedRecord?.status, selectedSample]);

  async function loadSampleSuggestions(keyword: string, openWhenDone = false) {
    const requestId = sampleSuggestionRequestRef.current + 1;
    sampleSuggestionRequestRef.current = requestId;
    setSampleSuggesting(true);
    try {
      const rows = await getProcessSampleSuggestions(keyword, activeStage);
      if (requestId !== sampleSuggestionRequestRef.current) {
        return;
      }
      setSampleSuggestions(rows);
      if (openWhenDone) {
        setSampleSuggestionsOpen(rows.length > 0);
      }
    } catch {
      if (requestId !== sampleSuggestionRequestRef.current) {
        return;
      }
      setSampleSuggestions([]);
      if (openWhenDone) {
        setSampleSuggestionsOpen(false);
      }
    } finally {
      if (requestId === sampleSuggestionRequestRef.current) {
        setSampleSuggesting(false);
      }
    }
  }

  useEffect(() => {
    const keyword = query.trim();
    let cancelled = false;
    setSampleSuggesting(true);
    const timer = window.setTimeout(async () => {
      const requestId = sampleSuggestionRequestRef.current + 1;
      sampleSuggestionRequestRef.current = requestId;
      try {
        const rows = await getProcessSampleSuggestions(keyword, activeStage);
        if (!cancelled && requestId === sampleSuggestionRequestRef.current) {
          setSampleSuggestions(rows);
        }
      } catch {
        if (!cancelled && requestId === sampleSuggestionRequestRef.current) {
          setSampleSuggestions([]);
          setSampleSuggestionsOpen(false);
        }
      } finally {
        if (!cancelled && requestId === sampleSuggestionRequestRef.current) {
          setSampleSuggesting(false);
        }
      }
    }, keyword ? 220 : 80);

    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [activeStage, query]);

  useEffect(() => {
    function handlePointerDown(event: PointerEvent) {
      if (lookupRef.current && !lookupRef.current.contains(event.target as Node)) {
        setSampleSuggestionsOpen(false);
      }
    }

    window.addEventListener("pointerdown", handlePointerDown);
    return () => window.removeEventListener("pointerdown", handlePointerDown);
  }, []);

  useEffect(() => {
    if (!selectedSample) {
      setSavedRecord(null);
      return;
    }

    let cancelled = false;
    setLoading(true);
    setError("");
    setMessage("");

    const layerName = confirmedLayerName;
    if (activeStage !== "发料" && !layerName) {
      resetFormByStage(activeStage, "默认图层");
      setLoading(false);
      return;
    }
    lookupProcessSample(selectedSample.sample_display_code || selectedSample.sample_uid || selectedSample.name, activeStage, {
      layer_name: layerName,
      record_no: 1,
    })
      .then((result) => {
        if (cancelled) {
          return;
        }
        setSelectedSample(result.sample);
        applyRecordByStage(activeStage, result.record, layerName);
      })
      .catch((lookupError) => {
        if (!cancelled) {
          resetFormByStage(activeStage, layerName);
          setError(lookupError instanceof Error ? lookupError.message : "样品关联失败");
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [activeStage, confirmedLayerName, selectedSample?.id, stageReloadToken]);

  async function applySample(sample: Sample) {
    setQuery(sample.sample_display_code || sample.sample_uid || sample.name);
    setSampleSuggestionsOpen(false);
    setLoading(true);
    setError("");
    setMessage("");
    try {
      const layerName = getLayerByStage(activeStage);
      setConfirmedLayerName(layerName);
      const result = await lookupProcessSample(sample.sample_display_code || sample.sample_uid, activeStage, {
        layer_name: layerName,
        record_no: 1,
      });
      setSelectedSample(result.sample);
      applyRecordByStage(activeStage, result.record, layerName);
      setMessage(`已关联建档样品，${activeStage}信息将保存到该样品下。`);
    } catch (lookupError) {
      setSelectedSample(sample);
      setSavedRecord(null);
      setWaferForm(defaultWaferForm);
      setLithographyForm(defaultLithographyForm);
      setLithographySectionState(defaultLithographySectionState);
      setDetectionForm(defaultDetectionForm);
      setDetectionLocked(false);
      setCoatingForm(defaultCoatingForm);
      setCoatingFieldLocks({});
      setEtchingForm(defaultEtchingForm);
      setEtchingFieldLocks({});
      setWetProcessForm(defaultWetProcessForm);
      setWetProcessFieldLocks({});
      setError(lookupError instanceof Error ? lookupError.message : "样品关联失败");
    } finally {
      setLoading(false);
    }
  }

  async function handleLookup() {
    setLoading(true);
    setError("");
    setMessage("");
    setSampleSuggestionsOpen(false);
    try {
      const layerName = getLayerByStage(activeStage);
      setConfirmedLayerName(layerName);
      const result = await lookupProcessSample(query, activeStage, {
        layer_name: layerName,
        record_no: 1,
      });
      setSelectedSample(result.sample);
      applyRecordByStage(activeStage, result.record, layerName);
      setMessage(`已关联建档样品，${activeStage}信息将保存到该样品下。`);
    } catch (lookupError) {
      setSelectedSample(null);
      setSavedRecord(null);
      setError(lookupError instanceof Error ? lookupError.message : "样品查询失败");
    } finally {
      setLoading(false);
    }
  }

  async function handleSave(status: ProcessRecordStatus) {
    if (!selectedSample) {
      setError("请先查询并关联建档样品");
      return;
    }

    setSaving(true);
    setError("");
    setMessage("");
    try {
      setConfirmedLayerName(currentLayerName);
      const processDetails = isLithography
        ? {
            ...lithographyForm,
            sectionState: lithographySectionState,
          }
        : isDetection
          ? {
              ...detectionForm,
              result: getDetectionResult(detectionForm),
              locked: detectionLocked,
            }
          : isEtching
            ? {
                ...etchingForm,
                stageStatus: getEtchingStageStatus(etchingForm),
              }
            : isCoating
              ? {
                  ...coatingForm,
                  stageStatus: getCoatingStageStatus(coatingForm),
                }
              : {
                  ...wetProcessForm,
                  stageStatus: getWetProcessStageStatus(wetProcessForm),
                };
      const record = await saveProcessRecord({
        ...(savedRecordMatchesCurrentScope ? { id: savedRecord?.id } : {}),
        sample_id: selectedSample.id,
        stage: activeStage,
        layer_name: currentLayerName,
        record_no: 1,
        record_label: "第1次记录",
        status,
        ...(isLithography || isDetection || isEtching || isCoating || isWetProcess
          ? {
              substrate_type: "",
              resistance_type: "",
              wafer_thickness: "",
              details: processDetails as unknown as Record<string, unknown>,
            }
          : waferForm),
      });
      setSavedRecord(record);
      if (isDetection && status === "submitted") {
        setDetectionLocked(true);
      }
      if (isCoating) {
        setCoatingFieldLocks(getCoatingFieldLocks(record));
      }
      if (isEtching) {
        setEtchingFieldLocks(getEtchingFieldLocks(record));
      }
      if (isWetProcess) {
        setWetProcessFieldLocks(getWetProcessFieldLocks(record));
      }
      setMessage(status === "submitted" ? `${activeStage}信息已提交。` : "草稿已保存。");
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : "保存失败");
    } finally {
      setSaving(false);
    }
  }

  async function saveLithographyDraft(
    nextSectionState?: LithographySectionState,
    nextLithographyForm: LithographyForm = lithographyForm,
  ) {
    if (!selectedSample) {
      setError("请先查询并关联建档样品");
      return null;
    }

    const details = {
      ...nextLithographyForm,
      sectionState: nextSectionState ?? lithographySectionState,
    };

    setSaving(true);
    setError("");
    setMessage("");
    try {
      setConfirmedLayerName(normalizeRecordLayer(nextLithographyForm.layer));
      const record = await saveProcessRecord({
        ...(savedRecordMatchesCurrentScope && activeStage === "光刻" ? { id: savedRecord?.id } : {}),
        sample_id: selectedSample.id,
        stage: "光刻",
        layer_name: normalizeRecordLayer(nextLithographyForm.layer),
        record_no: 1,
        record_label: "第1次记录",
        status: "draft",
        substrate_type: "",
        resistance_type: "",
        wafer_thickness: "",
        details: details as unknown as Record<string, unknown>,
      });
      setSavedRecord(record);
      setMessage("草稿已保存。");
      return record;
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : "保存失败");
      return null;
    } finally {
      setSaving(false);
    }
  }

  async function handleSaveLithographySection(section: keyof LithographySectionState) {
    const nextSectionState: LithographySectionState =
      section === "coat"
        ? { coat: "done", exposure: "editing", develop: "pending" }
        : section === "exposure"
          ? { coat: "done", exposure: "done", develop: "editing" }
          : { coat: "done", exposure: "done", develop: "done" };
    setLithographySectionState(nextSectionState);
    const record = await saveLithographyDraft(nextSectionState);
    if (!record) {
      setLithographySectionState(lithographySectionState);
    }
  }

  function handleEditLithographySection(section: keyof LithographySectionState) {
    setLithographyForm((current) => (section === "develop" ? { ...current, skippedDevelop: false } : current));
    setLithographySectionState((current) => ({
      ...current,
      [section]: "editing",
    }));
  }

  function updateLithography<K extends keyof LithographyForm>(key: K, value: LithographyForm[K]) {
    if (key === "layer") {
      const nextLayer = normalizeRecordLayer(String(value));
      setLithographyForm({ ...defaultLithographyForm, layer: nextLayer === "默认图层" ? "" : String(value) });
      if (nextLayer !== confirmedLayerName) {
        setSavedRecord(null);
        setLithographySectionState(defaultLithographySectionState);
      }
      return;
    }
    setLithographyForm((current) => ({ ...current, [key]: value }));
  }

  function updateDetection<K extends keyof Omit<DetectionForm, "points">>(key: K, value: DetectionForm[K]) {
    setDetectionForm((current) => {
      if (key === "layer") {
        const nextLayer = normalizeRecordLayer(String(value));
        if (nextLayer !== confirmedLayerName) {
          setSavedRecord(null);
          setDetectionLocked(false);
        }
        return { ...defaultDetectionForm, layer: nextLayer === "默认图层" ? "" : String(value) };
      }
      if (key === "tool") {
        const template = detectionMachineTemplates.find((item) => item.name === value);
        return {
          ...current,
          tool: value,
          project: template?.projectOptions.includes(current.project) ? current.project : "",
          unit: "",
          points: { ...defaultDetectionForm.points },
          remark: "",
        };
      }
      return { ...current, [key]: value };
    });
  }

  function updateDetectionPoint(key: DetectionPointKey, value: string) {
    setDetectionForm((current) => ({
      ...current,
      points: {
        ...current.points,
        [key]: value,
      },
    }));
  }

  function updateCoating<K extends keyof CoatingForm>(key: K, value: CoatingForm[K]) {
    if (key === "layer") {
      const nextLayer = normalizeRecordLayer(String(value));
      setCoatingForm({ ...defaultCoatingForm, layer: nextLayer === "默认图层" ? "" : String(value) });
      if (nextLayer !== confirmedLayerName) {
        setSavedRecord(null);
        setCoatingFieldLocks({});
      }
      return;
    }
    if (key === "machineTemplate") {
      setCoatingForm((current) => ({ ...defaultCoatingForm, layer: current.layer, machineTemplate: String(value) }));
      setCoatingFieldLocks({});
      return;
    }
    setCoatingForm((current) => ({ ...current, [key]: value }));
  }

  function updateEtching(key: keyof EtchingForm, value: string) {
    if (key === "layer") {
      const nextLayer = normalizeRecordLayer(value);
      setEtchingForm({ ...defaultEtchingForm, layer: nextLayer === "默认图层" ? "" : value });
      if (nextLayer !== confirmedLayerName) {
        setSavedRecord(null);
        setEtchingFieldLocks({});
      }
      return;
    }
    if (key === "machineTemplate") {
      setEtchingForm((current) => ({ ...defaultEtchingForm, layer: current.layer, machineTemplate: value }));
      setEtchingFieldLocks({});
      return;
    }
    setEtchingForm((current) => ({ ...current, [key]: value }));
  }

  function updateWetProcess<K extends keyof WetProcessForm>(key: K, value: WetProcessForm[K]) {
    if (key === "layer") {
      const nextLayer = normalizeRecordLayer(String(value));
      setWetProcessForm({ ...defaultWetProcessForm, layer: nextLayer === "默认图层" ? "" : String(value) });
      if (nextLayer !== confirmedLayerName) {
        setSavedRecord(null);
        setWetProcessFieldLocks({});
      }
      return;
    }
    if (key === "processTemplate") {
      setWetProcessForm((current) => ({
        ...current,
        processTemplate: value as WetProcessName,
        parameterValues: {},
      }));
      setWetProcessFieldLocks((current) => ({ ...current, parameterValues: {} }));
      return;
    }
    setWetProcessForm((current) => ({ ...current, [key]: value }));
  }

  function handleStageChange(stage: ProcessStage) {
    setActiveStage(stage);
    setQuery("");
    setSelectedSample(null);
    setError("");
    setMessage("");
    const layerName = stage === "发料" ? "默认图层" : "";
    resetFormByStage(stage, layerName || "默认图层");
    setConfirmedLayerName(layerName);
    setStageReloadToken((current) => current + 1);
  }

  return (
    <section className="process-record-page">
      <div className="process-stage-tabs" aria-label="工艺段">
        {processTabs.map((tab) => (
          <button
            className={`process-stage-tab${tab === activeStage ? " active" : ""}`}
            key={tab}
            type="button"
            onClick={() => handleStageChange(tab)}
          >
            {tab}
          </button>
        ))}
        <span className="process-stage-status">{statusText}</span>
      </div>

      <section className="panel process-lookup-panel">
        <header className="process-lookup-header">
          <h3>样品查找</h3>
          <span>查询建档样品，提交内容将关联到该样品下</span>
        </header>
        <div className="process-lookup-form process-lookup-form-compact">
          <label className="process-record-field process-sample-combobox" ref={lookupRef}>
            <span>样品编号</span>
            <input
              autoComplete="off"
              value={query}
              onBlur={() => window.setTimeout(() => setSampleSuggestionsOpen(false), 120)}
              onChange={(event) => {
                setQuery(event.target.value);
                setSelectedSample(null);
                setSavedRecord(null);
                setMessage("");
                setError("");
                setSampleSuggestionsOpen(true);
              }}
              onFocus={() => {
                setSampleSuggestionsOpen(true);
                void loadSampleSuggestions(query.trim(), true);
              }}
            />
            {sampleSuggestionsOpen && (
              <SuggestionPopover
                loading={sampleSuggesting}
                suggestions={sampleSuggestions.map((sample) => sample.sample_display_code || sample.name)}
                onPick={(value) => {
                  const sample = sampleSuggestions.find(
                    (item) => (item.sample_display_code || item.name) === value,
                  );
                  if (sample) {
                    void applySample(sample);
                  }
                }}
              />
            )}
          </label>
          <ReadonlyField label="样品UID" value={selectedSample?.sample_uid || "查询后自动带出"} />
          <div className="process-lookup-actions">
            <span className="process-button-label-spacer" aria-hidden="true" />
            <div className="process-lookup-button-row">
              <button disabled={loading} type="button" onClick={handleLookup}>
                {loading ? "查询中" : "查询样品"}
              </button>
            </div>
          </div>
        </div>
        {(message || error) && (
          <p className={`process-inline-message${error ? " error" : ""}`}>{error || message}</p>
        )}
      </section>

      <section className="panel process-entry-panel">
        <header className="process-entry-header">
          <h3>{currentRecordLabel}</h3>
          <span>
            关联样品：{sampleLabel(selectedSample)} / {selectedSample?.sample_uid || "未查询"}
          </span>
        </header>

        {isLithography ? (
          <LithographyFormView
            disabled={!selectedSample || saving}
            form={lithographyForm}
            sampleId={selectedSample?.id}
            sectionState={lithographySectionState}
            onChange={updateLithography}
            onLayerCommit={commitLayer}
            onEditSection={handleEditLithographySection}
            onSaveSection={handleSaveLithographySection}
          />
        ) : isDetection ? (
          <DetectionFormView
            disabled={!selectedSample || saving}
            form={detectionForm}
            locked={detectionLocked}
            sampleId={selectedSample?.id}
            onChange={updateDetection}
            onLayerCommit={commitLayer}
            onPointChange={updateDetectionPoint}
          />
        ) : isCoating ? (
          <CoatingFormView
            disabled={!selectedSample || saving}
            form={coatingForm}
            lockedFields={coatingFieldLocks}
            sampleId={selectedSample?.id}
            onChange={updateCoating}
            onLayerCommit={commitLayer}
          />
        ) : isWetProcess ? (
          <WetProcessFormView
            disabled={!selectedSample || saving}
            form={wetProcessForm}
            lockedFields={wetProcessFieldLocks}
            sampleId={selectedSample?.id}
            onChange={updateWetProcess}
            onLayerCommit={commitLayer}
          />
        ) : isEtching ? (
          <EtchingFormView
            disabled={!selectedSample || saving}
            form={etchingForm}
            lockedFields={etchingFieldLocks}
            sampleId={selectedSample?.id}
            onChange={updateEtching}
            onLayerCommit={commitLayer}
          />
        ) : (
          <div className="process-entry-body">
            <h4>硅片信息</h4>
            <div className="process-grid process-wafer-grid">
              {waferFields.map((field) => (
                <WaferSuggestField
                  disabled={!selectedSample}
                  field={field.key}
                  key={field.key}
                  label={field.label}
                  placeholder={field.placeholder}
                  value={waferForm[field.key]}
                  onChange={(value) => setWaferForm((current) => ({ ...current, [field.key]: value }))}
                />
              ))}
            </div>
          </div>
        )}

        <footer className="process-entry-footer">
          <span>
            {savedRecord
              ? `最后保存 ${new Date(savedRecord.updated_at).toLocaleTimeString([], {
                  hour: "2-digit",
                  minute: "2-digit",
                })}`
              : `查询样品后可保存${activeStage}信息；已完成步骤会锁定为只读状态`}
          </span>
          <div className="process-footer-actions">
            <button
              className="ghost-button"
              disabled={saving || !selectedSample}
              type="button"
              onClick={() => handleSave("draft")}
            >
              保存草稿
            </button>
            <button disabled={saving || !selectedSample} type="button" onClick={() => handleSave("submitted")}>
              提交{activeStage}段
            </button>
          </div>
        </footer>
      </section>
    </section>
  );
}
