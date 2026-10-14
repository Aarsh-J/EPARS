import { useEffect, useState } from "react";

// Loads public/results.json, written by `npm run bench`.
export default function useResults() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  useEffect(() => {
    fetch("/results.json", { cache: "no-store" })
      .then((r) => { if (!r.ok) throw new Error("results.json not found"); return r.json(); })
      .then(setData)
      .catch((e) => setError(e.message));
  }, []);
  return { data, error };
}
