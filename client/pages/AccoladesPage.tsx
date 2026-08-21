import {Suspense, useEffect} from "react";
import type {LoaderFunctionArgs} from "react-router-dom";
import {useLocation, useNavigate} from "react-router-dom";
import type {QueryClient} from "@tanstack/react-query";
import {useSuspenseQuery, useQuery} from "@tanstack/react-query";
import type {Transport} from "@connectrpc/connect";
import {createQueryOptions, useTransport} from "@connectrpc/connect-query";

import {
  getDailyHighlights,
  listMatchDays
} from "proto/highlights_service-HighlightsService_connectquery.js";
import {
  Accolade,
  GetDailyHighlightsResponse,
  ListMatchDaysResponse
} from "proto/highlights_service_pb.js";
import {create} from "@bufbuild/protobuf";
import {Date as RpcDate, DateSchema} from "proto/common_pb.js";
import {AccoladeCard} from "client/components/AccoladeCard.js";
import {ErrorState} from "client/components/ErrorState.js";
import {LoadingState} from "client/components/LoadingState.js";

type AccoladeWithPlayer = { accolade: Accolade; playerName: string };

export function formatMatchDayString(date: RpcDate): string {
  const m = String(date.month).padStart(2, '0');
  const d = String(date.day).padStart(2, '0');
  return `${date.year}-${m}-${d}`;
}

export function parseMatchDayString(dateStr: string | null): RpcDate | undefined {
  if (!dateStr) return undefined;
  const parts = dateStr.split('-');
  if (parts.length !== 3) return undefined;
  const [year, month, day] = parts.map(Number);
  if (isNaN(year) || isNaN(month) || isNaN(day)) return undefined;
  return create(DateSchema, {year, month, day});
}

export const matchDaysQueryOptions = (transport: Transport) => ({
  ...createQueryOptions(listMatchDays, {timezone: "-05:00"}, {transport}),
  select: (data: ListMatchDaysResponse) =>
      data.matchDays.map(formatMatchDayString)
});

export const highlightsQueryOptions = (dateInput: RpcDate, transport: Transport) => ({
  ...createQueryOptions(
      getDailyHighlights,
      {
        date: dateInput,
        timezone: "-05:00",
        readMask: {
          paths: ["players.accolades", "players.player.steam_name"]
        },
      },
      {transport}
  ),
  select: (data: GetDailyHighlightsResponse) => data.players.flatMap(p =>
      p.accolades.map(accolade => ({
        accolade, playerName: p.player?.steamName ?? "Unknown"
      }))
  )
});

export const accoladesLoader = (queryClient: QueryClient, transport: Transport) => async ({request}: LoaderFunctionArgs) => {
  const url = new URL(request.url);
  const hash = url.hash.substring(1);

  const rawMatchDays = await queryClient.ensureQueryData(matchDaysQueryOptions(transport));
  const matchDays = rawMatchDays.matchDays.map(formatMatchDayString);
  const currentIndex = matchDays.length === 0 ? 0 : Math.max(0, matchDays.indexOf(hash));
  const currentDayString = matchDays.length === 0 ? null : matchDays[currentIndex];
  const dateInput = parseMatchDayString(currentDayString);

  if (dateInput) {
    queryClient.prefetchQuery(highlightsQueryOptions(dateInput, transport));
  }
  return null;
};

export function AccoladesPage() {
  const transport = useTransport();
  const location = useLocation();
  const navigate = useNavigate();

  const {data: matchDays} = useSuspenseQuery(matchDaysQueryOptions(transport));
  const hasNoDays = matchDays.length === 0;

  const hash = location.hash.substring(1);
  const currentIndex = hasNoDays ? 0 : Math.max(0, matchDays.indexOf(hash));
  const currentDayString = hasNoDays ? null : matchDays[currentIndex];

  useEffect(() => {
    if (currentDayString && hash !== currentDayString) {
      navigate(`#${currentDayString}`, {replace: true});
    }
  }, [currentDayString, hash, navigate]);

  const displayDate = currentDayString
      ? new Date(currentDayString + 'T00:00:00-05:00').toLocaleDateString('en-US', {
        weekday: 'long',
        year: 'numeric',
        month: 'long',
        day: 'numeric'
      })
      : "No Match Days Found";

  const dateInput = parseMatchDayString(currentDayString);
  const highlightsQuery = useQuery({
    ...highlightsQueryOptions(dateInput!, transport),
    enabled: !!dateInput
  });

  const loading = highlightsQuery.isLoading || highlightsQuery.isFetching;
  const error = highlightsQuery.isError;
  const accolades = highlightsQuery.data ?? [];

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

        {hasNoDays ? (
            <div className="text-center py-16 text-slate-400">
              <p className="text-lg font-medium">No match data.</p>
            </div>
        ) : !dateInput ? (
            <ErrorState message="Invalid match day string in URL."/>
        ) : loading ? (
            <LoadingState message="Chickens are crunching the stats..."/>
        ) : error ? (
            <ErrorState message="Failed to load daily highlights."/>
        ) : accolades.length === 0 ? (
            <div className="text-center py-16 text-slate-400">
              <p className="text-lg font-medium">No accolades available for this day.</p>
              <p className="text-sm text-slate-500 mt-1">Even the chickens left.</p>
            </div>
        ) : (
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
