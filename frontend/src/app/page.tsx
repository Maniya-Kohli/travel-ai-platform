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

const DB_SERVICE_URL =
  process.env.NEXT_PUBLIC_DB_SERVICE_URL || "http://localhost:8001";

const GETEWAY_SERVICE_URL =
  process.env.NEXT_PUBLIC_GETEWAY_SERVICE_URL || "http://localhost:8000";

console.log("GW URL (client):", GETEWAY_SERVICE_URL);

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
  const lodging = plan.lodging as any | null;

  return (
    <>
      {hasItinerary &&
        plan.itinerary!.map((day, idx) => {
          const hasHighlights =
            Array.isArray(day.highlights) && day.highlights.length > 0;
          const hasActivities =
            Array.isArray(day.activities) && day.activities.length > 0;

          if (!day.title && !hasHighlights && !hasActivities) {
            return null;
          }

          return (
            <div key={day.day ?? idx}>
              {day.title && (
                <>
                  <strong>{day.title}</strong>
                  <br />
                </>
              )}

              {hasHighlights && (
                <>
                  {day.highlights!.join(", ")}
                  <br />
                </>
              )}

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

  // Sidebar open / close + mobile
  const [isMobile, setIsMobile] = useState(false);
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  const [isFilterHover, setIsFilterHover] = useState(false);

  const chatEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chat, loading, waitingForReply]);

  // Detect mobile / window resize
  useEffect(() => {
    const handleResize = () => {
      if (typeof window === "undefined") return;
      const mobile = window.innerWidth <= 768;
      setIsMobile(mobile);
    };
    handleResize();
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  // ---- Thread bootstrapping ----
  useEffect(() => {
    const validateAndSetThreadId = async () => {
      const savedId =
        typeof window !== "undefined"
          ? localStorage.getItem("thread_id")
          : null;
      if (savedId) {
        try {
          // const resp = await fetch("http://localhost:8001/threads");
          const resp = await fetch(`${DB_SERVICE_URL}/threads`);
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
      // const res = await fetch("http://localhost:8001/threads", {
      //   method: "POST",
      // });
      const res = await fetch(`${DB_SERVICE_URL}/threads`, { method: "POST" });

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
    if (typeof window !== "undefined") {
      localStorage.removeItem("thread_id");
    }
    const res = await fetch(`${DB_SERVICE_URL}/threads`, { method: "POST" });
    const data = await res.json();
    setThreadId(data.id);
    if (typeof window !== "undefined") {
      localStorage.setItem("thread_id", data.id);
    }
  };

  // ---- Poll /trip/latest ----
  useEffect(() => {
    if (!threadId || !waitingForReply) return;
    let cancelled = false;
    const poll = async () => {
      if (cancelled) return;
      try {
        const params = new URLSearchParams({ thread_id: threadId! });
        if (latestAssistantId) {
          params.set("after_message_id", latestAssistantId);
        }

        const res = await fetch(
          `${GETEWAY_SERVICE_URL}/trip/latest?${params.toString()}`
        );

        const data = await res.json();
        if (cancelled) return;

        if (data.status === "no_new_message") {
          setTimeout(poll, 1500);
          return;
        }

        if (data.status === "ok" && data.message) {
          const msg = data.message;
          const msgId = msg.id ?? msg.message_id;
          if (msgId && msgId !== latestAssistantId) {
            const content = msg.content;

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

            setLatestAssistantId(msgId);
            setWaitingForReply(false);
            return;
          }
        }

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
      const saveMessageRes = await fetch(`${DB_SERVICE_URL}/messages`, {
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
      const res = await fetch(`${GETEWAY_SERVICE_URL}/trip/plan`, {
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

  const tripTypes = filters.trip_types ?? [];
  const showDifficulty = tripTypes.includes("TREKKING");

  // --------------- RENDER ---------------
  return (
    <div
      style={{
        height: "100vh",
        width: "100vw",
        background:
          "radial-gradient(circle at top, #333754 0, #1b1c25 40%, #111119 100%)",
        color: "#F9F9FB",
        fontFamily: "Inter, system-ui, -apple-system, BlinkMacSystemFont",
        display: "flex",
        flexDirection: isMobile ? "column" : "row",
        alignItems: "stretch",
        overflow: "hidden",
      }}
    >
      {/* ---- Trip Filters Sidebar ---- */}
      {isSidebarOpen && (
        <div
          style={{
            width: isMobile ? "100%" : 320,
            minWidth: isMobile ? "100%" : 260,
            background:
              "linear-gradient(180deg, #14151e 0%, #111119 45%, #101017 100%)",
            padding: "24px 18px 20px 24px",
            boxShadow: isMobile
              ? "0 4px 18px rgba(0,0,0,0.45)"
              : "2px 0 18px rgba(0,0,0,0.4)",
            display: "flex",
            flexDirection: "column",
            borderRight: isMobile ? "none" : "1px solid #262733",
            overflowY: "auto",
            maxHeight: isMobile ? "45vh" : "100vh",
          }}
        >
          {/* Sidebar header on mobile */}
          {isMobile && (
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                marginBottom: 12,
              }}
            >
              <div
                style={{
                  fontWeight: 600,
                  fontSize: ".95rem",
                  color: "#f5f5ff",
                }}
              >
                Filters
              </div>
              <button
                onClick={() => setIsSidebarOpen(false)}
                style={{
                  background: "transparent",
                  border: "none",
                  color: "#b5b5d0",
                  cursor: "pointer",
                  fontSize: "0.9rem",
                  padding: "4px 8px",
                  borderRadius: 999,
                }}
              >
                ✕ Close
              </button>
            </div>
          )}

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
                        setFilters((f) => {
                          const current = f.trip_types ?? [];
                          const updated = e.target.checked
                            ? [...current, type]
                            : current.filter((t: string) => t !== type);
                          return { ...f, trip_types: updated };
                        })
                      }
                    />
                    <span>{formatEnumLabel(type)}</span>
                  </label>
                )
              )}
            </div>
          </div>

          {/* Difficulty - ONLY visible if TREKKING selected */}
          {showDifficulty && (
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
          )}

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
                borderRadius: 8,
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
                borderRadius: 8,
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
                borderRadius: 8,
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

          {/* Must Include / Exclude */}
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
                borderRadius: 8,
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
                borderRadius: 8,
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
                borderRadius: 8,
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
          <div style={{ marginBottom: 8 }}>
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
      )}

      {/* ---- Chat Panel ---- */}
      <div
        style={{
          flex: 1,
          background: "transparent",
          display: "flex",
          flexDirection: "column",
          height: "100vh",
          minWidth: 0,
          color: "#F9F9FB",
        }}
      >
        <div
          style={{
            padding: "14px 24px",
            borderBottom: "1px solid #262733",
            display: "flex",
            alignItems: "center",
            gap: 12,
            backdropFilter: "blur(16px)",
            background:
              "linear-gradient(90deg, rgba(18,19,28,0.96), rgba(25,34,60,0.92))",
          }}
        >
          <div style={{ position: "relative", flexShrink: 0 }}>
            <button
              onClick={() => setIsSidebarOpen((open) => !open)}
              onMouseEnter={() => setIsFilterHover(true)}
              onMouseLeave={() => setIsFilterHover(false)}
              title={isSidebarOpen ? "Close sidebar" : "Open sidebar"} // fallback
              style={{
                width: 34,
                height: 34,
                borderRadius: "999px",
                border: "1px solid #34354a",
                background: "rgba(9,10,18,0.9)",
                color: "#d6d7f0",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                cursor: "pointer",
                fontSize: "1.1rem",
                lineHeight: 1,
                boxShadow: "0 2px 8px rgba(0,0,0,0.4)",
                padding: 0,
              }}
            >
              {/* Arrow exactly centered */}
              <span
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  width: "100%",
                  marginTop: "-2px",
                  height: "100%",
                }}
              >
                {isSidebarOpen ? "«" : "»"}
              </span>
            </button>

            {/* Custom tooltip stays the same */}
            {isFilterHover && (
              <div
                style={{
                  position: "absolute",
                  top: "115%",
                  left: "50%",
                  transform: "translateX(-50%)",
                  background: "#11121a",
                  color: "#f7f7fa",
                  padding: "4px 8px",
                  borderRadius: 6,
                  fontSize: "0.75rem",
                  border: "1px solid #34354a",
                  whiteSpace: "nowrap",
                  boxShadow: "0 4px 10px rgba(0,0,0,0.5)",
                  zIndex: 20,
                }}
              >
                {isSidebarOpen ? "Close sidebar" : "Open sidebar"}
              </div>
            )}
          </div>

          {/* Centered big title */}
          <div
            style={{
              flex: 1,
              display: "flex",
              justifyContent: "center",
              pointerEvents: "none", // so clicks pass through
            }}
          >
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 10,
                maxWidth: "100%",
                overflow: "hidden",
              }}
            >
              <span
                role="img"
                aria-label="plane"
                style={{ fontSize: "1.9rem", flexShrink: 0 }}
              >
                🛩️
              </span>
              <div
                style={{
                  display: "flex",
                  flexDirection: "column",
                  minWidth: 0,
                }}
              >
                <span
                  style={{
                    fontSize: "1.4rem",
                    fontWeight: 800,
                    letterSpacing: "0.06em",
                    textTransform: "uppercase",
                    background:
                      "linear-gradient(120deg, #ffffff 0%, #d7e0ff 40%, #8ba8ff 100%)",
                    WebkitBackgroundClip: "text",
                    backgroundClip: "text",
                    color: "transparent",
                    whiteSpace: "nowrap",
                    textOverflow: "ellipsis",
                    overflow: "hidden",
                  }}
                >
                  TravelBot
                </span>
                <span
                  style={{
                    fontSize: ".82rem",
                    opacity: 0.8,
                    whiteSpace: "nowrap",
                    textOverflow: "ellipsis",
                    overflow: "hidden",
                  }}
                >
                  AI Travel Planner
                </span>
              </div>
            </div>
          </div>

          {/* New chat button on the right */}
          <button
            onClick={handleNewChat}
            style={{
              background:
                "linear-gradient(135deg, #4760ff 0%, #6f9bff 45%, #4bd5ff 100%)",
              color: "#fff",
              border: "none",
              borderRadius: 999,
              padding: "7px 16px",
              fontSize: ".9rem",
              cursor: "pointer",
              marginLeft: 12,
              display: "inline-flex",
              alignItems: "center",
              gap: 6,
              boxShadow: "0 6px 18px rgba(0,0,0,0.5)",
              fontWeight: 600,
              flexShrink: 0,
            }}
          >
            <span>🧹</span>
            <span>New chat</span>
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
                    background:
                      msg.sender === "user"
                        ? "linear-gradient(135deg, #0b84ff, #4e9dff)"
                        : "rgba(18,19,30,0.96)",
                    color: msg.sender === "user" ? "#fff" : "#e9eaf0",
                    borderRadius:
                      msg.sender === "user"
                        ? "18px 18px 4px 18px"
                        : "18px 18px 18px 4px",
                    padding:
                      msg.kind === "trip_plan" && msg.sender === "assistant"
                        ? "16px 18px"
                        : "11px 15px",
                    fontSize: "0.97rem",
                    whiteSpace: "pre-line",
                    wordBreak: "break-word",
                    boxShadow:
                      msg.sender === "assistant"
                        ? "0 3px 18px rgba(0,0,0,0.42)"
                        : "0 2px 14px rgba(0,0,0,0.35)",
                    border:
                      msg.sender === "assistant" && msg.kind === "trip_plan"
                        ? "1px solid rgba(66,134,255,0.6)"
                        : "1px solid rgba(255,255,255,0.04)",
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
                    background: "rgba(25,27,40,0.95)",
                    color: "#e9eaf0",
                    borderRadius: 999,
                    padding: "8px 16px",
                    fontSize: ".9rem",
                    fontStyle: "italic",
                    boxShadow: "0 2px 14px rgba(0,0,0,0.35)",
                  }}
                >
                  TravelBot is thinking…
                </div>
              </div>
            )}
            <div ref={chatEndRef} />
          </div>
        </div>

        {/* Input area */}
        <div
          style={{
            borderTop: "1px solid #262733",
            padding: "12px 22px 16px 22px",
            background:
              "linear-gradient(180deg, rgba(15,16,24,0.96), rgba(10,11,18,0.98))",
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
              alignItems: "flex-end",
            }}
            onSubmit={(e) => {
              e.preventDefault();
              sendMessage();
            }}
          >
            {/* TEXTAREA: Shift+Enter = newline, Enter = send */}
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask TravelBot for a trip plan…"
              rows={1}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  sendMessage();
                }
              }}
              style={{
                flex: 1,
                padding: "11px 14px",
                borderRadius: 12,
                border: "1px solid #343545",
                background: "#11121a",
                color: "#f7f7fa",
                fontSize: ".96rem",
                resize: "none",
                maxHeight: 130,
                lineHeight: 1.4,
                overflowY: "auto",
              }}
              disabled={loading || waitingForReply}
            />
            <button
              type="submit"
              disabled={loading || waitingForReply || !input.trim()}
              style={{
                background:
                  loading || waitingForReply || !input.trim()
                    ? "rgba(76,78,104,0.8)"
                    : "linear-gradient(135deg, #0b84ff, #5f9bff)",
                color: "#fff",
                borderRadius: 999,
                fontWeight: 600,
                padding: "10px 20px",
                fontSize: ".9rem",
                border: "none",
                cursor:
                  loading || waitingForReply || !input.trim()
                    ? "not-allowed"
                    : "pointer",
                display: "inline-flex",
                alignItems: "center",
                gap: 6,
                boxShadow:
                  loading || waitingForReply || !input.trim()
                    ? "none"
                    : "0 4px 14px rgba(0,0,0,0.45)",
                transition: "transform 0.08s ease, box-shadow 0.08s ease",
              }}
            >
              <span>📨</span>
              <span>Send</span>
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
