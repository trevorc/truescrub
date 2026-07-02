import React from 'react';
import {useQuery} from '@connectrpc/connect-query';
import {getPlayerRounds} from 'proto/profile_service-ProfileService_connectquery.js';
import {LoadingState} from 'client/components/LoadingState.js';
import {ErrorState} from 'client/components/ErrorState.js';

export function MatchesTab({playerId}: { playerId: bigint }) {
  const {data, isLoading, error} = useQuery(getPlayerRounds, {playerId});

  if (isLoading) return <LoadingState message="Loading match history..."/>;
  if (error) return <ErrorState message={error.message}/>;

  return (
    <div className="flex flex-col gap-6 animate-fade-in mb-8">
      <h2 className="text-2xl font-bold text-white mb-2 flex items-center gap-3">
        <svg className="w-6 h-6 text-brand-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        Recent Rounds
      </h2>
      {data?.rounds.length === 0 ? (
        <div className="glass-panel p-8 rounded-2xl text-center text-slate-400">
          No matches found for this player.
        </div>
      ) : (
        <div className="flex flex-col gap-4">
          {data?.rounds.map((round, index) => {
            const date = new Date(round.createdAt?.year || 0, (round.createdAt?.month || 1) - 1, round.createdAt?.day || 1).toLocaleDateString();
            
            return (
              <div key={index} className="glass-panel p-6 rounded-2xl shadow-lg border border-white/5 hover:bg-white/5 transition-colors">
                <div className="flex flex-col md:flex-row justify-between md:items-center gap-4 mb-4 pb-4 border-b border-white/10">
                  <span className="text-brand-400 font-bold tracking-widest uppercase text-sm">
                    {date}
                  </span>
                </div>
                
                <div className="grid md:grid-cols-2 gap-8">
                  <div>
                    <h3 className="text-green-400 font-bold mb-3 flex items-center gap-2">
                      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                      </svg>
                      Winning Team
                    </h3>
                    <div className="flex flex-wrap gap-2">
                      {round.winningTeamNames.map((name, i) => (
                        <span key={i} className="px-3 py-1.5 bg-slate-800/50 text-slate-300 rounded-lg text-sm border border-white/5">
                          {name}
                        </span>
                      ))}
                    </div>
                  </div>
                  <div>
                    <h3 className="text-red-400 font-bold mb-3 flex items-center gap-2">
                      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z" />
                      </svg>
                      Losing Team
                    </h3>
                    <div className="flex flex-wrap gap-2">
                      {round.losingTeamNames.map((name, i) => (
                        <span key={i} className="px-3 py-1.5 bg-slate-800/50 text-slate-300 rounded-lg text-sm border border-white/5">
                          {name}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
