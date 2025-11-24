"use client";
import { useState, useRef, useEffect } from "react";

type ChatMessage = { sender: "user" | "assistant"; text: string };

type Filters = {
  trip_types?: string[];
  difficulty?: string;
  budget_level?: string;
  duration_days?: number;
  group_type?: string;
  travel_modes?: string[];
  accommodation?: string[];
  accessibility?: string[];
  meal_preferences?: string[];
  must_include?: string[];
  must_exclude?: string[];
  interest_tags?: string[];
  events_only?: boolean;
  amenities?: string[];
  [key: string]: any;
};

export default function HomePage() {
  const [input, setInput] = useState("");
  const [threadId, setThreadId] = useState<string | null>(null);
  const [chat, setChat] = useState<ChatMessage[]>([]);
  const [filters, setFilters] = useState<Filters>({});
  const [loading, setLoading] = useState(false);
  const chatEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chat, loading]);

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
          // fallback to new thread
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
    localStorage.removeItem("thread_id");
    const res = await fetch("http://localhost:8001/threads", {
      method: "POST",
    });
    const data = await res.json();
    setThreadId(data.id);
    localStorage.setItem("thread_id", data.id);
  };

  //---- SEND MESSAGE WITH FILTERS AND CHAT HISTORY ----
  const sendMessage = async () => {
    if (!input.trim() || loading || !threadId) return;
    setChat((prev) => [...prev, { sender: "user", text: input }]);
    setLoading(true);
    try {
      // 1. Save message in /messages (chat DB)
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
    } catch (err) {
      setChat((prev) => [
        ...prev,
        { sender: "assistant", text: "Error contacting server." },
      ]);
    }
    setInput("");
    setLoading(false);
  };

  return (
    <div
      style={{
        height: "100vh",
        width: "100vw",
        background: "#22232a",
        color: "#f6f6f6",
        fontFamily: "Inter, Arial, sans-serif",
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
          minWidth: 190,
          background: "#191a20",
          padding: "38px 14px 0 28px",
          boxShadow: "0 6px 22px 0 rgba(20,20,30,0.16)",
          display: "flex",
          flexDirection: "column",
          borderRight: "1px solid #292932",
          overflowY: "auto",
        }}
      >
        <div
          style={{
            fontSize: "1.15rem",
            fontWeight: 600,
            marginBottom: 24,
            letterSpacing: ".2px",
          }}
        >
          <span role="img" aria-label="filters" style={{ marginRight: 6 }}>
            🧮
          </span>
          Trip Filters
        </div>

        {/* Trip Types */}
        <div style={{ marginBottom: 18 }}>
          <div style={{ fontWeight: 500, color: "#cdcddc", marginBottom: 3 }}>
            Trip type
          </div>
          {["TREKKING", "CAMPING", "CITY", "ROAD_TRIP", "HIKING"].map(
            (type) => (
              <label
                key={type}
                style={{
                  display: "block",
                  marginBottom: 3,
                  fontSize: ".98rem",
                  color: "#aaa",
                }}
              >
                <input
                  type="checkbox"
                  checked={filters.trip_types?.includes(type) || false}
                  onChange={(e) =>
                    setFilters((f) => ({
                      ...f,
                      trip_types: e.target.checked
                        ? [...(f.trip_types || []), type]
                        : (f.trip_types || []).filter(
                            (t: string) => t !== type
                          ),
                    }))
                  }
                />{" "}
                {type.charAt(0) + type.slice(1).toLowerCase().replace("_", " ")}
              </label>
            )
          )}
        </div>

        {/* Difficulty */}
        <div style={{ marginBottom: 18 }}>
          <div style={{ fontWeight: 500, color: "#cdcddc", marginBottom: 3 }}>
            Difficulty
          </div>
          {["EASY", "MODERATE", "HARD"].map((diff) => (
            <label
              key={diff}
              style={{ marginRight: 12, fontSize: ".98rem", color: "#aaa" }}
            >
              <input
                type="radio"
                name="difficulty"
                checked={filters.difficulty === diff}
                onChange={() => setFilters((f) => ({ ...f, difficulty: diff }))}
              />{" "}
              {diff[0] + diff.slice(1).toLowerCase()}
            </label>
          ))}
        </div>

        {/* Budget Level */}
        <div style={{ marginBottom: 18 }}>
          <div style={{ fontWeight: 500, color: "#cdcddc", marginBottom: 3 }}>
            Budget (USD)
          </div>
          <select
            value={filters.budget_level || ""}
            onChange={(e) =>
              setFilters((f) => ({ ...f, budget_level: e.target.value }))
            }
            style={{
              marginTop: 6,
              width: "100%",
              padding: "8px",
              borderRadius: 6,
              background: "#23242b",
              color: "#f7f7fa",
              border: "1px solid #393a43",
            }}
          >
            <option value="">Any</option>
            <option value="USD_0_500">0 - 500</option>
            <option value="USD_500_1500">500 - 1,500</option>
            <option value="USD_1500_3000">1,500 - 3,000</option>
            <option value="USD_3000_PLUS">3,000+</option>
          </select>
        </div>

        {/* Duration Days */}
        <div style={{ marginBottom: 18 }}>
          <div style={{ fontWeight: 500, color: "#cdcddc", marginBottom: 3 }}>
            Duration (days)
          </div>
          <input
            type="number"
            min={1}
            max={30}
            value={filters.duration_days || ""}
            onChange={(e) =>
              setFilters((f) => ({
                ...f,
                duration_days: Number(e.target.value) || "",
              }))
            }
            style={{
              width: "75%",
              padding: "7px",
              borderRadius: 6,
              border: "1px solid #393a43",
              background: "#23242b",
              color: "#f7f7fa",
            }}
            placeholder="5"
          />
        </div>

        {/* Group type */}
        <div style={{ marginBottom: 18 }}>
          <div style={{ fontWeight: 500, color: "#cdcddc", marginBottom: 3 }}>
            Group Type
          </div>
          <select
            value={filters.group_type || ""}
            onChange={(e) =>
              setFilters((f) => ({ ...f, group_type: e.target.value }))
            }
            style={{
              marginTop: 6,
              width: "100%",
              padding: "8px",
              borderRadius: 6,
              background: "#23242b",
              color: "#f7f7fa",
              border: "1px solid #393a43",
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

        {/* Travel modes */}
        <div style={{ marginBottom: 18 }}>
          <div style={{ fontWeight: 500, color: "#cdcddc", marginBottom: 3 }}>
            Travel Modes
          </div>
          {["CAR", "BUS", "FLIGHT", "BIKE"].map((mode) => (
            <label
              key={mode}
              style={{
                display: "inline-block",
                marginRight: 12,
                fontSize: ".98rem",
                color: "#aaa",
              }}
            >
              <input
                type="checkbox"
                checked={filters.travel_modes?.includes(mode) || false}
                onChange={(e) =>
                  setFilters((f) => ({
                    ...f,
                    travel_modes: e.target.checked
                      ? [...(f.travel_modes || []), mode]
                      : (f.travel_modes || []).filter(
                          (m: string) => m !== mode
                        ),
                  }))
                }
              />
              {mode.charAt(0) + mode.slice(1).toLowerCase()}
            </label>
          ))}
        </div>
        {/* Accommodation */}
        <div style={{ marginBottom: 18 }}>
          <div style={{ fontWeight: 500, color: "#cdcddc", marginBottom: 3 }}>
            Accommodation
          </div>
          {["CAMPING", "HOTEL", "HOSTEL", "LODGE"].map((acc) => (
            <label
              key={acc}
              style={{
                display: "inline-block",
                marginRight: 12,
                fontSize: ".98rem",
                color: "#aaa",
              }}
            >
              <input
                type="checkbox"
                checked={filters.accommodation?.includes(acc) || false}
                onChange={(e) =>
                  setFilters((f) => ({
                    ...f,
                    accommodation: e.target.checked
                      ? [...(f.accommodation || []), acc]
                      : (f.accommodation || []).filter(
                          (a: string) => a !== acc
                        ),
                  }))
                }
              />
              {acc.charAt(0) + acc.slice(1).toLowerCase()}
            </label>
          ))}
        </div>
        {/* Accessibility */}
        <div style={{ marginBottom: 18 }}>
          <div style={{ fontWeight: 500, color: "#cdcddc", marginBottom: 3 }}>
            Accessibility
          </div>
          {["PET_FRIENDLY", "WHEELCHAIR", "KIDS"].map((tag) => (
            <label
              key={tag}
              style={{
                display: "inline-block",
                marginRight: 12,
                fontSize: ".98rem",
                color: "#aaa",
              }}
            >
              <input
                type="checkbox"
                checked={filters.accessibility?.includes(tag) || false}
                onChange={(e) =>
                  setFilters((f) => ({
                    ...f,
                    accessibility: e.target.checked
                      ? [...(f.accessibility || []), tag]
                      : (f.accessibility || []).filter(
                          (a: string) => a !== tag
                        ),
                  }))
                }
              />
              {tag.replace("_", " ")}
            </label>
          ))}
        </div>
        {/* Meal preferences */}
        <div style={{ marginBottom: 18 }}>
          <div style={{ fontWeight: 500, color: "#cdcddc", marginBottom: 3 }}>
            Meal Preferences
          </div>
          {["VEGETARIAN", "VEGAN", "GLUTEN_FREE", "NONE"].map((mp) => (
            <label
              key={mp}
              style={{
                display: "inline-block",
                marginRight: 12,
                fontSize: ".98rem",
                color: "#aaa",
              }}
            >
              <input
                type="checkbox"
                checked={filters.meal_preferences?.includes(mp) || false}
                onChange={(e) =>
                  setFilters((f) => ({
                    ...f,
                    meal_preferences: e.target.checked
                      ? [...(f.meal_preferences || []), mp]
                      : (f.meal_preferences || []).filter(
                          (m: string) => m !== mp
                        ),
                  }))
                }
              />
              {mp.replace("_", " ")}
            </label>
          ))}
        </div>
        {/* Must Include / Must Exclude */}
        <div style={{ marginBottom: 18 }}>
          <div style={{ fontWeight: 500, color: "#cdcddc", marginBottom: 3 }}>
            Must Include
          </div>
          <input
            type="text"
            placeholder="e.g. NATIONAL_PARK, MUSEUM"
            value={filters.must_include?.join(", ") || ""}
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
              border: "1px solid #393a43",
              background: "#23242b",
              color: "#f7f7fa",
              marginBottom: 7,
            }}
          />
          <div style={{ fontWeight: 500, color: "#cdcddc", marginBottom: 3 }}>
            Must Exclude
          </div>
          <input
            type="text"
            placeholder="e.g. FLIGHT"
            value={filters.must_exclude?.join(", ") || ""}
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
              border: "1px solid #393a43",
              background: "#23242b",
              color: "#f7f7fa",
            }}
          />
        </div>
        {/* Interest Tags */}
        <div style={{ marginBottom: 18 }}>
          <div style={{ fontWeight: 500, color: "#cdcddc", marginBottom: 3 }}>
            Interest Tags
          </div>
          <input
            type="text"
            placeholder="e.g. PHOTOGRAPHY, NATURE"
            value={filters.interest_tags?.join(", ") || ""}
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
              border: "1px solid #393a43",
              background: "#23242b",
              color: "#f7f7fa",
            }}
          />
        </div>
        {/* Events only */}
        <div style={{ marginBottom: 16 }}>
          <label style={{ fontWeight: 500, color: "#cdcddc" }}>
            <input
              type="checkbox"
              checked={filters.events_only || false}
              onChange={(e) =>
                setFilters((f) => ({ ...f, events_only: e.target.checked }))
              }
              style={{ marginRight: 7 }}
            />
            Events Only
          </label>
        </div>
        {/* Amenities */}
        <div style={{ marginBottom: 18 }}>
          <div style={{ fontWeight: 500, color: "#cdcddc", marginBottom: 3 }}>
            Amenities
          </div>
          {["WI_FI", "SPA", "POOL", "PARKING"].map((am) => (
            <label
              key={am}
              style={{
                display: "inline-block",
                marginRight: 12,
                fontSize: ".98rem",
                color: "#aaa",
              }}
            >
              <input
                type="checkbox"
                checked={filters.amenities?.includes(am) || false}
                onChange={(e) =>
                  setFilters((f) => ({
                    ...f,
                    amenities: e.target.checked
                      ? [...(f.amenities || []), am]
                      : (f.amenities || []).filter((a: string) => a !== am),
                  }))
                }
              />
              {am.replace("_", " ")}
            </label>
          ))}
        </div>
      </div>

      {/* ---- Chat Panel ---- */}
      <div
        style={{
          flex: 1,
          background: "#23242b",
          display: "flex",
          flexDirection: "column",
          height: "100vh",
          minWidth: 340,
        }}
      >
        <div
          style={{
            padding: "24px 32px 14px 32px",
            borderBottom: "1px solid #292932",
            fontWeight: 600,
            fontSize: "1.18rem",
            justifyContent: "space-between",
            display: "flex",
            alignItems: "center",
          }}
        >
          <span>
            <span role="img" aria-label="plane">
              🛩️
            </span>{" "}
            TRAVEL BOT - Your AI travel chatbot
          </span>
          <button
            onClick={handleNewChat}
            style={{
              background: "#363649",
              color: "#fff",
              border: "none",
              borderRadius: 7,
              padding: "6px 18px",
              fontSize: ".98rem",
              cursor: "pointer",
              marginLeft: "auto",
              marginRight: 0,
            }}
          >
            New Chat
          </button>
        </div>
        <div
          style={{
            flex: 1,
            overflowY: "auto",
            padding: "28px 30px 10px 30px",
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
                marginBottom: 18,
              }}
            >
              <div
                style={{
                  maxWidth: "75%",
                  background: msg.sender === "user" ? "#0081fa" : "#393a41",
                  color: msg.sender === "user" ? "#fff" : "#e9eaf0",
                  borderRadius: 15,
                  padding: "14px 22px",
                  fontSize: "1.08rem",
                  whiteSpace: "pre-wrap",
                  boxShadow:
                    msg.sender === "assistant"
                      ? "0 2px 18px rgba(0,0,0,0.07)"
                      : undefined,
                }}
              >
                {msg.text}
              </div>
            </div>
          ))}
          {loading && (
            <div
              style={{
                display: "flex",
                justifyContent: "flex-start",
                marginBottom: 18,
              }}
            >
              <div
                style={{
                  background: "#393a41",
                  color: "#e9eaf0",
                  borderRadius: 15,
                  padding: "14px 22px",
                  fontSize: "1.08rem",
                  fontStyle: "italic",
                }}
              >
                TravelBot is thinking…
              </div>
            </div>
          )}
          <div ref={chatEndRef} />
        </div>
        <div
          style={{
            borderTop: "1px solid #2a2b35",
            padding: "22px 32px",
            background: "#292933",
          }}
        >
          <form
            style={{ display: "flex", gap: 12 }}
            onSubmit={(e) => {
              e.preventDefault();
              sendMessage();
            }}
          >
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask TravelBot..."
              style={{
                flex: 1,
                padding: "16px 20px",
                borderRadius: 13,
                border: "1px solid #34343a",
                background: "#181920",
                color: "#f7f7fa",
                fontSize: "1.04rem",
              }}
              disabled={loading}
            />
            <button
              type="submit"
              disabled={loading || !input.trim()}
              style={{
                background: loading || !input.trim() ? "#43444d" : "#007fff",
                color: "#fff",
                borderRadius: 10,
                fontWeight: 600,
                padding: "0 28px",
                fontSize: "1.07rem",
                border: "none",
                cursor: loading ? "not-allowed" : "pointer",
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
