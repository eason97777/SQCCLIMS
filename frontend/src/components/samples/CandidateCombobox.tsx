import { useEffect, useMemo, useRef, useState } from "react";
import { includesNormalizedText } from "../../utils/searchUtils";

type CandidateComboboxProps = {
  fieldKey: string;
  value: string;
  options: string[];
  placeholder?: string;
  required?: boolean;
  onChange: (value: string) => void;
};

export function CandidateCombobox({
  fieldKey,
  value,
  options,
  placeholder,
  required = false,
  onChange,
}: CandidateComboboxProps) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement | null>(null);

  const filteredOptions = useMemo(() => {
    const uniqueOptions = Array.from(new Set(options.filter(Boolean)));
    if (!value) {
      return uniqueOptions;
    }

    return uniqueOptions.filter((option) => includesNormalizedText(option, value));
  }, [options, value]);

  useEffect(() => {
    function handlePointerDown(event: MouseEvent) {
      if (!rootRef.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    }

    document.addEventListener("mousedown", handlePointerDown);
    return () => document.removeEventListener("mousedown", handlePointerDown);
  }, []);

  function handleSelect(nextValue: string) {
    onChange(nextValue);
    setOpen(false);
  }

  return (
    <div className="candidate-combobox" ref={rootRef}>
      <input
        name={fieldKey}
        required={required}
        value={value}
        placeholder={placeholder}
        autoComplete="off"
        onFocus={() => setOpen(true)}
        onChange={(event) => {
          onChange(event.target.value);
          setOpen(true);
        }}
      />
      {open ? (
        <div className="candidate-dropdown">
          {filteredOptions.length === 0 ? (
            <div className="candidate-empty">暂无候选项</div>
          ) : null}
          {filteredOptions.map((option) => (
            <button
              className="candidate-option"
              key={option}
              type="button"
              onMouseDown={(event) => event.preventDefault()}
              onClick={() => handleSelect(option)}
            >
              {option}
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}

