export const NAV_ITEMS = [
  { path: "/", label: "总览" },
  { path: "/samples", label: "样品信息库" },
  { path: "/process-records", label: "工艺记录" },
  { path: "/raw-data", label: "原始数据" },
  { path: "/characterization", label: "表征数据中心" },
  { path: "/test-data", label: "测试数据库" },
  { path: "/performance-datasets", label: "性能数据集" },
  { path: "/processing", label: "数据处理" },
] as const;

export const VIEW_META: Record<string, { title: string; eyebrow: string }> = {
  "/": { title: "总览", eyebrow: "实验室数据资产" },
  "/samples": { title: "样品信息库", eyebrow: "Sample Base" },
  "/samples/maintenance": {
    title: "样品建档维护",
    eyebrow: "Sample Maintenance",
  },
  "/raw-data": {
    title: "原始数据",
    eyebrow: "Raw Data",
  },
  "/process-records": {
    title: "工艺记录",
    eyebrow: "Process Record",
  },
  "/characterization": {
    title: "表征数据中心",
    eyebrow: "Characterization Center",
  },
  "/test-data": { title: "测试数据库", eyebrow: "Data Base" },
  "/performance-datasets": {
    title: "性能数据集",
    eyebrow: "Performance Datasets",
  },
  "/data": { title: "测试数据库", eyebrow: "Data Base" },
  "/performance": { title: "性能数据集", eyebrow: "Performance Datasets" },
  "/processing": { title: "数据处理模块", eyebrow: "Processing" },
};

export const SAMPLE_STATUS_OPTIONS = [
  "待测试",
  "测试中",
  "已完成",
  "已归档",
] as const;

export const RAW_DATA_TYPE_OPTIONS = [
  { value: "resistance", label: "电阻测试数据", category: "electrical" },
  { value: "cd_sem", label: "CD_SEM", category: "metrology" },
  { value: "sem_image", label: "SEM / 图片类数据", category: "image" },
  { value: "xps", label: "XPS / 光谱类数据", category: "spectrum" },
  { value: "xrd", label: "XRD 数据", category: "spectrum" },
  { value: "afm", label: "AFM 数据", category: "metrology" },
  { value: "report", label: "报告文件", category: "report" },
  { value: "instrument_folder", label: "仪器原始目录", category: "folder" },
  { value: "generic_file", label: "通用文件", category: "other" },
] as const;
