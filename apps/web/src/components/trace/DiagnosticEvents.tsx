"use client";

import { useState, useMemo } from "react";

interface DiagnosticEvent {
  event_type: string;
  topics: string[];
  data: Record<string, string>;
  timeline_position: number;
}

interface DiagnosticEventsProps {
  events: DiagnosticEvent[];
}

function formatEventType(eventType: string): string {
  switch (eventType) {
    case "contract":
      return "Contract Event";
    case "system":
      return "System Event";
    case "debug":
      return "Debug Event";
    default:
      return eventType.charAt(0).toUpperCase() + eventType.slice(1);
  }
}

function getEventTypeColor(eventType: string): string {
  switch (eventType) {
    case "contract":
      return "bg-purple-100 text-purple-800";
    case "system":
      return "bg-blue-100 text-blue-800";
    case "debug":
      return "bg-yellow-100 text-yellow-800";
    default:
      return "bg-gray-100 text-gray-800";
  }
}

function getEventTypeIcon(eventType: string): string {
  switch (eventType) {
    case "contract":
      return "⬡";
    case "system":
      return "⚙️";
    case "debug":
      return "🔍";
    default:
      return "📋";
  }
}

export function DiagnosticEvents({ events }: DiagnosticEventsProps) {
  const [filter, setFilter] = useState<string>("");
  const [selectedEventType, setSelectedEventType] = useState<string>("all");

  const eventTypes = useMemo(() => {
    const types = new Set(events.map((e) => e.event_type));
    return Array.from(types).sort();
  }, [events]);

  const filteredEvents = useMemo(() => {
    return events.filter((event) => {
      const matchesFilter =
        filter === "" ||
        event.topics.some((t) => t.toLowerCase().includes(filter.toLowerCase())) ||
        Object.entries(event.data).some(
          ([k, v]) =>
            k.toLowerCase().includes(filter.toLowerCase()) ||
            v.toLowerCase().includes(filter.toLowerCase())
        );
      const matchesType =
        selectedEventType === "all" || event.event_type === selectedEventType;
      return matchesFilter && matchesType;
    });
  }, [events, filter, selectedEventType]);

  return (
    <div className="bg-white rounded-lg shadow p-6">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-xl font-semibold">Diagnostic Events</h2>
        <span className="px-3 py-1 text-sm font-medium bg-gray-100 text-gray-700 rounded">
          {filteredEvents.length} / {events.length} events
        </span>
      </div>

      <div className="mb-4 space-y-3">
        <div className="relative">
          <input
            type="text"
            placeholder="Filter by topic, key, or value..."
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 pl-10"
          />
          <span className="absolute left-3 top-2.5 text-gray-400">🔍</span>
        </div>

        <div className="flex flex-wrap gap-2">
          <button
            onClick={() => setSelectedEventType("all")}
            className={`px-3 py-1 text-sm font-medium rounded-full transition-colors ${
              selectedEventType === "all"
                ? "bg-blue-600 text-white"
                : "bg-gray-100 text-gray-700 hover:bg-gray-200"
            }`}
          >
            All
          </button>
          {eventTypes.map((type) => (
            <button
              key={type}
              onClick={() => setSelectedEventType(type)}
              className={`px-3 py-1 text-sm font-medium rounded-full transition-colors ${
                selectedEventType === type
                  ? "bg-purple-600 text-white"
                  : "bg-gray-100 text-gray-700 hover:bg-gray-200"
              }`}
            >
              {formatEventType(type)}
            </button>
          ))}
        </div>
      </div>

      <div className="space-y-3 max-h-96 overflow-y-auto">
        {filteredEvents.length === 0 ? (
          <div className="text-center py-8 text-gray-500">
            {events.length === 0 ? (
              "No diagnostic events captured for this transaction."
            ) : (
              "No events match the current filters."
            )}
          </div>
        ) : (
          filteredEvents.map((event, idx) => (
            <div
              key={`event-${event.timeline_position}`}
              className="p-4 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors"
            >
              <div className="flex items-start justify-between mb-3">
                <div className="flex items-center space-x-3">
                  <span className="text-lg">{getEventTypeIcon(event.event_type)}</span>
                  <div>
                    <div className="flex items-center space-x-2">
                      <span className="font-mono text-sm font-medium">
                        #{event.timeline_position}
                      </span>
                      <span
                        className={`px-2 py-0.5 text-xs font-medium rounded ${getEventTypeColor(
                          event.event_type
                        )}`}
                      >
                        {formatEventType(event.event_type)}
                      </span>
                    </div>
                  </div>
                </div>
              </div>

              {event.topics.length > 0 && (
                <div className="mb-3">
                  <div className="text-xs text-gray-500 mb-1">Topics</div>
                  <div className="flex flex-wrap gap-2">
                    {event.topics.map((topic, topicIdx) => (
                      <span
                        key={topicIdx}
                        className="px-2 py-1 text-xs font-mono bg-gray-100 text-gray-700 rounded border border-gray-200"
                      >
                        {topic}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {Object.keys(event.data).length > 0 && (
                <div>
                  <div className="text-xs text-gray-500 mb-1">Data</div>
                  <div className="space-y-1">
                    {Object.entries(event.data).map(([key, value], dataIdx) => (
                      <div
                        key={dataIdx}
                        className="flex items-start gap-3 text-sm"
                      >
                        <span className="font-mono text-gray-600 whitespace-nowrap min-w-[120px]">
                          {key}
                        </span>
                        <span className="font-mono text-gray-800 break-all flex-1">
                          {value}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {event.topics.length === 0 &&
                Object.keys(event.data).length === 0 && (
                  <p className="text-sm text-gray-500 italic">
                    No topics or data for this event.
                  </p>
                )}
            </div>
          ))
        )}
      </div>
    </div>
  );
}

export default DiagnosticEvents;