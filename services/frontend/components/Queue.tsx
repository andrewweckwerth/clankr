// components/Queue.tsx
'use client';

export default function Queue({ items }: { items: string[] }) {
  return (
    <div>
      <h2 className="text-xl font-bold mb-2">Queue</h2>
      <ul className="list-disc pl-5">
        {items.map((item, i) => (
          <li key={i}>{item}</li>
        ))}
      </ul>
    </div>
  );
}