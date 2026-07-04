import React, {useMemo, useState} from 'react';
import {NavLink, Route, Routes, useParams} from 'react-router-dom';
import {useQuery} from '@connectrpc/connect-query';
import {getProfile, getSkillHistory} from 'proto/profile_service-ProfileService_connectquery.js';
import {getAvailableSeasons} from 'proto/season_service-SeasonService_connectquery.js';
import {ErrorState} from 'client/components/ErrorState.js';
import {LoadingState} from 'client/components/LoadingState.js';
import {
  Area,
  ComposedChart,
  Line,
  ResponsiveContainer,
  Scatter,
  Tooltip,
  XAxis,
  YAxis
} from 'recharts';

import {MatchesTab} from 'client/pages/MatchesTab.js';
import {TeamRecordsTab} from 'client/pages/TeamRecordsTab.js';
import {fromJson} from '@bufbuild/protobuf';
import {SkillGroupConfigurationSchema} from 'truescrub/proto/profile_pb.js';
import skillGroupsJson from 'truescrub/proto/skill_groups.json';
import {skillGroupName} from 'client/pages/skill_group.js';

import achievementsJson from 'truescrub/proto/achievements.json';
import {AchievementConfigurationSchema} from 'truescrub/proto/profile_pb.js';


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

import ach_distinct_maps from "client/pages/achievements/distinct_maps.png";
import ach_distinct_teammates from "client/pages/achievements/distinct_teammates.png";
import ach_multi_kill_rounds from "client/pages/achievements/multi_kill_rounds.png";
import ach_rounds_played from "client/pages/achievements/rounds_played.png";
import ach_seasons_played from "client/pages/achievements/seasons_played.png";
import ach_survived_losses from "client/pages/achievements/survived_losses.png";
import ach_total_headshots from "client/pages/achievements/total_headshots.png";
import ach_total_kills from "client/pages/achievements/total_kills.png";
import ach_total_mvps from "client/pages/achievements/total_mvps.png";
import ach_zero_damage_rounds from "client/pages/achievements/zero_damage_rounds.png";

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

const ACH_IMAGES: Record<string, string> = {
  "distinct_maps": ach_distinct_maps,
  "distinct_teammates": ach_distinct_teammates,
  "multi_kill_rounds": ach_multi_kill_rounds,
  "rounds_played": ach_rounds_played,
  "seasons_played": ach_seasons_played,
  "survived_losses": ach_survived_losses,
  "total_headshots": ach_total_headshots,
  "total_kills": ach_total_kills,
  "total_mvps": ach_total_mvps,
  "zero_damage_rounds": ach_zero_damage_rounds,
};

const config = fromJson(AchievementConfigurationSchema, achievementsJson);

export interface TierConfig {
  name: string;
  threshold: number;
}

export interface AchievementConfig {
  id: string;
  name: string;
  tiers: TierConfig[];
}

export interface AchievementProgress {
  achievementId: string;
  currentValue: number;
}

export interface EnrichedTier extends TierConfig {
  earned: boolean;
}

export interface EnrichedAchievement extends AchievementConfig {
  currentValue: number;
  tiers: EnrichedTier[];
  highestEarnedTier?: EnrichedTier;
}

export interface AchievementCalculationResult {
  enrichedAchievements: EnrichedAchievement[];
  earnedCount: number;
  totalTiers: number;
}

export function calculateAchievements(
    configAchievements: AchievementConfig[],
    playerProgress: AchievementProgress[]
): AchievementCalculationResult {
  let earnedCount = 0;
  let totalTiers = 0;

  const enrichedAchievements = configAchievements.map(def => {
    const progress = playerProgress.find(a => a.achievementId === def.id);
    const currentValue = progress ? progress.currentValue : 0;

    const tiers = def.tiers.map(tier => {
      totalTiers++;
      const earned = currentValue >= tier.threshold;
      if (earned) earnedCount++;
      return {...tier, earned};
    });

    const highestEarnedTier = [...tiers].reverse().find(t => t.earned);

    return {
      ...def,
      currentValue,
      tiers,
      highestEarnedTier
    };
  });

  return {
    enrichedAchievements,
    earnedCount,
    totalTiers
  };
}

export function getLocalTimezoneOffset(date: Date = new Date()) {
  const offsetMinutes = -date.getTimezoneOffset();
  const sign = offsetMinutes >= 0 ? '+' : '-';
  const absMinutes = Math.abs(offsetMinutes);
  const hours = String(Math.floor(absMinutes / 60)).padStart(2, '0');
  const minutes = String(absMinutes % 60).padStart(2, '0');
  return `${sign}${hours}:${minutes}`;
}

export function ProfilePage() {
  const {playerId} = useParams();
  const id = BigInt(playerId || '0');
  const skillGroupsConfig = React.useMemo(() => fromJson(SkillGroupConfigurationSchema, skillGroupsJson), []);

  const [selectedSeason, setSelectedSeason] = useState<number>(0);
  const [showImpact, setShowImpact] = useState<boolean>(false);

  const {
    data: profileData,
    isLoading: profileLoading,
    error: profileError
  } = useQuery(getProfile, {playerId: id});
  const {
    data: seasonsData,
    isLoading: seasonsLoading
  } = useQuery(getAvailableSeasons, {});
  const {
    data: historyData,
    isLoading: historyLoading
  } = useQuery(getSkillHistory, {
    playerId: id,
    seasonId: selectedSeason,
    timezone: getLocalTimezoneOffset()
  });

  const chartData = useMemo(() => {
    if (!historyData?.history) return [];
    return historyData.history.map((point: any) => {
      const date = new Date(
          point.date!.year,
          point.date!.month - 1,
          point.date!.day
      ).getTime();
      const mu = point.skill?.mu || 0;
      const sigma = point.skill?.sigma || 0;
      return {
        date,
        mmr: Math.floor(mu - 2 * sigma),
        confidence: [mu - 2 * sigma, mu + 2 * sigma],
        impact: point.impactRating !== undefined ? point.impactRating : null,
        skillGroup: skillGroupName(point.skill!.mmr, skillGroupsConfig)
      };
    }).sort((a: any, b: any) => a.date - b.date);
  }, [historyData, skillGroupsConfig]);

  if (profileLoading || seasonsLoading) {
    return <LoadingState/>;
  }

  if (profileError || !profileData?.player) {
    return <ErrorState message={
        profileError?.message || "Player not found"}/>;
  }

  const {
    player,
    roundsWon,
    roundsLost,
    seasonSkills,
    overallRating,
    seasonRatings,
    achievements
  } = profileData;
  const currentSeason = seasonsData?.availableSeasons?.length || 0;

  const allSeasonIds = Object.keys(seasonSkills)
      .map(Number)
      .sort((a: any, b: any) => b - a);

  const {
    enrichedAchievements,
    earnedCount,
    totalTiers
  } = calculateAchievements(config.achievements as any[], achievements as any[]);

  const CustomTooltip = ({active, payload, label}: any) => {
    if (active && payload && payload.length) {
      const data = payload[0].payload;
      return (
          <div
              className="bg-slate-900/95 border border-white/10 rounded-xl p-3 shadow-xl backdrop-blur-md">
            <div className="font-bold text-white mb-1">{new Date(label).toLocaleDateString()}</div>
            <div className="text-sm">
              <strong>{data.skillGroup}</strong> (<span style={{color: '#22d3ee'}}>{data.mmr}</span>)
            </div>
            {showImpact && data.impact !== null && (
                <div className="text-sm mt-1">
                  Impact: <strong>{data.impact.toFixed(2)}</strong>
                </div>
            )}
          </div>
      );
    }
    return null;
  };

  return (
      <div className="max-w-7xl mx-auto px-4 py-8 relative">
        <div className="mb-10 relative">
          <div
              className="absolute -top-10 -left-10 w-64 h-64 bg-brand-500/20 rounded-full blur-3xl pointer-events-none"></div>
          <div
              className="absolute -top-10 left-40 w-64 h-64 bg-purple-500/10 rounded-full blur-3xl pointer-events-none"></div>

          <div
              className="flex flex-col md:flex-row items-start md:items-center justify-between w-full mb-6 relative z-10 gap-6 glass-panel p-8 rounded-[2rem] shadow-2xl border border-white/5">
            <div className="flex flex-col md:flex-row items-start md:items-center gap-6">
              <div className="relative group">
                <div
                    className="absolute inset-0 bg-brand-400 rounded-full blur-xl opacity-30 group-hover:opacity-60 transition-opacity duration-500"></div>
                <div
                    className="w-24 h-24 rounded-full bg-gradient-to-br from-brand-500 to-purple-600 flex items-center justify-center text-4xl font-black text-white shadow-2xl border-4 border-dark-bg relative z-10 transform group-hover:scale-105 transition-transform duration-500">
                  {player.steamName?.[0]?.toUpperCase()}
                </div>
              </div>
              <div className="flex flex-col">
                <div className="flex items-center gap-4">
                  <h1 className="text-5xl text-transparent bg-clip-text bg-gradient-to-br from-white via-brand-100 to-brand-300 md:text-6xl font-black tracking-tight drop-shadow-lg pb-1">{player.steamName}</h1>
                </div>
                <span
                    className="mt-1 font-bold text-transparent bg-clip-text bg-gradient-to-r from-brand-300 to-purple-400 text-xl tracking-wide drop-shadow-md">{skillGroupName(player.skill!.mmr, skillGroupsConfig)}</span>
                <div className="flex items-center gap-3 mt-3">
                  <div
                      className="flex items-center gap-1.5 bg-green-500/10 border border-green-500/20 px-3 py-1 rounded-lg shadow-inner">
                    <span
                        className="text-green-500 font-black text-xs uppercase tracking-wider">Wins</span>
                    <span className="text-white font-mono font-bold">{roundsWon}</span>
                  </div>
                  <div
                      className="flex items-center gap-1.5 bg-red-500/10 border border-red-500/20 px-3 py-1 rounded-lg shadow-inner">
                    <span
                        className="text-red-500 font-black text-xs uppercase tracking-wider">Losses</span>
                    <span className="text-white font-mono font-bold">{roundsLost}</span>
                  </div>
                </div>
              </div>
            </div>

            <div className="hidden md:block">
              <img src={RANKS[skillGroupName(player.skill!.mmr, skillGroupsConfig)] || ""}
                   alt={skillGroupName(player.skill!.mmr, skillGroupsConfig)}
                   className="w-32 h-32 object-contain filter drop-shadow-[0_5px_15px_rgba(0,0,0,0.5)] transform hover:scale-110 transition-transform duration-300"/>
            </div>
          </div>

          {/* Tab Navigation */}
          <div className="flex items-center gap-4 mb-4 pb-2 overflow-x-auto relative z-10">
            <NavLink to={`/profiles/${playerId}`} end
                     className={({isActive}) => `px-6 py-2.5 rounded-full font-bold uppercase tracking-widest text-sm transition-all ${isActive ? 'bg-brand-500 text-white shadow-[0_0_15px_rgba(14,165,233,0.5)]' : 'text-slate-400 hover:text-white hover:bg-white/5'}`}>
              Overview
            </NavLink>
            <NavLink to={`/profiles/${playerId}/matches`}
                     className={({isActive}) => `px-6 py-2.5 rounded-full font-bold uppercase tracking-widest text-sm transition-all ${isActive ? 'bg-brand-500 text-white shadow-[0_0_15px_rgba(14,165,233,0.5)]' : 'text-slate-400 hover:text-white hover:bg-white/5'}`}>
              Matches
            </NavLink>
            <NavLink to={`/profiles/${playerId}/team_records`}
                     className={({isActive}) => `px-6 py-2.5 rounded-full font-bold uppercase tracking-widest text-sm transition-all ${isActive ? 'bg-brand-500 text-white shadow-[0_0_15px_rgba(14,165,233,0.5)]' : 'text-slate-400 hover:text-white hover:bg-white/5'}`}>
              Team Records
            </NavLink>
          </div>
        </div>

        <Routes>
          <Route index element={
            <>
              <div className="grid lg:grid-cols-2 gap-8 mb-8">
                {/* Player Skill Table */}
                <div
                    className="glass-panel rounded-[2rem] overflow-hidden shadow-2xl flex flex-col relative w-full">
                  <div
                      className="absolute inset-0 bg-gradient-to-b from-slate-800/50 to-transparent pointer-events-none"></div>
                  <div className="p-6 border-b border-white/10 relative z-10">
                    <h2 className="text-2xl font-bold text-brand-400 flex items-center gap-2 drop-shadow-sm">
                      <svg className="w-6 h-6 text-brand-400 drop-shadow-md" fill="none"
                           viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2"
                              d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6"/>
                      </svg>
                      Player Skill
                    </h2>
                  </div>
                  <div className="overflow-x-auto flex-1 relative z-10">
                    <table className="w-full text-left border-collapse h-full">
                      <thead>
                      <tr className="bg-dark-card/50 border-b border-white/5 text-slate-400 text-xs font-bold uppercase tracking-widest">
                        <th className="py-4 px-2 sm:px-4">Season</th>
                        <th className="py-4 px-2 sm:px-4 text-right">MMR</th>
                        <th className="py-4 px-2 sm:px-4">Percentile</th>
                        <th className="py-4 px-2 sm:px-4">Skill Group</th>
                      </tr>
                      </thead>
                      <tbody className="divide-y divide-white/5">
                      {allSeasonIds.map(seasonId => {
                        const sp = seasonSkills[seasonId];
                        if (!sp) return null;
                        const leftOffset = Math.min(sp.lowerBound, 0.9);
                        const width = Math.max(sp.upperBound, 0.1) - leftOffset;
                        return (
                            <tr key={seasonId}
                                className="hover:bg-slate-800/30 transition-colors group">
                              <td className="py-3 px-2 sm:px-4 font-medium text-slate-300">{seasonId}</td>
                              <td className="py-3 px-2 sm:px-4 text-right font-mono text-brand-400 group-hover:text-brand-300 transition-colors"
                                  title={`${sp.skill?.mu?.toFixed(2)} ± ${sp.skill?.sigma?.toFixed(2)}σ`}>
                                {Math.floor(sp.skill?.mmr || 0)}
                              </td>
                              <td className="py-3 px-2 sm:px-4">
                                <div className="flex items-center gap-2">
                            <span
                                className="text-xs font-medium text-slate-400 w-10 text-right">{(sp.lowerBound * 100).toFixed(1)}%</span>
                                  <div
                                      className="h-2 w-24 bg-slate-900/80 rounded-full shadow-inner border border-white/5 relative overflow-hidden flex items-center">
                                    <div
                                        className="absolute h-full rounded-full bg-gradient-to-r from-brand-600 via-brand-400 to-brand-300 shadow-[0_0_10px_rgba(56,189,248,0.4)]"
                                        style={{
                                          left: `${leftOffset * 100}%`,
                                          width: `${width * 100}%`
                                        }}></div>
                                  </div>
                                  <span
                                      className="text-xs font-medium text-slate-400 w-10">{(sp.upperBound * 100).toFixed(1)}%</span>
                                </div>
                              </td>
                              <td className="py-3 px-2 sm:px-4">
                                <div className="flex items-center gap-2">
                                  <img
                                      src={RANKS[skillGroupName(sp.skill!.mmr, skillGroupsConfig)] || ""}
                                      alt={skillGroupName(sp.skill!.mmr, skillGroupsConfig)}
                                      className="w-8 h-8 object-contain drop-shadow-md"/>
                                  <span
                                      className="bg-slate-900/80 px-3 py-1.5 rounded-xl text-xs font-semibold text-brand-300 border border-brand-500/20 shadow-[inset_0_1px_0_rgba(255,255,255,0.05)] whitespace-nowrap">{skillGroupName(sp.skill!.mmr, skillGroupsConfig)}</span>
                                </div>
                              </td>
                            </tr>
                        );
                      })}
                      </tbody>
                      <tfoot className="bg-dark-card/50 border-t border-white/10">
                      {(() => {
                        return (
                            <tr>
                              <td className="py-4 px-2 sm:px-4 font-bold text-white uppercase tracking-wider text-xs">Overall</td>
                              <td className="py-4 px-2 sm:px-4 text-right font-mono font-bold text-brand-400 text-lg"
                                  title={`${player.skill?.mu?.toFixed(2)} ± ${player.skill?.sigma?.toFixed(2)}σ`}>{Math.floor(player.skill?.mmr || 0)}</td>
                              <td className="py-4 px-2 sm:px-4">
                              </td>
                              <td className="py-4 px-2 sm:px-4">
                                <div className="flex items-center gap-2">
                                  <img
                                      src={RANKS[skillGroupName(player.skill!.mmr, skillGroupsConfig)] || ""}
                                      alt={skillGroupName(player.skill!.mmr, skillGroupsConfig)}
                                      className="w-10 h-10 object-contain drop-shadow-md"/>
                                  <span
                                      className="bg-gradient-to-r from-brand-500 to-purple-600 px-3 py-1.5 rounded-xl text-xs font-bold text-white shadow-lg whitespace-nowrap">{skillGroupName(player.skill!.mmr, skillGroupsConfig)}</span>
                                </div>
                              </td>
                            </tr>
                        );
                      })()}
                      </tfoot>
                    </table>
                  </div>
                </div>

                {/* Skill History Chart */}
                <div
                    className="glass-panel rounded-[2rem] overflow-hidden shadow-2xl flex flex-col relative w-full">
                  <div
                      className="absolute inset-0 bg-gradient-to-b from-slate-800/50 to-transparent pointer-events-none"></div>
                  <div
                      className="p-6 border-b border-white/10 relative z-10 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                    <h2 className="text-2xl font-bold text-purple-400 flex items-center gap-2 drop-shadow-sm">
                      <svg className="w-6 h-6 text-purple-400 drop-shadow-md" fill="none"
                           viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2"
                              d="M7 12l3-3 3 3 4-4M8 21l4-4 4 4M3 4h18M4 4h16v12a1 1 0 01-1 1H5a1 1 0 01-1-1V4z"/>
                      </svg>
                      Skill History
                    </h2>
                    <div className="flex items-center gap-3">
                      <div className="text-sm font-medium flex items-center gap-1">
                        {[0, ...Array.from({length: currentSeason}, (_, i) => i + 1)].map(season => {
                          const label = season === 0 ? 'all' : season;
                          if (season === selectedSeason) {
                            return <strong key={season}
                                           className="px-2.5 py-1 bg-brand-500/20 shadow-inner border border-brand-500/30 rounded-lg text-brand-300">{label}</strong>
                          }
                          return <button key={season} onClick={() => setSelectedSeason(season)}
                                         className="px-2.5 py-1 text-brand-400 hover:text-brand-300 hover:underline transition-colors">{label}</button>
                        })}
                      </div>
                      <button onClick={() => setShowImpact(!showImpact)} type="button"
                              className="btn-secondary text-xs px-4 py-1.5 rounded-full font-bold uppercase tracking-wider backdrop-blur-md bg-dark-card/50 hover:bg-white/10 border-white/10 transition-all text-slate-300 hover:text-white">
                        {showImpact ? 'Hide impact' : 'Show impact'}
                      </button>
                    </div>
                  </div>
                  <div className="relative w-full flex-1 min-h-[320px] p-4">
                    {historyLoading ? (
                        <div className="absolute inset-0 flex items-center justify-center">
                          <div
                              className="w-8 h-8 border-4 border-brand-500/20 border-t-brand-500 rounded-full animate-spin"></div>
                        </div>
                    ) : (
                        <ResponsiveContainer width="100%" height="100%">
                          <ComposedChart data={chartData}
                                         margin={{top: 10, right: 10, left: -20, bottom: 0}}>
                            <XAxis
                                dataKey="date"
                                type="number"
                                domain={['dataMin', 'dataMax']}
                                tickFormatter={(tick) => new Date(tick).toLocaleDateString()}
                                stroke="rgba(255,255,255,0.1)"
                                tick={{fill: '#94a3b8', fontSize: 12}}
                            />
                            <YAxis
                                yAxisId="left"
                                domain={['auto', 'auto']}
                                stroke="rgba(255,255,255,0.1)"
                                tick={{fill: '#94a3b8', fontSize: 12}}
                            />
                            {showImpact && (
                                <YAxis
                                    yAxisId="right"
                                    orientation="right"
                                    domain={[0, 2]}
                                    stroke="rgba(255,255,255,0.1)"
                                    tick={{fill: '#94a3b8', fontSize: 12}}
                                />
                            )}
                            <Tooltip content={<CustomTooltip/>}/>
                            <Area
                                yAxisId="left"
                                type="monotone"
                                dataKey="confidence"
                                stroke="none"
                                fill="#c084fc"
                                fillOpacity={0.10}
                                isAnimationActive={false}
                            />
                            <Line
                                yAxisId="left"
                                type="monotone"
                                dataKey="mmr"
                                stroke="#22d3ee"
                                strokeWidth={2}
                                dot={{fill: '#0f172a', stroke: '#22d3ee', strokeWidth: 2, r: 4}}
                                isAnimationActive={false}
                            />
                            {showImpact && (
                                <Scatter
                                    yAxisId="right"
                                    dataKey="impact"
                                    fill="#10b981"
                                    isAnimationActive={false}
                                />
                            )}
                          </ComposedChart>
                        </ResponsiveContainer>
                    )}
                  </div>
                </div>
              </div>

              {/* Player Impact Table */}
              <div className="glass-panel rounded-[2rem] overflow-hidden shadow-2xl relative mb-8">
                <div
                    className="absolute inset-0 bg-gradient-to-b from-slate-800/50 to-transparent pointer-events-none"></div>
                <div className="p-6 border-b border-white/10 relative z-10">
                  <h2 className="text-2xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-green-400 to-emerald-600 flex items-center gap-2 drop-shadow-sm">
                    <svg className="w-6 h-6 text-green-400 drop-shadow-md" fill="none"
                         viewBox="0 0 24 24"
                         stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2"
                            d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"/>
                    </svg>
                    Player Impact
                  </h2>
                </div>
                <div className="overflow-x-auto relative z-10">
                  <table className="w-full text-left border-collapse">
                    <thead>
                    <tr className="bg-dark-card/50 border-b border-white/5 text-slate-400 text-xs font-bold uppercase tracking-widest">
                      <th className="py-4 px-4 sm:px-6">Season</th>
                      <th className="py-4 px-4 sm:px-6 text-right"
                          title="Percent of rounds MVP">MVP
                      </th>
                      <th className="py-4 px-4 sm:px-6 text-right"
                          title="Average kills per round">KPR
                      </th>
                      <th className="py-4 px-4 sm:px-6 text-right"
                          title="Average deaths per round">DPR
                      </th>
                      <th className="py-4 px-4 sm:px-6 text-right"
                          title="Average damage per round">ADR
                      </th>
                      <th className="py-4 px-4 sm:px-6 text-right"
                          title="Percent of rounds with kills, assists or survived">KAS
                      </th>
                      <th className="py-4 px-4 sm:px-6 text-center text-green-400">Impact</th>
                    </tr>
                    </thead>
                    <tbody className="divide-y divide-white/5">
                    {allSeasonIds.map(seasonId => {
                      const sr = seasonRatings[seasonId];
                      if (!sr) return null;
                      const impactClass = (sr.impactRating !== undefined && sr.impactRating > 1.0)
                          ? "bg-green-500/20 text-green-400 border border-green-500/30"
                          : "bg-slate-800 text-slate-400 border border-white/5";

                      return (
                          <tr key={seasonId}
                              className="hover:bg-slate-800/30 transition-colors group">
                            <td className="py-3 px-4 sm:px-6 font-medium text-slate-300">{seasonId}</td>
                            <td className="py-3 px-4 sm:px-6 text-right font-mono text-slate-400 group-hover:text-white transition-colors">{(sr.mvpRating * 100).toFixed(0)}%</td>
                            <td className="py-3 px-4 sm:px-6 text-right font-mono text-slate-400 group-hover:text-white transition-colors">{sr.killRating.toFixed(2)}</td>
                            <td className="py-3 px-4 sm:px-6 text-right font-mono text-slate-400 group-hover:text-white transition-colors">{sr.deathRating.toFixed(2)}</td>
                            <td className="py-3 px-4 sm:px-6 text-right font-mono text-slate-400 group-hover:text-white transition-colors">{sr.damageRating.toFixed(0)}</td>
                            <td className="py-3 px-4 sm:px-6 text-right font-mono text-slate-400 group-hover:text-white transition-colors">{(sr.kasRating * 100).toFixed(0)}%</td>
                            <td className="py-3 px-4 sm:px-6 text-center">
                      <span
                          className={`inline-flex items-center px-3 py-1 rounded-xl text-xs font-bold whitespace-nowrap shadow-inner ${impactClass}`}>
                        {sr.impactRating !== undefined ? sr.impactRating.toFixed(2) : '-'}
                      </span>
                            </td>
                          </tr>
                      );
                    })}
                    </tbody>
                    <tfoot className="bg-dark-card/50 border-t border-white/10">
                    {overallRating && (
                        <tr>
                          <td className="py-4 px-4 sm:px-6 font-bold text-white uppercase tracking-wider text-xs">Overall</td>
                          <td className="py-4 px-4 sm:px-6 text-right font-mono font-medium text-lg">{(overallRating.mvpRating * 100).toFixed(0)}%</td>
                          <td className="py-4 px-4 sm:px-6 text-right font-mono font-medium text-lg">{overallRating.killRating.toFixed(2)}</td>
                          <td className="py-4 px-4 sm:px-6 text-right font-mono font-medium text-lg">{overallRating.deathRating.toFixed(2)}</td>
                          <td className="py-4 px-4 sm:px-6 text-right font-mono font-medium text-lg">{overallRating.damageRating.toFixed(0)}</td>
                          <td className="py-4 px-4 sm:px-6 text-right font-mono font-medium text-lg">{(overallRating.kasRating * 100).toFixed(0)}%</td>
                          <td className="py-4 px-4 sm:px-6 text-center">
                    <span
                        className={`inline-flex items-center px-3 py-1.5 rounded-xl text-sm font-bold whitespace-nowrap shadow-lg ${(overallRating.impactRating !== undefined && overallRating.impactRating > 1.0) ? "bg-gradient-to-r from-green-400 to-emerald-600 text-white" : "bg-slate-700 text-white border border-white/5"}`}>
                      {overallRating.impactRating !== undefined ? overallRating.impactRating.toFixed(2) : '-'}
                    </span>
                          </td>
                        </tr>
                    )}
                    </tfoot>
                  </table>
                </div>
              </div>

              {/* Achievements */}
              <div className="glass-panel rounded-[2rem] overflow-hidden shadow-2xl relative">
                <div
                    className="absolute inset-0 bg-gradient-to-b from-slate-800/50 to-transparent pointer-events-none"></div>
                <div
                    className="p-6 border-b border-white/10 relative z-10 flex items-center justify-between">
                  <h2 className="text-2xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-amber-400 to-yellow-600 flex items-center gap-2 drop-shadow-sm">
                    🏆 Achievements
                  </h2>
                  <span className="text-sm font-normal text-slate-500">
            {earnedCount}/{totalTiers}
          </span>
                </div>
                <div className="overflow-x-auto relative z-10">
                  <table className="w-full text-left border-collapse">
                    <thead>
                    <tr className="bg-dark-card/50 border-b border-white/5 text-slate-400 text-xs font-bold uppercase tracking-widest">
                      <th className="py-3 px-4 sm:px-6 w-[140px]"></th>
                      <th className="py-3 px-4 sm:px-6">Category</th>
                      <th className="py-3 px-4 sm:px-6">Tiers</th>
                      <th className="py-3 px-4 sm:px-6 text-right">Count</th>
                    </tr>
                    </thead>
                    <tbody className="divide-y divide-white/5">
                    {enrichedAchievements.map((achievement: any) => (
                        <tr key={achievement.id}
                            className="hover:bg-slate-800/30 transition-colors">
                          <td className="py-3 px-4 sm:px-6">
                            {achievement.highestEarnedTier && (
                                <img
                                    src={ACH_IMAGES[achievement.id] || ""}
                                    alt=""
                                    className="h-12 w-[120px] object-cover rounded-lg"
                                />
                            )}
                          </td>
                          <td className="py-4 px-4 sm:px-6">
                            <div
                                className="font-medium text-slate-300 text-sm whitespace-nowrap">{achievement.name}</div>
                          </td>
                          <td className="py-4 px-4 sm:px-6">
                            <div className="flex gap-1.5 flex-wrap">
                              {achievement.tiers.map((tier: any, i: number) => (
                                  <span
                                      key={i}
                                      className={`inline-flex items-center px-3 py-1 rounded-lg text-xs font-semibold whitespace-nowrap ${tier.earned ? 'bg-brand-500/20 text-brand-400 border border-brand-500/30' : 'bg-slate-800/50 text-slate-600 border border-white/5'}`}>
                          {tier.earned && '✓ '} {tier.name}
                                    <span
                                        className={`ml-1 text-[10px] ${tier.earned ? 'text-brand-500/60' : 'text-slate-700'}`}>{tier.threshold}</span>
                        </span>
                              ))}
                            </div>
                          </td>
                          <td className="py-4 px-4 sm:px-6 text-right">
                    <span
                        className={`font-mono text-sm ${achievement.highestEarnedTier ? 'text-white' : 'text-slate-500'}`}>
                      {achievement.currentValue}
                    </span>
                          </td>
                        </tr>
                    ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </>
          }/>
          <Route path="matches" element={<MatchesTab playerId={id}/>}/>
          <Route path="team_records" element={<TeamRecordsTab playerId={id}/>}/>
        </Routes>
      </div>
  );
}
