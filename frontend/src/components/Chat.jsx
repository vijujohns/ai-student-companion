import { useState } from "react";
import axios from "axios";

export default function Chat() {
  const [q, setQ] = useState("");
  const [messages, setMessages] = useState([]);

  const send = async () => {
    const res = await axios.post("http://localhost:8000/query", {
      question: q
    });

    setMessages([...messages, {q, a: res.data.answer}]);
    setQ("");
  };

  return (
    <div>
      <input value={q} onChange={e=>setQ(e.target.value)} />
      <button onClick={send}>Ask</button>
      {messages.map((m,i)=>(
        <div key={i}>
          <b>Q:</b>{m.q}<br/>
          <b>A:</b>{m.a}
        </div>
      ))}
    </div>
  );
}
