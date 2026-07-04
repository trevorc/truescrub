import React, {useState} from 'react';
import {useQuery} from '@connectrpc/connect-query';
import {Link, useParams} from 'react-router-dom';
import {getLeaderboard} from 'proto/leaderboard_service-LeaderboardService_connectquery.js';
import {getAvailableSeasons} from 'proto/season_service-SeasonService_connectquery.js';
import {fromJson} from '@bufbuild/protobuf';
import {SkillGroupConfigurationSchema} from 'truescrub/proto/profile_pb.js';
import skillGroupsJson from 'truescrub/proto/skill_groups.json';
import {skillGroupName} from 'client/pages/skill_group.js';
import {ErrorState} from 'client/components/ErrorState.js';
import {LoadingState} from 'client/components/LoadingState.js';

import rank_cardboard_i from "client/pages/ranks/cardboard_i.png";
import rank_cardboard_ii from "client/pages/ranks/cardboard_ii.png";
import rank_cardboard_iii from "client/pages/ranks/cardboard_iii.png";
import rank_cardboard_iv from "client/pages/ranks/cardboard_iv.png";
import rank_garb_salad from "client/pages/ranks/garb_salad.png";
import rank_legendary_wood from "client/pages/ranks/legendary_wood.png";
import rank_low_key_dirty from "client/pages/ranks/low_key_dirty.png";
import rank_master_garbian from "client/pages/ranks/master_garbian.png";
import rank_master_garbian_elite from "client/pages/ranks/master_garbian_elite.png";
import rank_plastic_elite from "client/pages/ranks/plastic_elite.png";
import rank_plastic_i from "client/pages/ranks/plastic_i.png";
import rank_plastic_ii from "client/pages/ranks/plastic_ii.png";
import rank_plastic_iii from "client/pages/ranks/plastic_iii.png";

const RANKS: Record<string, string> = {
  "Cardboard I": rank_cardboard_i,
  "Cardboard II": rank_cardboard_ii,
  "Cardboard III": rank_cardboard_iii,
  "Cardboard IV": rank_cardboard_iv,
  "Garb Salad": rank_garb_salad,
  "Legendary Wood": rank_legendary_wood,
  "Low-Key Dirty": rank_low_key_dirty,
  "Master Garbian": rank_master_garbian,
  "Master Garbian Elite": rank_master_garbian_elite,
  "Plastic Elite": rank_plastic_elite,
  "Plastic I": rank_plastic_i,
  "Plastic II": rank_plastic_ii,
  "Plastic III": rank_plastic_iii,
};

// Winitzki approximation for the Error Function; maximum error ~1.2e-4
export function erf(x: number): number {
  const sign = x < 0 ? -1 : 1;
  const x2 = x * x;
  const a = (8 * (Math.PI - 3)) / (3 * Math.PI * (4 - Math.PI));
  const inner = Math.exp(-x2 * (4 / Math.PI + a * x2) / (1 + a * x2));
  return sign * Math.sqrt(1 - inner);
}

const GLOBAL_MU = 1000.0;
const GLOBAL_SIGMA = 250.0;

export function calculatePercentileBounds(mu: number, sigma: number, zScore: number = 2.0) {
  const lower_skill = mu - zScore * sigma;
  const upper_skill = mu + zScore * sigma;

  const lower = 0.5 * (1 + erf((lower_skill - GLOBAL_MU) / (GLOBAL_SIGMA * Math.sqrt(2))));
  const upper = 0.5 * (1 + erf((upper_skill - GLOBAL_MU) / (GLOBAL_SIGMA * Math.sqrt(2))));
  return {lower, upper};
}

function PercentileEstimate({mu, sigma, zScore}: {
  mu: number;
  sigma: number;
  zScore: number
}) {
  const {lower, upper} = calculatePercentileBounds(mu, sigma, zScore);
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
  const [zScore, setZScore] = useState(2.0);
  const skillGroupsConfig = React.useMemo(() => fromJson(SkillGroupConfigurationSchema, skillGroupsJson), []);

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
      const lowerA = calculatePercentileBounds(muA, sigmaA, zScore).lower;

      const muB = b.skill?.mu || 0;
      const sigmaB = b.skill?.sigma || 1;
      const lowerB = calculatePercentileBounds(muB, sigmaB, zScore).lower;

      return lowerB - lowerA; // Descending
    });
  }, [rawPlayers, zScore]);

  return (
      <div className="flex flex-col">
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
                     className="text-xs font-medium text-slate-400">
                Penalty: {zScore.toFixed(1)}σ (CL: {(erf(zScore / Math.SQRT2) * 100).toFixed(1)}%)
              </label>
              <input
                  id="confidence-slider"
                  type="range"
                  min="0.0"
                  max="3.0"
                  step="0.1"
                  value={zScore}
                  onChange={(e) => setZScore(parseFloat(e.target.value))}
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
                    const dynamicMmr = mu - (zScore * sigma);
                    const {lower, upper} = calculatePercentileBounds(mu, sigma, zScore);
                    const impact = player.impactRating != null ? player.impactRating.toFixed(2) : '-';

                    // Map legacy image names
                    const displayName = skillGroupName(dynamicMmr, skillGroupsConfig, showSpecialSkillGroups);
                    const baseName = skillGroupName(dynamicMmr, skillGroupsConfig, false);
                    const isSpecial = showSpecialSkillGroups && displayName !== baseName;

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
                            {Math.round(dynamicMmr)}
                          </td>
                          <td className="py-3 px-6">
                            <div className="flex items-center gap-3">
                          <span
                              className="text-sm font-medium text-slate-300 w-12 text-right">{(lower * 100).toFixed(1)}%</span>
                              <PercentileEstimate mu={mu} sigma={sigma} zScore={zScore}/>
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
                                className={`skill flex items-center gap-2 inline-block`}>
                              <img src={RANKS[baseName] || ""} alt={displayName}
                                   className={`w-12 h-12 object-contain filter drop-shadow-[0_2px_5px_rgba(0,0,0,0.5)] transform group-hover:scale-110 transition-transform duration-300 ${isSpecial ? 'hue-rotate-180 sepia brightness-110' : ''}`}/>
                              <span
                                  className={`inline-block px-2 py-1 bg-dark-card border border-dark-border rounded-lg text-sm font-medium tracking-wide ${isSpecial ? 'text-orange-400' : 'text-slate-300'}`}>
                        {displayName}
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
