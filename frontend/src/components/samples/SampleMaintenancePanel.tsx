import type { ReactNode } from "react";
import { useEffect, useMemo, useRef, useState } from "react";
import type { SampleMaintenanceOptions } from "../../stores/sampleMaintenanceStore";
import { includesNormalizedText } from "../../utils/searchUtils";
import {
  normalizeCodeText,
  normalizeWhitespace,
} from "../../utils/textNormalize";

type MaintenanceField = keyof SampleMaintenanceOptions;

type MaintenanceFieldConfig = {
  key: MaintenanceField;
  label: string;
  placeholder: string;
  normalize: (value: string) => string;
};

const MAINTENANCE_FIELDS: MaintenanceFieldConfig[] = [
  {
    key: "sampleCodes",
    label: "项目编号",
    placeholder: "输入新的项目编号候选项",
    normalize: normalizeCodeText,
  },
  {
    key: "sampleNames",
    label: "样品名称",
    placeholder: "输入新的样品名称候选项",
    normalize: normalizeWhitespace,
  },
  {
    key: "processTypes",
    label: "工艺类型",
    placeholder: "输入新的工艺类型候选项",
    normalize: normalizeWhitespace,
  },
  {
    key: "sampleSeqs",
    label: "样品序号",
    placeholder: "输入新的样品序号候选项",
    normalize: normalizeCodeText,
  },
  {
    key: "owners",
    label: "负责人",
    placeholder: "输入新的负责人候选项",
    normalize: normalizeWhitespace,
  },
];

type SampleMaintenancePanelProps = {
  actions?: ReactNode;
  options: SampleMaintenanceOptions;
  onAddOption: (field: MaintenanceField, value: string) => void;
  onRemoveOption: (field: MaintenanceField, value: string) => void;
};

export function SampleMaintenancePanel({
  actions,
  options,
  onAddOption,
  onRemoveOption,
}: SampleMaintenancePanelProps) {
  const rootRef = useRef<HTMLElement | null>(null);
  const [expanded, setExpanded] = useState(false);
  const [drafts, setDrafts] = useState<Record<MaintenanceField, string>>({
    sampleCodes: "",
    sampleNames: "",
    processTypes: "",
    sampleSeqs: "",
    owners: "",
  });
  const [openField, setOpenField] = useState<MaintenanceField | null>(null);

  useEffect(() => {
    function handlePointerDown(event: MouseEvent) {
      if (!rootRef.current?.contains(event.target as Node)) {
        setOpenField(null);
        setExpanded(false);
      }
    }

    document.addEventListener("mousedown", handlePointerDown);
    return () => document.removeEventListener("mousedown", handlePointerDown);
  }, []);

  const filteredOptions = useMemo(() => {
    if (!openField) {
      return [];
    }

    const keyword = drafts[openField];
    return options[openField].filter((value) =>
      includesNormalizedText(value, keyword),
    );
  }, [drafts, openField, options]);

  function updateDraft(field: MaintenanceField, value: string) {
    setDrafts((current) => ({
      ...current,
      [field]: value,
    }));
    setOpenField(field);
  }

  function handleAdd(field: MaintenanceField, normalize: (value: string) => string) {
    const value = normalize(drafts[field]);
    if (!value || options[field].includes(value)) {
      return;
    }

    onAddOption(field, value);
    setDrafts((current) => ({ ...current, [field]: "" }));
    setOpenField(null);
  }

  function handleSelect(field: MaintenanceField, value: string) {
    setDrafts((current) => ({ ...current, [field]: value }));
    setOpenField(null);
  }

  function handleRemove(field: MaintenanceField, value: string) {
    const confirmed = window.confirm(
      `确认删除候选项「${value}」？这不会删除已经建档的样品。`,
    );
    if (!confirmed) {
      return;
    }

    onRemoveOption(field, value);
  }

  return (
    <section className="panel sample-maintenance-panel sample-maintenance-collapsible panel-section-spacing" ref={rootRef}>
      <button
        className="sample-maintenance-toggle"
        type="button"
        aria-expanded={expanded}
        onClick={() => setExpanded((current) => !current)}
      >
        <div>
          <h3>基础候选项维护</h3>
          <p className="subtle-text">
            维护项目编号、样品名称、工艺类型、样品序号、负责人候选项，建档时可按需调用。
          </p>
        </div>
        <span className="sample-maintenance-chevron">{expanded ? "收起" : "展开"}</span>
      </button>
      {expanded ? (
        <>
          {actions ? <div className="toolbar maintenance-actions">{actions}</div> : null}
          <div className="maintenance-grid">
            {MAINTENANCE_FIELDS.map((field) => {
              const isOpen = openField === field.key;

              return (
                <div className="maintenance-card" key={field.key}>
                  <label htmlFor={`${field.key}-draft`}>{field.label}</label>
                  <div className="maintenance-add-row">
                    <div className="maintenance-input-area">
                      <input
                        id={`${field.key}-draft`}
                        value={drafts[field.key]}
                        placeholder={field.placeholder}
                        onFocus={() => setOpenField(field.key)}
                        onChange={(event) => updateDraft(field.key, event.target.value)}
                      />
                      {isOpen ? (
                        <div className="maintenance-candidate-dropdown">
                          {filteredOptions.length === 0 ? (
                            <div className="option-manager-empty">暂无候选项</div>
                          ) : null}
                          {filteredOptions.map((value) => (
                            <div className="maintenance-candidate-row" key={value}>
                              <button
                                className="candidate-text-button"
                                type="button"
                                onMouseDown={(event) => event.preventDefault()}
                                onClick={() => handleSelect(field.key, value)}
                              >
                                {value}
                              </button>
                              <button
                                className="danger-button candidate-delete-button"
                                type="button"
                                onMouseDown={(event) => event.preventDefault()}
                                onClick={() => handleRemove(field.key, value)}
                              >
                                删除
                              </button>
                            </div>
                          ))}
                        </div>
                      ) : null}
                    </div>
                    <button
                      type="button"
                      onClick={() => handleAdd(field.key, field.normalize)}
                    >
                      添加
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </>
      ) : null}
    </section>
  );
}
