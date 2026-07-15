import {useEffect, useMemo, useState} from "react";
import {useLocation, useNavigate} from "react-router-dom";
import {useQuery} from "@connectrpc/connect-query";
import {
  getDailyHighlights,
  listMatchDays
} from "proto/highlights_service-HighlightsService_connectquery.js";
import {Accolade} from "proto/highlights_service_pb.js";
import {AccoladeCard} from "client/components/AccoladeCard.js";
import {ErrorState} from "client/components/ErrorState.js";
import {LoadingState} from "client/components/LoadingState.js";

type AccoladeWithPlayer = { accolade: Accolade; playerName: string };

export function formatMatchDayString(year: number, month: number, day: number): string {
  const m = String(month).padStart(2, '0');
  const d = String(day).padStart(2, '0');
  return `${year}-${m}-${d}`;
}

export function parseMatchDayString(dateStr: string | null | undefined): {year: number, month: number, day: number} | undefined {
  if (!dateStr) return undefined;
  const parts = dateStr.split('-');
  if (parts.length !== 3) return undefined;
  const [year, month, day] = parts.map(Number);
  if (isNaN(year) || isNaN(month) || isNaN(day)) return undefined;
  return {year, month, day};
}

export function AccoladesPage() {
  const location = useLocation();
  const navigate = useNavigate();

  const matchDaysQuery = useQuery(listMatchDays, {timezone: "-05:00"}, {
    select: (data) => data.matchDays.map(d => formatMatchDayString(d.year, d.month, d.day))
  });

  const matchDays = matchDaysQuery.data ?? [];
  const hasNoDays = matchDays.length === 0;

  const hash = location.hash.substring(1);
  const currentIndex = hasNoDays ? 0 : Math.max(0, matchDays.indexOf(hash));
  const currentDayString = !hasNoDays ? matchDays[currentIndex] : null;

  // Auto-correct URL if it doesn't match the resolved current day
  useEffect(() => {
    if (currentDayString && hash !== currentDayString) {
      navigate(`#${currentDayString}`, {replace: true});
    }
  }, [currentDayString, hash, navigate]);

  const dateInput = useMemo(() => parseMatchDayString(currentDayString), [currentDayString]);

  const highlightsQuery = useQuery(
      getDailyHighlights,
      dateInput ? {
        date: dateInput,
        timezone: "-05:00",
        readMask: {
          paths: ["players.accolades", "players.player.steam_name"]
        },
      } : undefined,
      {
        enabled: dateInput !== undefined,
        select: (data) => data.players.flatMap(p =>
            (p.accolades || []).map(accolade => ({
              accolade, playerName: p.player?.steamName ?? "Unknown"
            }))
        )
      },
  );

  const accolades: AccoladeWithPlayer[] = highlightsQuery.data ?? [];

  const loading = matchDaysQuery.isLoading || (highlightsQuery.isFetching && !highlightsQuery.data);
  const error = matchDaysQuery.isError || highlightsQuery.isError;

  const displayDate = currentDayString
      ? new Date(currentDayString + 'T00:00:00-05:00').toLocaleDateString('en-US', {
        weekday: 'long',
        year: 'numeric',
        month: 'long',
        day: 'numeric'
      })
      : (matchDaysQuery.isError ? "Error" : "No Match Days Found");

  return (
      <>
        <div
            className="flex justify-between items-center mb-8 bg-dark-card p-4 rounded-xl border border-dark-border">
          <button
              onClick={() => navigate('#' + matchDays[currentIndex + 1])}
              disabled={hasNoDays || currentIndex >= matchDays.length - 1}
              className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-white rounded-lg transition-colors cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
          >
            &larr; Previous Match Day
          </button>
          <div className="text-xl font-bold text-brand-400">
            {displayDate}
          </div>
          <button
              onClick={() => navigate('#' + matchDays[currentIndex - 1])}
              disabled={hasNoDays || currentIndex <= 0}
              className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-white rounded-lg transition-colors cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Next Match Day &rarr;
          </button>
        </div>

        {loading && (
            <LoadingState message="Chickens are crunching the stats..." />
        )}

        {error && !loading && (
            <ErrorState message="Failed to load accolades. Please try again later."/>
        )}

        {!loading && !error && accolades.length === 0 && !hasNoDays && (
            <div className="text-center py-16 text-slate-400">
              <p className="text-lg font-medium">No accolades available for this day.</p>
              <p className="text-sm text-slate-500 mt-1">Even the chickens left.</p>
            </div>
        )}

        {!loading && !error && accolades.length > 0 && (
            <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
              {accolades.map((acc) => (
                  <AccoladeCard key={`${acc.playerName}-${acc.accolade.name}`}
                                accolade={acc.accolade} playerName={acc.playerName}/>
              ))}
            </div>
        )}
      </>
  );
}
