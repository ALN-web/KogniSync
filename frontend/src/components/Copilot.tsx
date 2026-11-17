import { useEffect, useRef, useState, type FormEvent } from "react";
import { ApiError, api } from "../api/client";
import type { ChatResponse, ChatTurn, Journey } from "../api/types";
import { formatInr } from "../lib/format";
import { Icon } from "./icons";
import { ProvenanceBadge } from "./ProvenanceBadge";

interface Props {
  trippassId?: string;
  onReviewJourney: (j: Journey) => void;
}

interface Entry {
  role: "user" | "model";
  text: string;
  response?: ChatResponse;
}

const LANGS = [
  { code: "en-IN", name: "English" },
  { code: "hi-IN", name: "Hindi" },
  { code: "kn-IN", name: "Kannada" },
  { code: "ta-IN", name: "Tamil" },
  { code: "te-IN", name: "Telugu" },
];

const SUGGESTIONS = [
  "Udayapalya, Bengaluru to CP Delhi under ₹9,000",
  "Koramangala to Whitefield, avoid cabs",
  "Any delays on my trip?",
  "Bengaluru to Chennai by train",
];

// Browser speech recognition (Chrome/Edge) is the fallback when Gemini isn't configured.
type SpeechCtor = new () => {
  lang: string;
  onresult: (e: { results: { 0: { transcript: string } }[] }) => void;
  onerror: () => void;
  onend: () => void;
  start: () => void;
};
const BrowserSpeech: SpeechCtor | undefined =
  (globalThis as unknown as { SpeechRecognition?: SpeechCtor; webkitSpeechRecognition?: SpeechCtor })
    .SpeechRecognition ??
  (globalThis as unknown as { webkitSpeechRecognition?: SpeechCtor }).webkitSpeechRecognition;

export function Copilot({ trippassId, onReviewJourney }: Props) {
  const [entries, setEntries] = useState<Entry[]>([]);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [lang, setLang] = useState("en-IN");
  const [speak, setSpeak] = useState(false);
  const [recording, setRecording] = useState(false);
  const [gemini, setGemini] = useState<boolean | null>(null);
  const [error, setError] = useState<string | null>(null);
  const recorder = useRef<MediaRecorder | null>(null);
  const lastJourney = useRef<string | undefined>(undefined);
  const logRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    api.copilotStatus().then((s) => setGemini(s.gemini_configured), () => setGemini(false));
  }, []);

  useEffect(() => {
    const log = logRef.current;
    if (log && typeof log.scrollTo === "function") log.scrollTo({ top: log.scrollHeight, behavior: "smooth" });
  }, [entries, busy]);

  const langName = LANGS.find((l) => l.code === lang)?.name;

  function say(answer: string) {
    if (!speak || !("speechSynthesis" in globalThis)) return;
    const u = new SpeechSynthesisUtterance(answer);
    u.lang = lang;
    speechSynthesis.speak(u);
  }

  function addReply(res: ChatResponse) {
    if (res.journeys[0]) lastJourney.current = res.journeys[0].journey_id;
    setEntries((e) => [...e, { role: "model", text: res.answer, response: res }]);
    say(res.answer);
  }

  async function send(message: string) {
    if (!message.trim() || busy) return;
    const history: ChatTurn[] = entries.slice(-10).map(({ role, text }) => ({ role, text }));
    setEntries((e) => [...e, { role: "user", text: message }]);
    setText("");
    setBusy(true);
    setError(null);
    try {
      addReply(
        await api.chat(message, history, {
          trippass_id: trippassId,
          journey_id: lastJourney.current,
          reply_language: lang === "en-IN" ? undefined : langName,
        }),
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  async function startVoice() {
    setError(null);
    if (gemini) {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        const chunks: Blob[] = [];
        const rec = new MediaRecorder(stream);
        rec.ondataavailable = (e) => chunks.push(e.data);
        rec.onstop = async () => {
          stream.getTracks().forEach((t) => t.stop());
          setRecording(false);
          setBusy(true);
          try {
            const res = await api.voice(new Blob(chunks, { type: "audio/webm" }), langName, trippassId);
            setEntries((e) => [...e, { role: "user", text: `🎤 ${res.voice.transcript} (${res.voice.language})` }]);
            addReply(res.chat);
          } catch (e) {
            setError(e instanceof Error ? e.message : String(e));
          } finally {
            setBusy(false);
          }
        };
        recorder.current = rec;
        rec.start();
        setRecording(true);
      } catch {
        setError("Microphone permission was denied.");
      }
      return;
    }
    if (!BrowserSpeech) {
      setError("Voice needs a Gemini API key or a browser with speech recognition (Chrome, Edge).");
      return;
    }
    const r = new BrowserSpeech();
    r.lang = lang;
    r.onresult = (e) => send(e.results[0][0].transcript);
    r.onerror = () => setError("Couldn't hear that. Try again.");
    r.onend = () => setRecording(false);
    setRecording(true);
    r.start();
  }

  async function onPhoto(file: File | undefined) {
    if (!file) return;
    setBusy(true);
    setError(null);
    try {
      const res = await api.vision(file);
      const x = res.extraction;
      const facts = [
        x.operator,
        x.service_number,
        x.pnr && `PNR ${x.pnr}`,
        x.origin && x.destination && `${x.origin} → ${x.destination}`,
        x.depart,
        x.platform_or_gate && `Platform/gate ${x.platform_or_gate}`,
        x.status,
      ]
        .filter(Boolean)
        .join(" · ");
      setEntries((e) => [
        ...e,
        { role: "user", text: `📷 ${file.name}` },
        {
          role: "model",
          text: `I read a ${x.document_type.replace("_", " ")} (${x.confidence} confidence): ${facts || "nothing clear"}.`,
        },
      ]);
      if (res.suggested_search?.destination) {
        await send(`Plan from ${res.suggested_search.origin ?? "my location"} to ${res.suggested_search.destination}`);
      }
    } catch (e) {
      setError(
        e instanceof ApiError && e.status === 503
          ? "Reading photos needs a Gemini API key (GEMINI_API_KEY)."
          : e instanceof Error
            ? e.message
            : String(e),
      );
    } finally {
      setBusy(false);
    }
  }

  async function review(journeyId: string) {
    try {
      onReviewJourney(await api.journey(journeyId));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  return (
    <section className="card chat" aria-label="Copilot">
      <div className="chat__bar">
        <span className={`chip ${gemini ? "chip--recommended" : ""}`}>
          {gemini === null ? "Connecting…" : gemini ? "Gemini" : "Offline planner (no API key)"}
        </span>
        <label>
          Language
          <select value={lang} onChange={(e) => setLang(e.target.value)}>
            {LANGS.map((l) => (
              <option key={l.code} value={l.code}>
                {l.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          <input type="checkbox" checked={speak} onChange={(e) => setSpeak(e.target.checked)} /> Speak replies
        </label>
      </div>

      <div className="chat__log" ref={logRef} aria-live="polite">
        {entries.length === 0 && (
          <div className="chat__empty">
            <p className="eyebrow">KogniSync copilot</p>
            <h2>Where are you headed?</h2>
            <p className="muted">
              Ask in English, Hindi, Kannada, Tamil or Telugu. Send a photo of a ticket or departure board. Prices come
              only from KogniSync's services, and nothing is booked without your OK.
            </p>
            <div className="suggestions">
              {SUGGESTIONS.map((s) => (
                <button key={s} type="button" className="suggestion" onClick={() => send(s)}>
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}
        {entries.map((e, i) => (
          <div key={i} className={`msg msg--${e.role}`}>
            <span className="msg__avatar" aria-hidden="true">
              {e.role === "model" ? "K" : "You"}
            </span>
            <div className="msg__bubble">
              <p>{e.text}</p>
              {e.response && (
                <>
                  <p className="msg__meta">
                    {e.response.ai_mode === "gemini" ? "Gemini" : "Offline planner"}
                    {e.response.tool_calls.length > 0 && ` · tools: ${e.response.tool_calls.map((t) => t.name).join(", ")}`}
                    {e.response.grounding.verified ? " · prices verified" : " · unverified price removed"}
                  </p>
                  {e.response.notice && <p className="warning">{e.response.notice}</p>}
                  {e.response.journeys.slice(0, 3).map((j) => (
                    <div key={j.journey_id} className="mini">
                      <span className="mini__route">
                        {j.labels[0] && <strong>{j.labels[0].replace("_", " ")}: </strong>}
                        {j.route}
                        <br />
                        <span className="muted">
                          {j.depart} → {j.arrive} · {j.cost_display} <ProvenanceBadge kind={j.cost_provenance} />
                        </span>
                      </span>
                      <button className="btn btn--ghost" onClick={() => review(j.journey_id)}>
                        Review
                      </button>
                    </div>
                  ))}
                  {e.response.proposed_action && (
                    <button
                      className="btn"
                      style={{ marginTop: 10 }}
                      onClick={() => review(e.response!.proposed_action!.journey_id)}
                    >
                      Review and hold ({formatInr(e.response.proposed_action.cost_inr)})
                    </button>
                  )}
                </>
              )}
            </div>
          </div>
        ))}
        {busy && (
          <div className="msg msg--model" role="status" aria-label="Copilot is thinking">
            <span className="msg__avatar" aria-hidden="true">
              K
            </span>
            <div className="msg__bubble">
              <span className="typing">
                <i />
                <i />
                <i />
              </span>
            </div>
          </div>
        )}
      </div>

      {error && (
        <div role="alert" className="alert alert--bad" style={{ margin: "0 16px 10px" }}>
          <Icon name="alert" />
          <p>{error}</p>
        </div>
      )}

      <form
        className="chat__input"
        onSubmit={(e: FormEvent) => {
          e.preventDefault();
          send(text);
        }}
      >
        <button
          className="iconbtn"
          type="button"
          onClick={() => (recording ? recorder.current?.stop() : startVoice())}
          disabled={busy && !recording}
          aria-pressed={recording}
          aria-label={recording ? "Stop recording" : "Speak"}
        >
          <Icon name="mic" />
        </button>
        <label className="iconbtn file" aria-label="Send a photo">
          <Icon name="camera" />
          <input type="file" accept="image/*" capture="environment" onChange={(e) => onPhoto(e.target.files?.[0])} />
        </label>
        <input
          aria-label="Message"
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Where do you want to go?"
          disabled={busy}
          autoComplete="off"
        />
        <button className="btn" type="submit" disabled={busy || !text.trim()} aria-label="Send">
          <Icon name="send" size={16} />
          <span className="sr-only">Send</span>
        </button>
      </form>
    </section>
  );
}
