import { useEffect, useRef, useState } from "react";

type SelectComboboxProps = {
  name?: string;
  value: string;
  options: readonly (string | { label: string; value: string })[];
  placeholder?: string;
  onChange: (value: string) => void;
};

export function SelectCombobox({
  name,
  value,
  options,
  placeholder = "请选择",
  onChange,
}: SelectComboboxProps) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement | null>(null);
  const normalizedOptions = options.map((option) =>
    typeof option === "string" ? { label: option, value: option } : option,
  );
  const selectedOption = normalizedOptions.find((option) => option.value === value);
  const displayLabel = selectedOption?.label || placeholder;

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
    <div className="select-combobox" ref={rootRef}>
      {name ? <input name={name} type="hidden" value={value} /> : null}
      <button
        className="select-combobox-trigger"
        type="button"
        aria-expanded={open}
        onClick={() => setOpen((current) => !current)}
      >
        <span className={value ? "" : "placeholder"}>{displayLabel}</span>
        <span className="select-combobox-arrow" aria-hidden="true" />
      </button>
      {open ? (
        <div className="select-combobox-dropdown">
          {normalizedOptions.map((option) => (
            <button
              className={`select-combobox-option ${
                option.value === value ? "is-selected" : ""
              }`}
              key={option.value}
              type="button"
              onMouseDown={(event) => event.preventDefault()}
              onClick={() => handleSelect(option.value)}
            >
              {option.label}
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}
