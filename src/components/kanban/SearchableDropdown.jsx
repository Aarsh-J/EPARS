import { useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";

export default function SearchableDropdown({
  options,
  value,
  onChange,
  placeholder = "Select",
  ariaLabel,
  multiple = false,
  disabled = false,
  className = "",
  id,
  triggerClassName = "",
  searchable = true,
  showSelectionActions = false,
}) {
  const [isOpen, setIsOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [menuPosition, setMenuPosition] = useState(null);
  const rootRef = useRef(null);
  const menuRef = useRef(null);
  const searchRef = useRef(null);
  const selectedValues = useMemo(
    () => multiple ? value || [] : [value],
    [multiple, value]
  );

  const selectedOptions = useMemo(
    () => options.filter((option) => selectedValues.includes(option.value)),
    [options, selectedValues]
  );
  const filteredOptions = useMemo(() => {
    const normalizedQuery = query.trim().toLocaleLowerCase();
    if (!normalizedQuery) return options;
    return options.filter((option) =>
      `${option.label} ${option.value}`.toLocaleLowerCase().includes(normalizedQuery)
    );
  }, [options, query]);

  useEffect(() => {
    if (!isOpen) return undefined;
    const updateMenuPosition = () => {
      const trigger = rootRef.current?.querySelector(".kanban-searchable-trigger");
      if (!trigger) return;
      const rect = trigger.getBoundingClientRect();
      const width = Math.min(Math.max(210, rect.width), window.innerWidth - 16);
      const left = Math.max(8, Math.min(rect.left, window.innerWidth - width - 8));
      const maxHeight = Math.min(320, window.innerHeight - 16);
      const spaceBelow = window.innerHeight - rect.bottom - 8;
      if (spaceBelow < Math.min(220, maxHeight) && rect.top > spaceBelow) {
        setMenuPosition({
          left,
          width,
          bottom: window.innerHeight - rect.top + 4,
          maxHeight,
        });
      } else {
        setMenuPosition({
          left,
          width,
          top: rect.bottom + 4,
          maxHeight,
        });
      }
    };
    const handlePointerDown = (event) => {
      if (
        !rootRef.current?.contains(event.target) &&
        !menuRef.current?.contains(event.target)
      ) {
        setIsOpen(false);
        setQuery("");
      }
    };
    const handleKeyDown = (event) => {
      if (event.key === "Escape") {
        setIsOpen(false);
        setQuery("");
      }
    };
    updateMenuPosition();
    document.addEventListener("mousedown", handlePointerDown);
    document.addEventListener("touchstart", handlePointerDown);
    document.addEventListener("keydown", handleKeyDown);
    window.addEventListener("resize", updateMenuPosition);
    window.addEventListener("scroll", updateMenuPosition, true);
    return () => {
      document.removeEventListener("mousedown", handlePointerDown);
      document.removeEventListener("touchstart", handlePointerDown);
      document.removeEventListener("keydown", handleKeyDown);
      window.removeEventListener("resize", updateMenuPosition);
      window.removeEventListener("scroll", updateMenuPosition, true);
    };
  }, [isOpen]);

  useEffect(() => {
    if (isOpen && menuPosition) searchRef.current?.focus();
  }, [isOpen, menuPosition]);

  const selectedLabel = multiple
    ? selectedOptions.length === 0
      ? placeholder
      : selectedOptions.length === 1
        ? selectedOptions[0].label
        : `${selectedOptions.length} selected`
    : selectedOptions[0]?.label || placeholder;

  const toggleOption = (option) => {
    if (multiple) {
      const next = selectedValues.includes(option.value)
        ? selectedValues.filter((item) => item !== option.value)
        : [...selectedValues, option.value];
      onChange(next);
      return;
    }
    onChange(option.value);
    setIsOpen(false);
    setQuery("");
  };

  const selectAll = () => {
    onChange(options.map((option) => option.value));
    setIsOpen(false);
    setQuery("");
  };

  const clearSelection = () => {
    onChange(multiple ? [] : options[0]?.value ?? "");
    setQuery("");
    setIsOpen(false);
  };

  return (
    <div className={`kanban-searchable-dropdown ${className}`} ref={rootRef}>
      <button
        id={id}
        type="button"
        className={`jira-select-filter kanban-searchable-trigger ${triggerClassName}`}
        aria-label={ariaLabel}
        aria-haspopup="listbox"
        aria-expanded={isOpen}
        disabled={disabled}
        onClick={() => setIsOpen((open) => !open)}
      >
        <span className="kanban-searchable-trigger-label" title={selectedLabel}>
          {selectedLabel}
        </span>
        <span className="kanban-searchable-chevron" aria-hidden="true">▾</span>
      </button>
      {isOpen && menuPosition && createPortal(
        <div className="kanban-searchable-menu" ref={menuRef} style={menuPosition}>
          {searchable && (
            <div className="kanban-searchable-search-wrap">
              <input
                ref={searchRef}
                type="search"
                className="kanban-searchable-search"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Search…"
                aria-label={`Search ${ariaLabel || placeholder}`}
              />
            </div>
          )}
          {multiple && showSelectionActions && (
            <div className="kanban-searchable-actions">
              <button type="button" onClick={selectAll}>Select All</button>
              <button type="button" onClick={clearSelection}>Clear Selection</button>
            </div>
          )}
          <div className="kanban-searchable-options" role="listbox" aria-multiselectable={multiple}>
            {filteredOptions.length === 0 ? (
              <div className="kanban-searchable-empty">No results found</div>
            ) : filteredOptions.map((option) => {
              const isSelected = selectedValues.includes(option.value);
              return (
                <button
                  type="button"
                  key={option.value}
                  role="option"
                  aria-selected={isSelected}
                  className={`kanban-searchable-option ${isSelected ? "selected" : ""}`}
                  onClick={() => toggleOption(option)}
                >
                  {multiple && <span className="kanban-searchable-checkbox" aria-hidden="true">{isSelected ? "✓" : ""}</span>}
                  <span>{option.label}</span>
                </button>
              );
            })}
          </div>
        </div>,
        document.body
      )}
    </div>
  );
}
