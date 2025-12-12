"use client";
import { useState, useRef, useEffect } from "react";

// ---------------- Types ----------------

type Filters = {
  trip_types?: string[];
  difficulty?: string;
  budget_level?: string;
  duration_days?: number;
  group_type?: string;
  travel_modes?: string[];
  accommodation?: string[];
  accessibility?: string[];
  must_include?: string[];
  must_exclude?: string[];
  interest_tags?: string[];
  events_only?: boolean;
  amenities?: string[];
  [key: string]: any;
};
type TripPlan = {
  type: "trip_plan";
  version: string;
  thread_id: string;
  message_id: string;
  days: number;
  destination: string | null;
  difficulty: string | null;
  trip_types: string[];
  budget_band: string | null;
  weather_hint?: string | null;
  lodging?: any;
  window_summary?: string | null;
  intro_text?: string | null;
  closing_tips?: string | null;
  itinerary: {
    day: number;
    title: string;
    activities: any[];
    highlights: string[];
  }[];
};
type ChatMessage =
  | { sender: "user"; kind: "text"; text: string; messageId?: string }
  | { sender: "assistant"; kind: "text"; text: string; messageId?: string }
  | {
      sender: "assistant";
      kind: "trip_plan";
      plan: TripPlan;
      messageId?: string;
    };

// ---------------- Helpers ----------------

function formatEnumLabel(value: string | null | undefined): string {
  if (!value) return "";
  return value
    .split("_")
    .map((w) => w.toLowerCase())
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

function formatBudgetBand(band: string | null | undefined): string {
  if (!band) return "Any budget";
  const map: Record<string, string> = {
    USD_0_500: "USD $0 – $500",
    USD_500_1500: "USD $500 – $1,500",
    USD_1500_3000: "USD $1,500 – $3,000",
    USD_3000_PLUS: "USD $3,000+",
  };
  return map[band] ?? formatEnumLabel(band);
}
function formatTripTypes(types: string[] | undefined): string {
  if (!types || types.length === 0) return "Trip";
  return types.map(formatEnumLabel).join(" • ");
}
function summarizeTripPlan(plan: TripPlan) {
  const hasItinerary =
    Array.isArray(plan.itinerary) && plan.itinerary.length > 0;
  const lodging = plan.lodging as any | null; // if your type is looser / optional

  return (
    <>
      {/* Itinerary days – only if present */}
      {hasItinerary &&
        plan.itinerary!.map((day, idx) => {
          const hasHighlights =
            Array.isArray(day.highlights) && day.highlights.length > 0;
          const hasActivities =
            Array.isArray(day.activities) && day.activities.length > 0;

          // if this day is completely empty, skip it
          if (!day.title && !hasHighlights && !hasActivities) {
            return null;
          }

          return (
            <div key={day.day ?? idx}>
              {/* Day title */}
              {day.title && (
                <>
                  <strong>{day.title}</strong>
                  <br />
                </>
              )}

              {/* Highlights – plain list from backend */}
              {hasHighlights && (
                <>
                  {day.highlights!.join(", ")}
                  <br />
                </>
              )}

              {/* Activities – show name + description if present */}
              {hasActivities &&
                day.activities!.map((a: any, aIdx: number) => {
                  if (!a?.name && !a?.description) return null;
                  return (
                    <div key={aIdx}>
                      {a.name}
                      {a.description ? `: ${a.description}` : ""}
                    </div>
                  );
                })}

              <br />
            </div>
          );
        })}

      {/* Lodging – only if any field is present */}
      {lodging && (lodging.name || lodging.type || lodging.notes) && (
        <>
          {lodging.name && (
            <>
              {lodging.name}
              {lodging.type ? ` (${lodging.type})` : ""}
              <br />
            </>
          )}
          {lodging.notes && (
            <>
              {lodging.notes}
              <br />
            </>
          )}
        </>
      )}

      {/* Weather – direct from backend */}
      {plan.weather_hint && (
        <>
          {plan.weather_hint}
          <br />
        </>
      )}
    </>
  );
}

// ---------------- UI Components ----------------

function TripPlanView({ plan }: { plan: TripPlan }) {
  const readableBudget = formatBudgetBand(plan.budget_band);
  const readableDifficulty = plan.difficulty
    ? formatEnumLabel(plan.difficulty)
    : "Any difficulty";
  const readableTripTypes = formatTripTypes(plan.trip_types);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      {/* Header */}
      <div
        style={{
          marginBottom: 4,
          borderBottom: "1px solid rgba(255,255,255,0.08)",
          paddingBottom: 10,
        }}
      >
        <div
          style={{
            fontSize: "1.1rem",
            fontWeight: 600,
            marginBottom: 6,
          }}
        >
          🗺️ Trip plan for {plan.destination || "your destination"}
        </div>
        <div
          style={{
            display: "flex",
            flexWrap: "wrap",
            gap: 8,
            fontSize: ".8rem",
          }}
        >
          <span
            style={{
              padding: "3px 8px",
              borderRadius: 999,
              background: "rgba(255,255,255,0.07)",
            }}
          >
            {plan.days} days
          </span>
          <span
            style={{
              padding: "3px 8px",
              borderRadius: 999,
              background: "rgba(255,255,255,0.07)",
            }}
          >
            {readableTripTypes}
          </span>
          <span
            style={{
              padding: "3px 8px",
              borderRadius: 999,
              background: "rgba(255,255,255,0.07)",
            }}
          >
            {readableDifficulty}
          </span>
          <span
            style={{
              padding: "3px 8px",
              borderRadius: 999,
              background: "rgba(255,255,255,0.07)",
            }}
          >
            {readableBudget}
          </span>
        </div>
        {plan.window_summary && (
          <div
            style={{
              fontSize: ".85rem",
              opacity: 0.8,
              marginTop: 8,
            }}
          >
            {plan.window_summary}
          </div>
        )}
      </div>
      {/* Itinerary */}
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          gap: 12,
        }}
      >
        {plan.itinerary.map((day) => (
          <div
            key={day.day}
            style={{
              padding: "12px 14px",
              borderRadius: 12,
              background: "rgba(0,0,0,0.18)",
              border: "1px solid rgba(255,255,255,0.06)",
            }}
          >
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "baseline",
                marginBottom: 4,
              }}
            >
              <div
                style={{
                  fontWeight: 550,
                  fontSize: ".97rem",
                }}
              >
                Day {day.day}: {day.title}
              </div>
              {day.activities?.length > 0 && (
                <div style={{ fontSize: ".78rem", opacity: 0.75 }}>
                  {day.activities.length} activities
                </div>
              )}
            </div>
            {day.highlights?.length > 0 && (
              <div style={{ fontSize: ".86rem", opacity: 0.92 }}>
                <div style={{ marginBottom: 2, fontWeight: 500 }}>
                  Highlights
                </div>
                <ul style={{ margin: 0, paddingLeft: "1.1rem", marginTop: 3 }}>
                  {day.highlights.map((h, idx) => (
                    <li key={idx}>{h}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

// ---------------- Main Page ----------------

export default function HomePage() {
  const [input, setInput] = useState("");
  const [threadId, setThreadId] = useState<string | null>(null);
  const [chat, setChat] = useState<ChatMessage[]>([]);
  const [filters, setFilters] = useState<Filters>({});
  const [loading, setLoading] = useState(false);
  const [waitingForReply, setWaitingForReply] = useState(false);
  const [latestAssistantId, setLatestAssistantId] = useState<string | null>(
    null
  );
  const chatEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chat, loading, waitingForReply]);

  // ---- Thread bootstrapping ----
  useEffect(() => {
    const validateAndSetThreadId = async () => {
      const savedId =
        typeof window !== "undefined"
          ? localStorage.getItem("thread_id")
          : null;
      if (savedId) {
        try {
          const resp = await fetch("http://localhost:8001/threads");
          const data = await resp.json();
          const exists = data.some((t: { id: string }) => t.id === savedId);
          if (exists) {
            setThreadId(savedId);
            return;
          } else {
            localStorage.removeItem("thread_id");
          }
        } catch (err) {
          console.warn(
            "Failed to validate saved thread, creating new one",
            err
          );
        }
      }
      const res = await fetch("http://localhost:8001/threads", {
        method: "POST",
      });
      const data = await res.json();
      setThreadId(data.id);
      localStorage.setItem("thread_id", data.id);
    };
    validateAndSetThreadId();
  }, []);

  const handleNewChat = async () => {
    setChat([]);
    setThreadId(null);
    setLatestAssistantId(null);
    setWaitingForReply(false);
    localStorage.removeItem("thread_id");
    const res = await fetch("http://localhost:8001/threads", {
      method: "POST",
    });
    const data = await res.json();
    setThreadId(data.id);
    localStorage.setItem("thread_id", data.id);
  };

  // ---- Poll /trip/latest ----
  useEffect(() => {
    if (!threadId || !waitingForReply) return;
    let cancelled = false;
    const poll = async () => {
      if (cancelled) return;
      try {
        // 🔹 Build query params with last seen message id
        const params = new URLSearchParams({ thread_id: threadId! });
        if (latestAssistantId) {
          params.set("after_message_id", latestAssistantId);
        }

        const res = await fetch(
          `http://localhost:8000/trip/latest?${params.toString()}`
        );
        const data = await res.json();
        if (cancelled) return;

        // 🔹 If backend says "nothing new", just schedule next poll
        if (data.status === "no_new_message") {
          setTimeout(poll, 1500);
          return;
        }

        if (data.status === "ok" && data.message) {
          const msg = data.message;
          const msgId = msg.id ?? msg.message_id;
          if (msgId && msgId !== latestAssistantId) {
            const content = msg.content;

            // 1) structured trip plan
            if (
              content &&
              typeof content === "object" &&
              (content as any).type === "trip_plan"
            ) {
              setChat((prev) => [
                ...prev,
                {
                  sender: "assistant",
                  kind: "trip_plan",
                  plan: content as TripPlan,
                  messageId: msgId,
                },
              ]);
            } else {
              // 2) Fallback: plain text
              let text;
              if (typeof content === "string") {
                text = content;
              } else if (content && typeof content.text === "string") {
                text = content.text;
              } else {
                text = JSON.stringify(content ?? msg);
              }
              setChat((prev) => [
                ...prev,
                {
                  sender: "assistant",
                  kind: "text",
                  text: `${text}\n\nMessage ID: ${msgId}`,
                  messageId: msgId,
                },
              ]);
            }

            // 🔹 update cursor & stop waiting
            setLatestAssistantId(msgId);
            setWaitingForReply(false);
            return;
          }
        }

        // If we got here but no new message, keep polling
        setTimeout(poll, 1500);
      } catch (err) {
        setTimeout(poll, 3000);
      }
    };

    poll();
    return () => {
      cancelled = true;
    };
  }, [threadId, waitingForReply, latestAssistantId]);

  //---- SEND MESSAGE ----
  const sendMessage = async () => {
    if (!input.trim() || loading || !threadId) return;
    setChat((prev) => [...prev, { sender: "user", kind: "text", text: input }]);
    setLoading(true);
    try {
      const saveMessageRes = await fetch("http://localhost:8001/messages", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          thread_id: threadId,
          role: "user",
          content: input,
        }),
      });
      if (!saveMessageRes.ok) throw new Error("Failed to save message");
      const savedMessage = await saveMessageRes.json();
      const requestBody = {
        request_id: "frontend-" + Date.now(),
        thread_id: threadId,
        message_id: savedMessage.id,
        constraints: filters,
        content: input,
      };
      const res = await fetch("http://localhost:8000/trip/plan", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(requestBody),
      });
      if (!res.ok) throw new Error("Failed trip plan enqueue");
      setWaitingForReply(true);
    } catch (err) {
      setChat((prev) => [
        ...prev,
        {
          sender: "assistant",
          kind: "text",
          text: "Error contacting server.",
        },
      ]);
    }
    setInput("");
    setLoading(false);
  };

  // --------------- RENDER ---------------
  return (
    <div
      style={{
        height: "100vh",
        width: "100vw",
        background: "#24262F", // Perplexity-like grey (change from "#181920" or "#1e1f27")
        color: "#F9F9FB", // White text (change from "#f6f6f6")
        fontFamily: "Inter, system-ui, -apple-system, BlinkMacSystemFont",
        display: "flex",
        flexDirection: "row",
        alignItems: "stretch",
        overflow: "hidden",
      }}
    >
      {/* ---- Trip Filters Sidebar ---- */}
      <div
        style={{
          width: 320,
          minWidth: 220,
          background: "#15161c",
          padding: "24px 18px 20px 24px",
          boxShadow: "2px 0 18px rgba(0,0,0,0.4)",
          display: "flex",
          flexDirection: "column",
          borderRight: "1px solid #262733",
          overflowY: "auto",
        }}
      >
        {/* Trip Types */}
        <div style={{ marginBottom: 14 }}>
          <div
            style={{
              fontWeight: 500,
              color: "#d8d8e3",
              marginBottom: 6,
              fontSize: ".9rem",
            }}
          >
            Trip Type
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
            {["TREKKING", "CAMPING", "CITY", "ROAD_TRIP", "HIKING"].map(
              (type) => (
                <label
                  key={type}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 6,
                    fontSize: ".9rem",
                    color: "#a7a7bb",
                  }}
                >
                  <input
                    type="checkbox"
                    checked={(filters.trip_types ?? []).includes(type)}
                    onChange={(e) =>
                      setFilters((f) => ({
                        ...f,
                        trip_types: e.target.checked
                          ? [...(f.trip_types ?? []), type]
                          : (f.trip_types ?? []).filter(
                              (t: string) => t !== type
                            ),
                      }))
                    }
                  />
                  <span>{formatEnumLabel(type)}</span>
                </label>
              )
            )}
          </div>
        </div>

        {/* Difficulty */}
        <div style={{ marginBottom: 14 }}>
          <div
            style={{
              fontWeight: 500,
              color: "#d8d8e3",
              marginBottom: 6,
              fontSize: ".9rem",
            }}
          >
            Difficulty
          </div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 10 }}>
            {["EASY", "MODERATE", "HARD"].map((diff) => (
              <label
                key={diff}
                style={{
                  fontSize: ".9rem",
                  color: "#a7a7bb",
                  display: "flex",
                  alignItems: "center",
                  gap: 5,
                }}
              >
                <input
                  type="radio"
                  name="difficulty"
                  checked={filters.difficulty === diff}
                  onChange={() =>
                    setFilters((f) => ({ ...f, difficulty: diff }))
                  }
                />
                <span>{formatEnumLabel(diff)}</span>
              </label>
            ))}
          </div>
        </div>

        {/* Budget Level */}
        <div style={{ marginBottom: 14 }}>
          <div
            style={{
              fontWeight: 500,
              color: "#d8d8e3",
              marginBottom: 6,
              fontSize: ".9rem",
            }}
          >
            Budget (USD)
          </div>
          <select
            value={filters.budget_level || ""}
            onChange={(e) =>
              setFilters((f) => ({ ...f, budget_level: e.target.value }))
            }
            style={{
              width: "100%",
              padding: "7px 8px",
              borderRadius: 6,
              background: "#20212a",
              color: "#f7f7fa",
              border: "1px solid #343545",
              fontSize: ".9rem",
            }}
          >
            <option value="">Any</option>
            <option value="USD_0_500">USD $0 – $500</option>
            <option value="USD_500_1500">USD $500 – $1,500</option>
            <option value="USD_1500_3000">USD $1,500 – $3,000</option>
            <option value="USD_3000_PLUS">USD $3,000+</option>
          </select>
        </div>

        {/* Duration Days */}
        <div style={{ marginBottom: 14 }}>
          <div
            style={{
              fontWeight: 500,
              color: "#d8d8e3",
              marginBottom: 6,
              fontSize: ".9rem",
            }}
          >
            Duration (days)
          </div>
          <input
            type="number"
            min={1}
            max={30}
            value={filters.duration_days ?? ""}
            onChange={(e) => {
              const value = e.target.value;
              setFilters((f) => ({
                ...f,
                duration_days: value ? Number(value) : undefined,
              }));
            }}
            style={{
              width: "70%",
              padding: "7px",
              borderRadius: 6,
              border: "1px solid #343545",
              background: "#20212a",
              color: "#f7f7fa",
              fontSize: ".9rem",
            }}
            placeholder="5"
          />
        </div>

        {/* Group Type */}
        <div style={{ marginBottom: 14 }}>
          <div
            style={{
              fontWeight: 500,
              color: "#d8d8e3",
              marginBottom: 6,
              fontSize: ".9rem",
            }}
          >
            Group Type
          </div>
          <select
            value={filters.group_type || ""}
            onChange={(e) =>
              setFilters((f) => ({ ...f, group_type: e.target.value }))
            }
            style={{
              width: "100%",
              padding: "7px 8px",
              borderRadius: 6,
              background: "#20212a",
              color: "#f7f7fa",
              border: "1px solid #343545",
              fontSize: ".9rem",
            }}
          >
            <option value="">Any</option>
            <option value="SOLO">Solo</option>
            <option value="COUPLE">Couple</option>
            <option value="FRIENDS">Friends</option>
            <option value="FAMILY">Family</option>
            <option value="TEAM">Team</option>
          </select>
        </div>

        {/* Travel Modes */}
        <div style={{ marginBottom: 14 }}>
          <div
            style={{
              fontWeight: 500,
              color: "#d8d8e3",
              marginBottom: 6,
              fontSize: ".9rem",
            }}
          >
            Travel Modes
          </div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
            {["CAR", "BUS", "FLIGHT", "BIKE"].map((mode) => (
              <label
                key={mode}
                style={{
                  fontSize: ".9rem",
                  color: "#a7a7bb",
                  display: "flex",
                  alignItems: "center",
                  gap: 5,
                }}
              >
                <input
                  type="checkbox"
                  checked={(filters.travel_modes ?? []).includes(mode)}
                  onChange={(e) =>
                    setFilters((f) => ({
                      ...f,
                      travel_modes: e.target.checked
                        ? [...(f.travel_modes ?? []), mode]
                        : (f.travel_modes ?? []).filter(
                            (m: string) => m !== mode
                          ),
                    }))
                  }
                />
                <span>{formatEnumLabel(mode)}</span>
              </label>
            ))}
          </div>
        </div>

        {/* Accommodation */}
        <div style={{ marginBottom: 14 }}>
          <div
            style={{
              fontWeight: 500,
              color: "#d8d8e3",
              marginBottom: 6,
              fontSize: ".9rem",
            }}
          >
            Accommodation
          </div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
            {["CAMPING", "HOTEL", "HOSTEL", "LODGE"].map((acc) => (
              <label
                key={acc}
                style={{
                  fontSize: ".9rem",
                  color: "#a7a7bb",
                  display: "flex",
                  alignItems: "center",
                  gap: 5,
                }}
              >
                <input
                  type="checkbox"
                  checked={(filters.accommodation ?? []).includes(acc)}
                  onChange={(e) =>
                    setFilters((f) => ({
                      ...f,
                      accommodation: e.target.checked
                        ? [...(f.accommodation ?? []), acc]
                        : (f.accommodation ?? []).filter(
                            (a: string) => a !== acc
                          ),
                    }))
                  }
                />
                <span>{formatEnumLabel(acc)}</span>
              </label>
            ))}
          </div>
        </div>

        {/* Accessibility */}
        <div style={{ marginBottom: 14 }}>
          <div
            style={{
              fontWeight: 500,
              color: "#d8d8e3",
              marginBottom: 6,
              fontSize: ".9rem",
            }}
          >
            Accessibility
          </div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
            {["PET_FRIENDLY", "WHEELCHAIR", "KIDS"].map((tag) => (
              <label
                key={tag}
                style={{
                  fontSize: ".9rem",
                  color: "#a7a7bb",
                  display: "flex",
                  alignItems: "center",
                  gap: 5,
                }}
              >
                <input
                  type="checkbox"
                  checked={(filters.accessibility ?? []).includes(tag)}
                  onChange={(e) =>
                    setFilters((f) => ({
                      ...f,
                      accessibility: e.target.checked
                        ? [...(f.accessibility ?? []), tag]
                        : (f.accessibility ?? []).filter(
                            (a: string) => a !== tag
                          ),
                    }))
                  }
                />
                <span>{formatEnumLabel(tag)}</span>
              </label>
            ))}
          </div>
        </div>

        {/* Must Include */}
        <div style={{ marginBottom: 14 }}>
          <div
            style={{
              fontWeight: 500,
              color: "#d8d8e3",
              marginBottom: 6,
              fontSize: ".9rem",
            }}
          >
            Must Include
          </div>
          <input
            type="text"
            placeholder="e.g. National park, Museum"
            value={(filters.must_include ?? []).join(", ")}
            onChange={(e) =>
              setFilters((f) => ({
                ...f,
                must_include: e.target.value
                  .split(",")
                  .map((s) => s.trim())
                  .filter(Boolean),
              }))
            }
            style={{
              width: "100%",
              padding: "7px",
              borderRadius: 6,
              border: "1px solid #343545",
              background: "#20212a",
              color: "#f7f7fa",
              marginBottom: 8,
              fontSize: ".9rem",
            }}
          />
          <div
            style={{
              fontWeight: 500,
              color: "#d8d8e3",
              marginBottom: 6,
              fontSize: ".9rem",
            }}
          >
            Must Exclude
          </div>
          <input
            type="text"
            placeholder="e.g. Flight"
            value={(filters.must_exclude ?? []).join(", ")}
            onChange={(e) =>
              setFilters((f) => ({
                ...f,
                must_exclude: e.target.value
                  .split(",")
                  .map((s) => s.trim())
                  .filter(Boolean),
              }))
            }
            style={{
              width: "100%",
              padding: "7px",
              borderRadius: 6,
              border: "1px solid #343545",
              background: "#20212a",
              color: "#f7f7fa",
              fontSize: ".9rem",
            }}
          />
        </div>

        {/* Interest Tags */}
        <div style={{ marginBottom: 14 }}>
          <div
            style={{
              fontWeight: 500,
              color: "#d8d8e3",
              marginBottom: 6,
              fontSize: ".9rem",
            }}
          >
            Interest Tags
          </div>
          <input
            type="text"
            placeholder="e.g. Photography, Nature"
            value={(filters.interest_tags ?? []).join(", ")}
            onChange={(e) =>
              setFilters((f) => ({
                ...f,
                interest_tags: e.target.value
                  .split(",")
                  .map((s) => s.trim())
                  .filter(Boolean),
              }))
            }
            style={{
              width: "100%",
              padding: "7px",
              borderRadius: 6,
              border: "1px solid #343545",
              background: "#20212a",
              color: "#f7f7fa",
              fontSize: ".9rem",
            }}
          />
        </div>

        {/* Events only */}
        <div style={{ marginBottom: 12 }}>
          <label
            style={{
              fontWeight: 500,
              color: "#d8d8e3",
              fontSize: ".9rem",
              display: "flex",
              alignItems: "center",
              gap: 6,
            }}
          >
            <input
              type="checkbox"
              checked={filters.events_only || false}
              onChange={(e) =>
                setFilters((f) => ({ ...f, events_only: e.target.checked }))
              }
            />
            Events only
          </label>
        </div>

        {/* Amenities */}
        <div style={{ marginBottom: 16 }}>
          <div
            style={{
              fontWeight: 500,
              color: "#d8d8e3",
              marginBottom: 6,
              fontSize: ".9rem",
            }}
          >
            Amenities
          </div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
            {["WI_FI", "SPA", "POOL", "PARKING"].map((am) => (
              <label
                key={am}
                style={{
                  fontSize: ".9rem",
                  color: "#a7a7bb",
                  display: "flex",
                  alignItems: "center",
                  gap: 5,
                }}
              >
                <input
                  type="checkbox"
                  checked={(filters.amenities ?? []).includes(am)}
                  onChange={(e) =>
                    setFilters((f) => ({
                      ...f,
                      amenities: e.target.checked
                        ? [...(f.amenities ?? []), am]
                        : (f.amenities ?? []).filter((a: string) => a !== am),
                    }))
                  }
                />
                <span>{formatEnumLabel(am)}</span>
              </label>
            ))}
          </div>
        </div>
      </div>
      {/* ---- Chat Panel ---- */}
      <div
        style={{
          flex: 1,
          background: "#24262F", // Same as main background
          display: "flex",
          flexDirection: "column",
          height: "100vh",
          minWidth: 340,
          color: "#F9F9FB",
        }}
      >
        <div
          style={{
            padding: "18px 34px 14px 34px",
            borderBottom: "1px solid #262733",
            fontWeight: 600,
            fontSize: "1.05rem",
            justifyContent: "space-between",
            display: "flex",
            alignItems: "center",
          }}
        >
          <span>
            <span role="img" aria-label="plane">
              🛩️
            </span>{" "}
            TravelBot – AI Travel Planner
          </span>
          <button
            onClick={handleNewChat}
            style={{
              background: "#35364a",
              color: "#fff",
              border: "none",
              borderRadius: 7,
              padding: "6px 16px",
              fontSize: ".9rem",
              cursor: "pointer",
              marginLeft: "auto",
              marginRight: 0,
            }}
          >
            New chat
          </button>
        </div>
        <div
          style={{
            flex: 1,
            overflowY: "auto",
            padding: "20px 0 10px 0",
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
          }}
        >
          <div
            style={{
              width: "100%",
              maxWidth: 760,
              padding: "0 24px",
              display: "flex",
              flexDirection: "column",
            }}
          >
            {chat.map((msg, i) => (
              <div
                key={i}
                style={{
                  display: "flex",
                  justifyContent:
                    msg.sender === "user" ? "flex-end" : "flex-start",
                  marginBottom: 16,
                }}
              >
                <div
                  style={{
                    maxWidth: "80%",
                    background: msg.sender === "user" ? "#007fff" : "#24253b",
                    color: msg.sender === "user" ? "#fff" : "#e9eaf0",
                    borderRadius: 12,
                    padding:
                      msg.kind === "trip_plan" && msg.sender === "assistant"
                        ? "16px 18px"
                        : "11px 15px",
                    fontSize: "1rem",
                    whiteSpace: "pre-line",
                    boxShadow:
                      msg.sender === "assistant"
                        ? "0 2px 16px rgba(0,0,0,0.32)"
                        : "0 1px 10px rgba(0,0,0,0.22)",
                    borderLeft:
                      msg.sender === "assistant" && msg.kind === "trip_plan"
                        ? "4px solid #007fff"
                        : "none",
                  }}
                >
                  {msg.kind === "trip_plan" && msg.sender === "assistant" ? (
                    <div style={{ whiteSpace: "pre-line" }}>
                      <div style={{ marginBottom: "1em" }}>
                        {msg.plan.intro_text || ""}
                      </div>
                      {summarizeTripPlan(msg.plan)}
                      {msg.plan.closing_tips && (
                        <div
                          style={{
                            marginTop: "1.5em",
                            fontStyle: "italic",
                            opacity: 0.8,
                          }}
                        >
                          {msg.plan.closing_tips}
                        </div>
                      )}
                    </div>
                  ) : (
                    (msg as any).text
                  )}
                </div>
              </div>
            ))}
            {(loading || waitingForReply) && (
              <div
                style={{
                  display: "flex",
                  justifyContent: "flex-start",
                  marginBottom: 18,
                }}
              >
                <div
                  style={{
                    background: "#2d2f3a",
                    color: "#e9eaf0",
                    borderRadius: 12,
                    padding: "10px 16px",
                    fontSize: ".95rem",
                    fontStyle: "italic",
                  }}
                >
                  TravelBot is thinking…
                </div>
              </div>
            )}
            <div ref={chatEndRef} />
          </div>
        </div>
        <div
          style={{
            borderTop: "1px solid #262733",
            padding: "16px 30px 18px 30px",
            background: "#1a1b22",
            display: "flex",
            justifyContent: "center",
          }}
        >
          <form
            style={{
              display: "flex",
              gap: 10,
              width: "100%",
              maxWidth: 760,
            }}
            onSubmit={(e) => {
              e.preventDefault();
              sendMessage();
            }}
          >
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask TravelBot for a trip plan…"
              style={{
                flex: 1,
                padding: "12px 16px",
                borderRadius: 10,
                border: "1px solid #343545",
                background: "#11121a",
                color: "#f7f7fa",
                fontSize: ".98rem",
              }}
              disabled={loading || waitingForReply}
            />
            <button
              type="submit"
              disabled={loading || waitingForReply || !input.trim()}
              style={{
                background:
                  loading || waitingForReply || !input.trim()
                    ? "#3d3e4a"
                    : "#007fff",
                color: "#fff",
                borderRadius: 10,
                fontWeight: 600,
                padding: "0 24px",
                fontSize: ".98rem",
                border: "none",
                cursor:
                  loading || waitingForReply || !input.trim()
                    ? "not-allowed"
                    : "pointer",
              }}
            >
              Send
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
