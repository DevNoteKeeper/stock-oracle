import { useState, useRef, useEffect } from "react";
import { MessageCircle, X, Send, Loader, Bot, User, Minimize2 } from "lucide-react";
import type { StockData } from "../App";

interface Message {
  role: "user" | "assistant";
  content: string;
  streaming?: boolean;
}

interface Props {
  stockData: StockData | null;
  analysisText: string;
  isAnalysisDone: boolean;
}

export default function AiChat({ stockData, analysisText, isAnalysisDone }: Props) {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // 채팅창 열릴 때 웰컴 메시지
  useEffect(() => {
    if (isOpen && messages.length === 0 && stockData) {
      setMessages([{
        role: "assistant",
        content: `${stockData.company_name} 분석이 완료됐어요! 궁금한 점이 있으면 무엇이든 물어보세요 😊\n\n예시:\n• "손절가를 구체적으로 알려줘"\n• "지금 RSI 수준이 위험한가요?"\n• "외국인 매도가 계속될 것 같나요?"\n• "분할매수 전략 자세히 설명해줘"`,
      }]);
    }
  }, [isOpen]);

  // 메시지 추가 시 스크롤
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // 채팅창 열릴 때 입력창 포커스
  useEffect(() => {
    if (isOpen) {
      setTimeout(() => inputRef.current?.focus(), 100);
    }
  }, [isOpen]);

  const handleSend = async () => {
    if (!input.trim() || isLoading) return;

    const userMsg = input.trim();
    setInput("");
    setMessages(prev => [...prev, { role: "user", content: userMsg }]);
    setIsLoading(true);

    // assistant 스트리밍 메시지 추가
    setMessages(prev => [...prev, { role: "assistant", content: "", streaming: true }]);

    try {
      const response = await fetch("http://localhost:8000/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: userMsg,
          stock_data: stockData,
          analysis_text: analysisText,
          history: messages.slice(-10).map(m => ({
            role: m.role,
            content: m.content,
          })),
        }),
      });

      if (!response.ok) throw new Error("서버 오류");

      const reader = response.body!.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let fullText = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          try {
            const msg = JSON.parse(line.slice(6));
            if (msg.type === "token") {
              fullText += msg.payload;
              setMessages(prev => {
                const updated = [...prev];
                updated[updated.length - 1] = {
                  role: "assistant",
                  content: fullText,
                  streaming: true,
                };
                return updated;
              });
            } else if (msg.type === "done") {
              setMessages(prev => {
                const updated = [...prev];
                updated[updated.length - 1] = {
                  role: "assistant",
                  content: fullText,
                  streaming: false,
                };
                return updated;
              });
            }
          } catch {
            // 파싱 실패 무시
          }
        }
      }
    } catch {
      setMessages(prev => {
        const updated = [...prev];
        updated[updated.length - 1] = {
          role: "assistant",
          content: "❌ 오류가 발생했어요. 백엔드 서버가 실행 중인지 확인해주세요.",
          streaming: false,
        };
        return updated;
      });
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  // 분석 완료 전에는 버튼 숨김
  if (!isAnalysisDone || !stockData) return null;

  return (
    <>
      {/* 채팅 패널 */}
      {isOpen && (
        <div
          style={{
            position: "fixed",
            bottom: 90,
            right: 24,
            width: 380,
            height: 520,
            background: "var(--bg-card)",
            border: "1px solid var(--border)",
            borderRadius: 20,
            display: "flex",
            flexDirection: "column",
            boxShadow: "0 24px 64px rgba(0,0,0,0.5)",
            zIndex: 1000,
            overflow: "hidden",
          }}
        >
          {/* 헤더 */}
          <div
            style={{
              padding: "14px 16px",
              borderBottom: "1px solid var(--border)",
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              background: "var(--bg-panel)",
              flexShrink: 0,
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <div
                style={{
                  width: 28, height: 28, borderRadius: 8,
                  background: "linear-gradient(135deg,#0ea5e9,#0284c7)",
                  display: "flex", alignItems: "center", justifyContent: "center",
                  fontSize: 13, fontWeight: 700, color: "white",
                }}
              >
                AI
              </div>
              <div>
                <p style={{ fontSize: 13, fontWeight: 600, color: "var(--text-primary)", lineHeight: 1.2 }}>
                  AI 분석 어시스턴트
                </p>
                <p style={{ fontSize: 10, color: "var(--text-muted)", lineHeight: 1.2 }}>
                  {stockData.company_name} 분석 기반
                </p>
              </div>
            </div>
            <div style={{ display: "flex", gap: 6 }}>
              <button
                onClick={() => setIsOpen(false)}
                style={{
                  width: 28, height: 28, borderRadius: 8,
                  background: "var(--bg-base)", border: "1px solid var(--border)",
                  color: "var(--text-muted)", cursor: "pointer",
                  display: "flex", alignItems: "center", justifyContent: "center",
                }}
              >
                <Minimize2 size={13} />
              </button>
              <button
                onClick={() => { setIsOpen(false); setMessages([]); }}
                style={{
                  width: 28, height: 28, borderRadius: 8,
                  background: "var(--bg-base)", border: "1px solid var(--border)",
                  color: "var(--text-muted)", cursor: "pointer",
                  display: "flex", alignItems: "center", justifyContent: "center",
                }}
              >
                <X size={13} />
              </button>
            </div>
          </div>

          {/* 메시지 목록 */}
          <div
            style={{
              flex: 1,
              overflowY: "auto",
              padding: "12px 14px",
              display: "flex",
              flexDirection: "column",
              gap: 10,
            }}
          >
            {messages.map((msg, i) => (
              <div
                key={i}
                style={{
                  display: "flex",
                  flexDirection: msg.role === "user" ? "row-reverse" : "row",
                  alignItems: "flex-start",
                  gap: 8,
                }}
              >
                {/* 아바타 */}
                <div
                  style={{
                    width: 26, height: 26, borderRadius: 8, flexShrink: 0,
                    background: msg.role === "user"
                      ? "linear-gradient(135deg,#6366f1,#8b5cf6)"
                      : "linear-gradient(135deg,#0ea5e9,#0284c7)",
                    display: "flex", alignItems: "center", justifyContent: "center",
                  }}
                >
                  {msg.role === "user"
                    ? <User size={13} color="white" />
                    : <Bot size={13} color="white" />
                  }
                </div>

                {/* 말풍선 */}
                <div
                  style={{
                    maxWidth: "78%",
                    padding: "9px 12px",
                    borderRadius: msg.role === "user" ? "14px 4px 14px 14px" : "4px 14px 14px 14px",
                    background: msg.role === "user"
                      ? "linear-gradient(135deg,#0ea5e9,#0284c7)"
                      : "var(--bg-panel)",
                    border: msg.role === "user" ? "none" : "1px solid var(--border)",
                    fontSize: 13,
                    lineHeight: 1.6,
                    color: msg.role === "user" ? "white" : "var(--text-primary)",
                    whiteSpace: "pre-wrap",
                    wordBreak: "break-word",
                  }}
                >
                  {msg.content}
                  {msg.streaming && (
                    <span
                      style={{
                        display: "inline-block",
                        width: 6, height: 14,
                        background: "var(--accent)",
                        marginLeft: 3,
                        borderRadius: 2,
                        animation: "blink 1s step-end infinite",
                        verticalAlign: "text-bottom",
                      }}
                    />
                  )}
                </div>
              </div>
            ))}

            {/* 로딩 (메시지 전송 직후) */}
            {isLoading && messages[messages.length - 1]?.content === "" && (
              <div style={{ display: "flex", gap: 8, alignItems: "flex-start" }}>
                <div style={{
                  width: 26, height: 26, borderRadius: 8,
                  background: "linear-gradient(135deg,#0ea5e9,#0284c7)",
                  display: "flex", alignItems: "center", justifyContent: "center",
                }}>
                  <Bot size={13} color="white" />
                </div>
                <div style={{
                  padding: "10px 14px", borderRadius: "4px 14px 14px 14px",
                  background: "var(--bg-panel)", border: "1px solid var(--border)",
                  display: "flex", gap: 5, alignItems: "center",
                }}>
                  {[0, 1, 2].map(i => (
                    <div key={i} style={{
                      width: 6, height: 6, borderRadius: "50%",
                      background: "var(--accent)",
                      animation: `bounce 1.2s ease-in-out ${i * 0.2}s infinite`,
                    }} />
                  ))}
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* 입력창 */}
          <div
            style={{
              padding: "10px 12px",
              borderTop: "1px solid var(--border)",
              display: "flex",
              gap: 8,
              alignItems: "flex-end",
              background: "var(--bg-panel)",
              flexShrink: 0,
            }}
          >
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="질문을 입력하세요... (Enter 전송, Shift+Enter 줄바꿈)"
              rows={1}
              style={{
                flex: 1,
                background: "var(--bg-base)",
                border: "1px solid var(--border)",
                borderRadius: 10,
                padding: "8px 12px",
                color: "var(--text-primary)",
                fontSize: 13,
                lineHeight: 1.5,
                resize: "none",
                outline: "none",
                maxHeight: 100,
                overflowY: "auto",
                fontFamily: "var(--font-sans)",
              }}
              onInput={(e) => {
                const el = e.currentTarget;
                el.style.height = "auto";
                el.style.height = `${Math.min(el.scrollHeight, 100)}px`;
              }}
            />
            <button
              onClick={handleSend}
              disabled={!input.trim() || isLoading}
              style={{
                width: 36, height: 36, borderRadius: 10, flexShrink: 0,
                background: input.trim() && !isLoading
                  ? "linear-gradient(135deg,#0ea5e9,#0284c7)"
                  : "var(--bg-base)",
                border: `1px solid ${input.trim() && !isLoading ? "transparent" : "var(--border)"}`,
                color: input.trim() && !isLoading ? "white" : "var(--text-muted)",
                cursor: input.trim() && !isLoading ? "pointer" : "not-allowed",
                display: "flex", alignItems: "center", justifyContent: "center",
                transition: "all 0.15s",
              }}
            >
              {isLoading
                ? <Loader size={14} style={{ animation: "spin 1s linear infinite" }} />
                : <Send size={14} />
              }
            </button>
          </div>
        </div>
      )}

      {/* 플로팅 버튼 */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        style={{
          position: "fixed",
          bottom: 24,
          right: 24,
          width: 56,
          height: 56,
          borderRadius: "50%",
          background: isOpen
            ? "var(--bg-card)"
            : "linear-gradient(135deg,#0ea5e9,#0284c7)",
          border: isOpen ? "1px solid var(--border)" : "none",
          color: isOpen ? "var(--text-muted)" : "white",
          cursor: "pointer",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          boxShadow: isOpen
            ? "none"
            : "0 8px 32px rgba(14,165,233,0.4)",
          zIndex: 1001,
          transition: "all 0.2s",
        }}
        onMouseEnter={(e) => {
          if (!isOpen) e.currentTarget.style.transform = "scale(1.1)";
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.transform = "scale(1)";
        }}
      >
        {isOpen ? <X size={20} /> : <MessageCircle size={22} />}
      </button>

      {/* 애니메이션 CSS */}
      <style>{`
        @keyframes bounce {
          0%, 60%, 100% { transform: translateY(0); }
          30% { transform: translateY(-6px); }
        }
        @keyframes blink {
          0%, 100% { opacity: 1; }
          50% { opacity: 0; }
        }
        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
      `}</style>
    </>
  );
}