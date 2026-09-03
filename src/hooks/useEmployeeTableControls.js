import { useMemo, useState } from "react";

// Shared filter + sort + row-selection logic for the Burnout/Performance employee tables.
// `filterKeys` are the plain equality dropdown filters (e.g. department, role, seniority).
// `searchKeys` are the fields matched against the free-text search box.
export function useEmployeeTableControls(employees, { searchKeys, filterKeys, scoreKey }) {
  const [search, setSearch] = useState("");
  const [filters, setFilters] = useState({});
  const [sortDir, setSortDir] = useState(null); // null | "asc" | "desc"
  const [selectedIds, setSelectedIds] = useState(new Set());

  const filterOptions = useMemo(() => {
    const options = {};
    for (const key of filterKeys) {
      options[key] = [...new Set(employees.map((e) => e[key]).filter((v) => v != null && v !== ""))].sort();
    }
    return options;
  }, [employees, filterKeys]);

  const filtered = useMemo(() => {
    const q = search.toLowerCase();
    let rows = employees;
    if (q) {
      rows = rows.filter((e) => searchKeys.some((k) => String(e[k] ?? "").toLowerCase().includes(q)));
    }
    for (const key of filterKeys) {
      const val = filters[key];
      if (val) rows = rows.filter((e) => String(e[key] ?? "") === val);
    }
    return rows;
  }, [employees, search, filters, filterKeys, searchKeys]);

  const sorted = useMemo(() => {
    if (!sortDir || !scoreKey) return filtered;
    const withScore = filtered.filter((e) => e[scoreKey] != null);
    const withoutScore = filtered.filter((e) => e[scoreKey] == null);
    withScore.sort((a, b) => (sortDir === "asc" ? a[scoreKey] - b[scoreKey] : b[scoreKey] - a[scoreKey]));
    return [...withScore, ...withoutScore];
  }, [filtered, sortDir, scoreKey]);

  function setFilter(key, value) {
    setFilters((prev) => ({ ...prev, [key]: value }));
  }

  function clearFilters() {
    setSearch("");
    setFilters({});
  }

  function toggleSort() {
    setSortDir((prev) => (prev === null ? "asc" : prev === "asc" ? "desc" : null));
  }

  function toggleSelect(id) {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  const allFilteredSelected = sorted.length > 0 && sorted.every((e) => selectedIds.has(e.employee_id));

  function toggleSelectAll() {
    setSelectedIds((prev) => {
      if (allFilteredSelected) {
        const next = new Set(prev);
        sorted.forEach((e) => next.delete(e.employee_id));
        return next;
      }
      const next = new Set(prev);
      sorted.forEach((e) => next.add(e.employee_id));
      return next;
    });
  }

  function clearSelection() {
    setSelectedIds(new Set());
  }

  return {
    search,
    setSearch,
    filters,
    setFilter,
    filterOptions,
    clearFilters,
    sortDir,
    toggleSort,
    rows: sorted,
    selectedIds,
    toggleSelect,
    toggleSelectAll,
    allFilteredSelected,
    clearSelection,
  };
}
