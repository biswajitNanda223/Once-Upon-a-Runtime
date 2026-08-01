import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import "./style.css";

type Greeting = { message: string; email: string; pattern: string };
type Item = { id: number; name: string };

function App() {
  const [data, setData] = useState<Greeting | null>(null);
  const [item, setItem] = useState<Item | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    fetch("/api/hello", { credentials: "same-origin" })
      .then(async (r) => { if (!r.ok) throw new Error(`${r.status} ${await r.text()}`); return r.json(); })
      .then(setData).catch((e: Error) => setError(e.message));
    fetch("/api/items/42", { credentials: "same-origin" })
      .then(async (r) => { if (!r.ok) throw new Error(`${r.status} ${await r.text()}`); return r.json(); })
      .then(setItem).catch((e: Error) => setError(e.message));
  }, []);
  return <main><p className="eyebrow">ONCE UPON A RUNTIME</p><h1>One runtime. One origin.</h1>
    {data && <section><strong>{data.message}</strong><span>{data.email}</span><code>{data.pattern}</code></section>}
    {item && <p>Dynamic API route: <code>/api/items/{item.id}</code> → {item.name}</p>}
    <p>SPA deep link: <a href="/projects/42">/projects/42</a> (refresh-safe)</p>
    {error && <p role="alert">{error}</p>}</main>;
}

createRoot(document.getElementById("root")!).render(<React.StrictMode><App /></React.StrictMode>);
