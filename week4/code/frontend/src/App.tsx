import { useState } from 'react';

export default function App() {
  const [mode, setMode] = useState<'U' | 'A'>('U');

  return (
    <main>
      <h1>ED MAS</h1>
      <button onClick={() => setMode('U')}>Mode-U</button>
      <button onClick={() => setMode('A')}>Mode-A</button>
      <p>Current: {mode}</p>
    </main>
  );
}
