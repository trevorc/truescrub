import {useState} from "react";
import {Link, createRoute} from "@tanstack/react-router";
import {rootRoute} from "client/RootRoute.js";
import type {QueryClient} from "@tanstack/react-query";
import {useQuery, useSuspenseQuery} from "@tanstack/react-query";
import {createQueryOptions, useTransport} from "@connectrpc/connect-query";
import {availableSeasonsQueryOptions, getLatestSeasonId} from "client/api/seasons.js";
import type {Transport} from "@connectrpc/connect";

import {computeMatchmaking} from "proto/matchmaking_service-MatchmakingService_connectquery.js";
import type {ComputeMatchmakingRequest} from "proto/matchmaking_service_pb.js";
import {Match, PlayerSelectionSchema, RoundSelectionSchema} from "proto/matchmaking_service_pb.js";
import {create} from "@bufbuild/protobuf";
import {Player} from "proto/common_pb.js";
import chicken_war_png from "client/pages/img/chicken_war.png";
import {ErrorState} from "client/components/ErrorState.js";
import {LoadingState} from "client/components/LoadingState.js";

const MatchSkeleton = ({playersPerTeam = 5}: { playersPerTeam?: number }) => (
    <div className="glass-panel rounded-2xl overflow-hidden shadow-lg">
      <div
          className="bg-dark-bg/80 border-b border-dark-border px-6 py-3 flex justify-between items-center">
        <div className="flex items-center gap-2 h-5">
          <div className="h-4 w-20 rounded bg-slate-700 animate-pulse"/>
        </div>
        <div
            className="flex items-center gap-2 bg-slate-800/80 px-3 py-1 rounded-full border border-slate-700">
          <div className="h-4 w-24 rounded bg-slate-700 animate-pulse"/>
        </div>
      </div>
      <div className="grid md:grid-cols-2 divide-y md:divide-y-0 md:divide-x divide-dark-border/50">
        <div className="p-6">
          <div className="flex justify-between items-baseline mb-4 h-7">
            <div className="flex items-center gap-2">
              <span className="w-3 h-3 rounded-sm bg-slate-700 animate-pulse"></span>
              <div className="h-5 w-24 rounded bg-slate-700 animate-pulse"/>
            </div>
            <div className="h-5 w-16 rounded bg-slate-700 animate-pulse"/>
          </div>
          <ul className="space-y-2">
            {Array.from({length: Math.max(1, playersPerTeam)}).map((_, i) => (
                <li key={i}
                    className="flex items-center py-1 border-b border-dark-border/30 last:border-0 h-8">
                  <div
                      className="w-6 h-6 rounded-full bg-slate-800 flex-shrink-0 animate-pulse border border-slate-700 mr-3"/>
                  <div className="h-4 w-32 rounded bg-slate-700 animate-pulse"/>
                </li>
            ))}
          </ul>
        </div>
        <div className="p-6">
          <div className="flex justify-between items-baseline mb-4 h-7">
            <div className="flex items-center gap-2">
              <span className="w-3 h-3 rounded-sm bg-slate-700 animate-pulse"></span>
              <div className="h-5 w-24 rounded bg-slate-700 animate-pulse"/>
            </div>
            <div className="h-5 w-16 rounded bg-slate-700 animate-pulse"/>
          </div>
          <ul className="space-y-2">
            {Array.from({length: Math.max(1, playersPerTeam)}).map((_, i) => (
                <li key={i}
                    className="flex items-center py-1 border-b border-dark-border/30 last:border-0 h-8">
                  <div
                      className="w-6 h-6 rounded-full bg-slate-800 flex-shrink-0 animate-pulse border border-slate-700 mr-3"/>
                  <div className="h-4 w-32 rounded bg-slate-700 animate-pulse"/>
                </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
);

const SeasonPicker = ({seasons, displayedSeasonId, skeleton}: {
  seasons: number[],
  displayedSeasonId: number | undefined,
  skeleton: boolean,
}) => (
    <div className="-mt-4 mb-8 min-h-[72px]">
      {seasons.length > 0 ? (
          <div
              className="flex flex-wrap items-center gap-2 my-6 bg-dark-card p-2 rounded-xl border border-dark-border shadow-inner">
            <span
                className="text-slate-400 font-medium px-3 uppercase tracking-wider text-xs">Season</span>

            {displayedSeasonId !== undefined ? (
                <Link to="/matchmaking"
                      className="px-3 py-1.5 rounded-lg text-sm font-medium text-slate-300 hover:text-white hover:bg-slate-700 transition-colors">All</Link>
            ) : (
                <span
                    className="px-3 py-1.5 rounded-lg text-sm font-medium bg-brand-600 text-white shadow-md shadow-brand-500/20">All</span>
            )}

            {seasons.map((season) => (
                displayedSeasonId === season ? (
                    <span key={season}
                          className="px-3 py-1.5 rounded-lg text-sm font-medium bg-brand-600 text-white shadow-md shadow-brand-500/20">{season}</span>
                ) : (
                    <Link key={season} to={`/matchmaking/season/${season}`}
                          className="px-3 py-1.5 rounded-lg text-sm font-medium text-slate-300 hover:text-white hover:bg-slate-700 transition-colors">{season}</Link>
                )
            ))}
          </div>
      ) : skeleton ? (
          <div
              className="flex flex-wrap items-center gap-2 my-6 bg-dark-card p-2 rounded-xl border border-dark-border shadow-inner">
            <span
                className="text-slate-400 font-medium px-3 uppercase tracking-wider text-xs">Season</span>
            <div className="w-12 h-8 bg-slate-700/50 rounded-lg animate-pulse"/>
            <div className="w-8 h-8 bg-slate-700/50 rounded-lg animate-pulse"/>
            <div className="w-8 h-8 bg-slate-700/50 rounded-lg animate-pulse"/>
            <div className="w-8 h-8 bg-slate-700/50 rounded-lg animate-pulse"/>
            <div className="w-8 h-8 bg-slate-700/50 rounded-lg animate-pulse"/>
            <div className="w-8 h-8 bg-slate-700/50 rounded-lg animate-pulse"/>
          </div>
      ) : null}
    </div>
);

const PlayerSelector = ({
  availablePlayers,
  selectedPlayerIds,
  togglePlayer,
  toggleAll,
  linkToPath,
  playerParams,
  skeleton
}: {
  availablePlayers: Player[],
  selectedPlayerIds: Set<bigint>,
  togglePlayer: (playerId: bigint) => void,
  toggleAll: () => void,
  linkToPath: string,
  playerParams: string[],
  skeleton: boolean,
}) => (
    <div className="w-full lg:w-1/3">
      <div className="glass-panel rounded-2xl p-6 sticky top-6">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-xl font-bold text-white">Who is playing?</h2>
          <button
              type="button"
              onClick={toggleAll}
              className="text-xs text-brand-400 hover:text-brand-300 font-medium bg-brand-500/10 hover:bg-brand-500/20 px-3 py-1.5 rounded-full transition-colors">
            Toggle All
          </button>
        </div>

        <div className="overflow-y-auto max-h-[50vh] pr-2 mb-6 space-y-2 custom-scrollbar">
          {availablePlayers.length > 0 ? availablePlayers.map(player => (
              <label
                  key={player.playerId.toString()}
                  className="flex items-center p-3 rounded-xl border border-dark-border bg-dark-bg/50 hover:bg-slate-800/80 cursor-pointer transition-colors group">
                <div className="relative flex items-center justify-center">
                  <input
                      type="checkbox"
                      className="peer sr-only"
                      checked={selectedPlayerIds.has(player.playerId)}
                      onChange={() => togglePlayer(player.playerId)}
                  />
                  <div
                      className="w-5 h-5 rounded border-2 border-slate-600 peer-checked:bg-brand-500 peer-checked:border-brand-500 transition-colors"></div>
                  <svg
                      className="absolute w-3 h-3 text-white opacity-0 peer-checked:opacity-100 transition-opacity"
                      fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="3"
                          d="M5 13l4 4L19 7"/>
                  </svg>
                </div>
                <span
                    className="ml-3 text-slate-300 group-hover:text-white transition-colors font-medium select-none">{player.steamName}</span>
              </label>
          )) : skeleton ? (
              <div className="space-y-2">
                {Array.from({length: 10}).map((_, i) => (
                    <div key={i}
                         className="flex items-center p-3 rounded-xl border border-dark-border bg-dark-bg/50">
                      <div className="flex items-center justify-center">
                        <div
                            className="w-5 h-5 rounded border-2 border-slate-600 bg-slate-700/50 animate-pulse"></div>
                      </div>
                      <div className="ml-3 h-6 flex items-center">
                        <div className="h-4 w-32 bg-slate-700/50 rounded animate-pulse"></div>
                      </div>
                    </div>
                ))}
              </div>
          ) : null}
        </div>
        <Link
            to={linkToPath}
            search={{player: playerParams}}
            className="btn-primary w-full mt-auto py-3 text-lg flex items-center justify-center gap-2">
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2"
                  d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 002-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"/>
          </svg>
          Generate Matches
        </Link>
      </div>
    </div>
);

const MatchCard = ({match, index}: { match: Match, index: number }) => (
    <div className="glass-panel rounded-2xl overflow-hidden shadow-lg">
      <div
          className="bg-dark-bg/80 border-b border-dark-border px-6 py-3 flex justify-between items-center">
        <div className="flex items-center gap-2">
          <span
              className="text-sm font-medium text-slate-400 uppercase tracking-wide">Match {index + 1}</span>
        </div>
        <div
            className="flex items-center gap-2 bg-slate-800/80 px-3 py-1 rounded-full border border-slate-700"
            title="Chance of draw">
          <span
              className={`w-2 h-2 rounded-full ${match.quality > 0.8 ? 'bg-green-500' : match.quality > 0.5 ? 'bg-yellow-500' : 'bg-red-500'}`}></span>
          <span className="text-sm font-medium text-slate-300">Quality: <span
              className="text-white">{Math.floor(100 * match.quality)}%</span></span>
        </div>
      </div>

      <div
          className="grid md:grid-cols-2 divide-y md:divide-y-0 md:divide-x divide-dark-border/50">
        <div className="p-6 bg-gradient-to-br from-brand-900/10 to-transparent">
          <div className="flex justify-between items-baseline mb-4">
            <h4 className="text-lg font-bold text-white flex items-center gap-2">
              <span className="w-3 h-3 rounded-sm bg-brand-500"></span> Team 1
            </h4>
            <div
                className="text-brand-400 font-mono font-bold text-lg">{Math.round(100 * match.team1WinProbability)}% <span
                className="text-xs text-slate-500 font-sans font-normal">Win</span>
            </div>
          </div>
          <ul className="space-y-2">
            {match.team1.map((player, pIdx) => (
                <li key={Number(player.playerId)}
                    className="flex items-center text-slate-300 py-1 border-b border-dark-border/30 last:border-0">
                  <div
                      className="w-6 h-6 rounded-full bg-slate-800 flex items-center justify-center text-xs text-slate-400 mr-3 border border-slate-700">{pIdx + 1}</div>
                  {player.steamName}
                </li>
            ))}
          </ul>
        </div>

        <div className="p-6 bg-gradient-to-bl from-purple-900/10 to-transparent">
          <div className="flex justify-between items-baseline mb-4">
            <h4 className="text-lg font-bold text-white flex items-center gap-2">
              <span className="w-3 h-3 rounded-sm bg-purple-500"></span> Team 2
            </h4>
            <div
                className="text-purple-400 font-mono font-bold text-lg">{100 - Math.round(100 * match.team1WinProbability)}% <span
                className="text-xs text-slate-500 font-sans font-normal">Win</span>
            </div>
          </div>
          <ul className="space-y-2">
            {match.team2.map((player, pIdx) => (
                <li key={Number(player.playerId)}
                    className="flex items-center text-slate-300 py-1 border-b border-dark-border/30 last:border-0">
                  <div
                      className="w-6 h-6 rounded-full bg-slate-800 flex items-center justify-center text-xs text-slate-400 mr-3 border border-slate-700">{pIdx + 1}</div>
                  {player.steamName}
                </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
);

export const computeMatchmakingQueryOptions = (seasonId: number | undefined, selection: ComputeMatchmakingRequest["selection"], transport: Transport) => createQueryOptions(computeMatchmaking, {
  seasonId,
  selection
}, {transport});

function parsePlayerSearch(search: Record<string, unknown>): { player: string[] } {
  const p = search.player;
  if (p == null) {
    return {player: []};
  }
  if (Array.isArray(p)) {
    return {player: p.map(String)};
  }
  return {player: [String(p)]};
}

export const matchmakingRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/matchmaking',
  validateSearch: parsePlayerSearch,
  component: function MatchmakingRouteComponent() {
    const {player} = matchmakingRoute.useSearch();
    return <MatchmakingPage playerSearch={player}/>;
  },
  loaderDeps: ({ search }) => search,
  loader: async ({context: {queryClient, transport}, deps: search}) => {
    const seasons = await queryClient.ensureQueryData(availableSeasonsQueryOptions(transport));
    const urlPlayerIds = new Set(search.player.filter(Boolean).map(BigInt));
    const selection: ComputeMatchmakingRequest["selection"] = {
      case: 'playerSelection',
      value: create(PlayerSelectionSchema, {playerIds: Array.from(urlPlayerIds)})
    };
    queryClient.prefetchQuery(computeMatchmakingQueryOptions(undefined, selection, transport));
  }
});

export const matchmakingLatestRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/matchmaking/latest',
  validateSearch: parsePlayerSearch,
  component: function MatchmakingLatestRouteComponent() {
    const {player} = matchmakingLatestRoute.useSearch();
    return <MatchmakingPage isLatest={true} playerSearch={player}/>;
  },
  loaderDeps: ({ search }) => search,
  loader: async ({context: {queryClient, transport}, deps: search}) => {
    await queryClient.ensureQueryData(availableSeasonsQueryOptions(transport));
    const selection: ComputeMatchmakingRequest["selection"] = {
      case: 'roundSelection',
      value: create(RoundSelectionSchema, {})
    };
    queryClient.prefetchQuery(computeMatchmakingQueryOptions(undefined, selection, transport));
  }
});

export const matchmakingSeasonRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/matchmaking/season/$seasonId',
  validateSearch: parsePlayerSearch,
  component: function MatchmakingSeasonRouteComponent() {
    const {seasonId} = matchmakingSeasonRoute.useParams();
    const {player} = matchmakingSeasonRoute.useSearch();
    return <MatchmakingPage routeSeasonId={seasonId} playerSearch={player}/>;
  },
  loaderDeps: ({ search }) => search,
  loader: async ({context: {queryClient, transport}, deps: search, params}) => {
    const seasons = await queryClient.ensureQueryData(availableSeasonsQueryOptions(transport));
    const resolvedSeasonId = params.seasonId && !isNaN(parseInt(params.seasonId, 10))
        ? parseInt(params.seasonId, 10)
        : undefined;
    const urlPlayerIds = new Set(search.player.filter(Boolean).map(BigInt));
    const selection: ComputeMatchmakingRequest["selection"] = {
      case: 'playerSelection',
      value: create(PlayerSelectionSchema, {playerIds: Array.from(urlPlayerIds)})
    };
    queryClient.prefetchQuery(computeMatchmakingQueryOptions(resolvedSeasonId, selection, transport));
  }
});

export function MatchmakingPage({
  isLatest = false,
  routeSeasonId,
  playerSearch = []
}: {
  isLatest?: boolean;
  routeSeasonId?: string;
  playerSearch?: string[];
}) {
  const transport = useTransport();
  const seasonId = routeSeasonId ? (isNaN(parseInt(routeSeasonId, 10))
      ? undefined : parseInt(routeSeasonId, 10)) : undefined;

  const urlPlayerIdsKey = playerSearch.sort().join(",");
  const urlPlayerIds = new Set(playerSearch.filter(Boolean).map(BigInt));

  const [selectedPlayerIds, setSelectedPlayerIds] = useState<Set<bigint>>(urlPlayerIds);
  const [prevUrlKey, setPrevUrlKey] = useState(urlPlayerIdsKey);
  if (prevUrlKey !== urlPlayerIdsKey) {
    setPrevUrlKey(urlPlayerIdsKey);
    setSelectedPlayerIds(urlPlayerIds);
  }

  const {data: {availableSeasons}} = useSuspenseQuery(availableSeasonsQueryOptions(transport));

  const selection: ComputeMatchmakingRequest["selection"] = isLatest
      ? {case: 'roundSelection', value: create(RoundSelectionSchema, {})}
      : {
        case: 'playerSelection',
        value: create(PlayerSelectionSchema, {playerIds: Array.from(urlPlayerIds)})
      };

  const matchmakingQuery = useQuery(computeMatchmakingQueryOptions(seasonId, selection, transport));
  const availablePlayers = matchmakingQuery.data?.availablePlayers ?? [];
  const proposedMatches = matchmakingQuery.data?.proposedMatches ?? [];

  const [latestSynced, setLatestSynced] = useState(false);
  if (isLatest && !latestSynced && matchmakingQuery.data && proposedMatches.length > 0 && urlPlayerIds.size === 0) {
    const match = proposedMatches[0];
    setSelectedPlayerIds(new Set([
      ...match.team1.map(p => p.playerId),
      ...match.team2.map(p => p.playerId),
    ]));
    setLatestSynced(true);
  }

  const loading = matchmakingQuery.isLoading;
  const error = matchmakingQuery.isError;
  const skeleton = matchmakingQuery.isFetching && !matchmakingQuery.data;

  const togglePlayer = (playerId: bigint) => {
    setSelectedPlayerIds(prev => {
      const next = new Set(prev);
      next.has(playerId) ? next.delete(playerId) : next.add(playerId);
      return next;
    });
  };

  const toggleAll = () => {
    setSelectedPlayerIds(prev =>
        prev.size === availablePlayers.length
            ? new Set()
            : new Set(availablePlayers.map(p => p.playerId))
    );
  };

  const displayedSeasonId = isLatest
      ? getLatestSeasonId(availableSeasons)
      : seasonId;

  const linkToPath = displayedSeasonId !== undefined
      ? `/matchmaking/season/${displayedSeasonId}`
      : '/matchmaking';
  const playerParams = Array.from(selectedPlayerIds).map(id => id.toString());
  return (
      <div className="flex flex-col">
        {/* Header */}
        <div className="mb-4">
          <h1 className="text-4xl font-bold text-white mb-2">Matchmaking</h1>
          <p className="text-slate-400">
            {isLatest
                ? "Proposes evenly matched teams given the players in the last round."
                : "Proposes evenly matched teams for a given set of players."}
          </p>
        </div>

        <SeasonPicker seasons={availableSeasons} displayedSeasonId={displayedSeasonId}
                      skeleton={skeleton}/>

        <div className="flex flex-col lg:flex-row gap-8">
          <PlayerSelector availablePlayers={availablePlayers} selectedPlayerIds={selectedPlayerIds}
                          togglePlayer={togglePlayer} toggleAll={toggleAll}
                          linkToPath={linkToPath} playerParams={playerParams}
                          skeleton={skeleton}/>

          {/* Results */}
          <div className="w-full lg:w-2/3 space-y-6">
            {skeleton ? (
                <div className="space-y-6">
                  <h2 className="text-2xl font-bold text-white mb-4 flex items-center gap-3">
                    <svg className="w-6 h-6 text-slate-700 animate-pulse" fill="none"
                         viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2"
                            d="M9 12l2 2 4-4M7.835 4.697a3.42 3.42 0 001.946-.806 3.42 3.42 0 014.438 0 3.42 3.42 0 001.946.806 3.42 3.42 0 013.138 3.138 3.42 3.42 0 00.806 1.946 3.42 3.42 0 010 4.438 3.42 3.42 0 00-.806 1.946 3.42 3.42 0 01-3.138 3.138 3.42 3.42 0 00-1.946.806 3.42 3.42 0 01-4.438 0 3.42 3.42 0 00-1.946-.806 3.42 3.42 0 01-3.138-3.138 3.42 3.42 0 00-.806-1.946 3.42 3.42 0 010-4.438 3.42 3.42 0 00.806-1.946 3.42 3.42 0 013.138-3.138z"/>
                    </svg>
                    <div className="h-6 w-48 rounded bg-slate-700 animate-pulse"/>
                  </h2>
                  {Array.from({length: Math.max(proposedMatches.length, 2)}).map((_, i) => (
                      <MatchSkeleton key={i}
                                     playersPerTeam={Math.ceil((selectedPlayerIds.size > 0 ? selectedPlayerIds.size : 10) / 2)}/>
                  ))}
                </div>
            ) : loading ? (
                <LoadingState message="Computing matches..."/>
            ) : error ? (
                <ErrorState message="Failed to compute matches."/>
            ) : proposedMatches.length > 0 ? (
                <>
                  <h2 className="text-2xl font-bold text-white mb-4 flex items-center gap-3">
                    <svg className="w-6 h-6 text-brand-400" fill="none" viewBox="0 0 24 24"
                         stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2"
                            d="M9 12l2 2 4-4M7.835 4.697a3.42 3.42 0 001.946-.806 3.42 3.42 0 014.438 0 3.42 3.42 0 001.946.806 3.42 3.42 0 013.138 3.138 3.42 3.42 0 00.806 1.946 3.42 3.42 0 010 4.438 3.42 3.42 0 00-.806 1.946 3.42 3.42 0 01-3.138 3.138 3.42 3.42 0 00-1.946.806 3.42 3.42 0 01-4.438 0 3.42 3.42 0 00-1.946-.806 3.42 3.42 0 01-3.138-3.138 3.42 3.42 0 00-.806-1.946 3.42 3.42 0 010-4.438 3.42 3.42 0 00.806-1.946 3.42 3.42 0 013.138-3.138z"/>
                    </svg>
                    Proposed Matches
                  </h2>

                  {proposedMatches.map((match, idx) => (
                      <MatchCard key={idx} match={match} index={idx}/>
                  ))}
                </>
            ) : (
                <div
                    className="h-64 border-2 border-dashed border-dark-border rounded-2xl flex flex-col items-center justify-center text-slate-500">
                  <img src={chicken_war_png} alt="Waiting"
                       className="w-32 h-32 object-contain mb-4"/>
                  <p className="text-lg font-medium">Select players and generate matches</p>
                  <p className="text-sm text-slate-600 mt-1">The chicken is ready for battle.</p>
                </div>
            )}
          </div>
        </div>
      </div>
  );
}
