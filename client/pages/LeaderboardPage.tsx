import React, {useState} from 'react';
import {useQuery} from '@connectrpc/connect-query';
import {Link, useParams} from 'react-router-dom';
import {getLeaderboard} from 'proto/leaderboard_service-LeaderboardService_connectquery.js';
import {getAvailableSeasons} from 'proto/season_service-SeasonService_connectquery.js';
import {ErrorState} from 'client/components/ErrorState.js';
import {LoadingState} from 'client/components/LoadingState.js';

// Winitzki approximation for the Error Function; maximum error ~1.2e-4
function erf(x: number): number {
  const sign = x < 0 ? -1 : 1;
  const x2 = x * x;
  const a = (8 * (Math.PI - 3)) / (3 * Math.PI * (4 - Math.PI));
  const inner = Math.exp(-x2 * (4 / Math.PI + a * x2) / (1 + a * x2));
  return sign * Math.sqrt(1 - inner);
}

// Winitzki approximation for the Inverse Error Function
function erfinv(x: number): number {
  const sign = x < 0 ? -1 : 1;
  const a = 0.147;

  const ln1MinusX2 = Math.log(1 - x * x);
  const term1 = 2 / (Math.PI * a) + ln1MinusX2 / 2;
  const term2 = ln1MinusX2 / a;

  return sign * Math.sqrt(Math.sqrt(term1 * term1 - term2) - term1);
}

// Computes the z-score for a given two-tailed confidence interval
function confidenceIntervalZ(confidenceLevel: number): number {
  const alpha = 1 - confidenceLevel;
  const p = alpha / 2.0;
  return -Math.sqrt(2) * erfinv(2 * p - 1);
}

const GLOBAL_MU = 1000.0;
const GLOBAL_SIGMA = 250.0;

function calculatePercentileBounds(mu: number, sigma: number, confidence: number = 0.95) {
  const z_star = confidenceIntervalZ(confidence);

  const lower_skill = mu - z_star * sigma;
  const upper_skill = mu + z_star * sigma;

  const lower = 0.5 * (1 + erf((lower_skill - GLOBAL_MU) / (GLOBAL_SIGMA * Math.sqrt(2))));
  const upper = 0.5 * (1 + erf((upper_skill - GLOBAL_MU) / (GLOBAL_SIGMA * Math.sqrt(2))));
  return {lower, upper};
}

function PercentileEstimate({mu, sigma, confidence}: {
  mu: number;
  sigma: number;
  confidence: number
}) {
  const {lower, upper} = calculatePercentileBounds(mu, sigma, confidence);
  const minWidth = 0.1;
  const leftOffset = Math.min(lower, 1 - minWidth);
  const rightOffset = Math.max(upper, 0 + minWidth);
  const ratingWidth = rightOffset - leftOffset;

  return (
      <div title={`${(lower * 100).toFixed(1)}% - ${(upper * 100).toFixed(1)}%`}
           style={{width: '12em'}}
           className="relative h-4 bg-slate-900/80 rounded-full overflow-hidden border border-slate-700 shadow-inner group">
        <div
            style={{width: `${ratingWidth * 12}em`, marginLeft: `${leftOffset * 12}em`}}
            className="absolute top-0 bottom-0 bg-gradient-to-r from-brand-500 to-purple-500 rounded-full shadow-[0_0_12px_rgba(14,165,233,0.8)] transition-all duration-300"></div>
      </div>
  );
}

export function LeaderboardPage() {
  const {seasonId} = useParams();
  const parsedSeasonId = seasonId ? parseInt(seasonId, 10) : undefined;
  const [showSpecialSkillGroups, setShowSpecialSkillGroups] = useState(false);
  const [confidence, setConfidence] = useState(0.95);

  const leaderboardQuery = useQuery(getLeaderboard, {
    seasonId: parsedSeasonId,
  });

  const seasonsQuery = useQuery(getAvailableSeasons, {});
  const rawPlayers = leaderboardQuery.data?.leaderboard || [];
  const seasons = seasonsQuery.data?.availableSeasons || [];
  const loading = leaderboardQuery.isLoading;
  const error = leaderboardQuery.isError;

  const players = React.useMemo(() => {
    return [...rawPlayers].sort((a, b) => {
      const muA = a.skill?.mu || 0;
      const sigmaA = a.skill?.sigma || 1;
      const lowerA = calculatePercentileBounds(muA, sigmaA, confidence).lower;

      const muB = b.skill?.mu || 0;
      const sigmaB = b.skill?.sigma || 1;
      const lowerB = calculatePercentileBounds(muB, sigmaB, confidence).lower;

      return lowerB - lowerA; // Descending
    });
  }, [rawPlayers, confidence]);

  return (
      <div className="container mx-auto px-4 py-8 max-w-7xl">
        <div className="mb-4 flex flex-col md:flex-row md:items-end justify-between gap-4">
          <div>
            <h1 className="text-4xl font-bold text-white mb-2">Leaderboard</h1>
            <p className="text-slate-400">Top ranked players across TrueScrub matchmaking.</p>
          </div>
        </div>

        <div className="-mt-4 mb-6 group">
          <div
              className="flex flex-wrap items-center gap-2 my-6 bg-dark-card p-2 rounded-xl border border-dark-border shadow-inner relative">
            <span
                className="text-slate-400 font-medium px-3 uppercase tracking-wider text-xs">Season</span>

            <Link to="/leaderboard"
                  className={!parsedSeasonId ? "px-3 py-1.5 rounded-lg text-sm font-medium bg-brand-600 text-white shadow-md shadow-brand-500/20" : "px-3 py-1.5 rounded-lg text-sm font-medium text-slate-300 hover:text-white hover:bg-slate-700 transition-colors"}>All</Link>

            {seasons.map((season) => (
                <Link key={season} to={`/leaderboard/season/${season}`}
                      className={parsedSeasonId === season ? "px-3 py-1.5 rounded-lg text-sm font-medium bg-brand-600 text-white shadow-md shadow-brand-500/20" : "px-3 py-1.5 rounded-lg text-sm font-medium text-slate-300 hover:text-white hover:bg-slate-700 transition-colors"}>{season}</Link>
            ))}

            <div
                className="ml-auto flex items-center gap-3 opacity-0 group-hover:opacity-100 transition-opacity duration-300 pr-2">
              <label htmlFor="confidence-slider"
                     className="text-xs font-medium text-slate-400">Confidence: {(confidence * 100).toFixed(0)}%</label>
              <input
                  id="confidence-slider"
                  type="range"
                  min="0.5"
                  max="0.99"
                  step="0.01"
                  value={confidence}
                  onChange={(e) => setConfidence(parseFloat(e.target.value))}
                  className="w-24 h-1.5 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-brand-500"
              />
            </div>
          </div>
        </div>

        {loading && (
            <LoadingState message="Loading leaderboard..." />
        )}

        {error && !loading && (
            <ErrorState message="Failed to load leaderboard. Please try again later."/>
        )}

        {!loading && !error && (
            <div className="glass-panel rounded-2xl overflow-hidden shadow-2xl">
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse whitespace-nowrap">
                  <thead>
                  <tr className="bg-dark-card border-b border-dark-border text-slate-300 text-sm font-semibold uppercase tracking-wider">
                    <th className="py-4 px-6">Name</th>
                    <th className="py-4 px-6 text-right">MMR</th>
                    <th className="py-4 px-6">Percentile</th>
                    <th className="py-4 px-6 text-center">Impact</th>
                    <th className="py-4 px-6">
                      <div className="flex items-center gap-2">
                        Skill Group
                        {parsedSeasonId === 4 && (
                            <span
                                className="hover:bg-slate-700 p-1 rounded-full cursor-pointer transition-colors"
                                title="Toggle special skill groups"
                                onClick={() => setShowSpecialSkillGroups(!showSpecialSkillGroups)}>🔔</span>
                        )}
                      </div>
                    </th>
                  </tr>
                  </thead>
                  <tbody className="divide-y divide-dark-border/50 bg-dark-bg/30">
                  {players.map((player, index) => {
                    const mu = player.skill?.mu || 0;
                    const sigma = player.skill?.sigma || 1;
                    const {lower, upper} = calculatePercentileBounds(mu, sigma, confidence);
                    const impact = player.impactRating != null ? player.impactRating.toFixed(2) : '-';

                    // Map legacy image names
                    const skillGroupStr = player.skill?.skillGroup || 'Unranked';
                    const imgName = skillGroupStr.toLowerCase().replace(/ /g, '_').replace(/-/g, '_') + '.png';

                    return (
                        <tr key={player.playerId.toString()}
                            className="hover:bg-slate-800/50 transition-colors group">
                          <td className="py-3 px-6">
                            {/* Native a tag for profiles until they are ported */}
                            <a href={`/profiles/${player.playerId.toString()}`}
                               className="font-medium text-white group-hover:text-brand-400 group-hover:underline transition-colors flex items-center gap-3">
                              <div
                                  className="w-8 h-8 rounded-full bg-gradient-to-tr from-brand-600 to-purple-600 flex items-center justify-center text-xs font-bold shadow-inner">
                                {index + 1}
                              </div>
                              {player.steamName.length > 18 ? player.steamName.substring(0, 18) + '…' : player.steamName}
                            </a>
                          </td>
                          <td className="py-3 px-6 text-right text-brand-400 font-mono font-bold"
                              title={`${Math.round(mu)} ± ${Math.round(sigma)}σ`}>
                            {Math.round(player.skill?.mmr || 0)}
                          </td>
                          <td className="py-3 px-6">
                            <div className="flex items-center gap-3">
                          <span
                              className="text-sm font-medium text-slate-300 w-12 text-right">{(lower * 100).toFixed(1)}%</span>
                              <PercentileEstimate mu={mu} sigma={sigma} confidence={confidence}/>
                              <span
                                  className="text-sm font-medium text-slate-300 w-12">{(upper * 100).toFixed(1)}%</span>
                            </div>
                          </td>
                          <td className="py-3 px-6 text-center">
                    <span
                        className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${player.impactRating != null && player.impactRating > 1.0 ? 'bg-green-400/10 text-green-400 border border-green-400/20' : 'bg-slate-700 text-slate-300'}`}>
                      {impact}
                    </span>
                          </td>
                          <td className="py-3 px-6">
                            <div
                                className={`skill flex items-center gap-2 ${showSpecialSkillGroups ? 'hidden' : 'inline-block'}`}>
                              <img src={`/htdocs/img/ranks/${imgName}`} alt={skillGroupStr}
                                   className="w-10 h-10 object-contain drop-shadow-md"/>
                              <span
                                  className="inline-block px-2 py-1 bg-dark-card border border-dark-border rounded-lg text-sm text-slate-300 font-medium tracking-wide">
                        {skillGroupStr}
                      </span>
                            </div>
                          </td>
                        </tr>
                    );
                  })}
                  </tbody>
                </table>
              </div>
            </div>
        )}

        <div className="mt-8 text-center pt-8 border-t border-dark-border/50">
          <Link to="/skill_groups"
                className="inline-flex items-center text-slate-400 hover:text-white transition-colors group">
            <svg className="w-4 h-4 mr-2 group-hover:-translate-x-1 transition-transform"
                 fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2"
                    d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
            </svg>
            Learn about Skill Groups
          </Link>
        </div>
      </div>
  );
}
