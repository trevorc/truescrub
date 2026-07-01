import {useEffect, useMemo, useState} from "react";
import {useLocation, useNavigate} from "react-router-dom";
import {useQuery} from "@connectrpc/connect-query";
import {
  getDailyHighlights,
  listMatchDays
} from "proto/highlights_service-HighlightsService_connectquery.js";
import {Accolade} from "proto/highlights_service_pb.js";
import {AccoladeCard} from "client/components/AccoladeCard.js";

import chicken1 from "./chickens/chicken_ui.png";
import chicken2 from "./chickens/chicken_ui2.png";
import chicken3 from "./chickens/chicken_ui3.png";
import chicken4 from "./chickens/chicken_ui4.png";
import chicken5 from "./chickens/chicken_ui5.png";

type AccoladeWithPlayer = { accolade: Accolade; playerName: string };

const CHICKENS = [chicken1, chicken2, chicken3, chicken4, chicken5];

function getRandomChicken(): string {
  return CHICKENS[Math.floor(Math.random() * CHICKENS.length)];
}

export function AccoladesPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const [randomChicken] = useState(getRandomChicken);

  const matchDaysQuery = useQuery(listMatchDays, {timezone: "-05:00"}, {
    select: (data) => data.matchDays.map(d => {
      const m = String(d.month).padStart(2, '0');
      const day = String(d.day).padStart(2, '0');
      return `${d.year}-${m}-${day}`;
    })
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

  const dateInput = useMemo(() => {
    if (!currentDayString) return undefined;
    const [year, month, day] = currentDayString.split('-').map(Number);
    return {year, month, day};
  }, [currentDayString]);

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
            <div className="text-center py-12 text-slate-400">
              <div className="flex flex-col items-center">
                <img src={randomChicken}
                     className="w-16 h-16 object-contain mb-4 animate-chickenBounce"
                     alt="Loading..."/>
                <p>Chickens are crunching the stats...</p>
              </div>
            </div>
        )}

        {error && !loading && (
            <div className="text-center py-12 text-red-400">
              <p>Failed to load accolades. Please try again later.</p>
            </div>
        )}

        {!loading && !error && accolades.length === 0 && !hasNoDays && (
            <div className="text-center py-16 text-slate-400">
              <img src={randomChicken} className="w-32 h-32 object-contain mx-auto mb-4"
                   alt="No data"/>
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
