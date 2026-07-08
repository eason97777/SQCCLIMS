type ProcessingTypeSelectorProps = {
  selectedType: "stats" | "qc" | "normalize";
  onChange: (value: "stats" | "qc" | "normalize") => void;
};

export function ProcessingTypeSelector({
  selectedType,
  onChange,
}: ProcessingTypeSelectorProps) {
  return (
    <fieldset className="method-group full">
      <legend>分析方法</legend>
      <label>
        <input
          type="radio"
          name="method"
          checked={selectedType === "stats"}
          onChange={() => onChange("stats")}
        />
        统计汇总
      </label>
      <label>
        <input
          type="radio"
          name="method"
          checked={selectedType === "qc"}
          onChange={() => onChange("qc")}
        />
        质控判定
      </label>
      <label>
        <input
          type="radio"
          name="method"
          checked={selectedType === "normalize"}
          onChange={() => onChange("normalize")}
        />
        归一化
      </label>
    </fieldset>
  );
}
