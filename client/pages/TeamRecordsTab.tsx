import React, {useState, useMemo} from 'react';
import {useQuery} from '@connectrpc/connect-query';
import {getPlayerTeamRecords} from 'proto/profile_service-ProfileService_connectquery.js';
import {LoadingState} from 'client/components/LoadingState.js';
import {ErrorState} from 'client/components/ErrorState.js';

export function TeamRecordsTab({playerId}: { playerId: bigint }) {
  const {data, isLoading, error} = useQuery(getPlayerTeamRecords, {playerId});
  const [sortField, setSortField] = useState<'played' | 'won' | 'winrate'>('played');

  const sortedRecords = useMemo(() => {
    if (!data?.teamRecords) return [];
    return [...data.teamRecords].sort((a, b) => {
      const totalA = a.roundsWon + a.roundsLost;
      const totalB = b.roundsWon + b.roundsLost;
      if (sortField === 'played') {
        return totalB - totalA;
      } else if (sortField === 'won') {
        return b.roundsWon - a.roundsWon;
      } else {
        const wrA = totalA > 0 ? a.roundsWon / totalA : 0;
        const wrB = totalB > 0 ? b.roundsWon / totalB : 0;
        if (wrB !== wrA) return wrB - wrA;
        return totalB - totalA;
      }
    });
  }, [data, sortField]);

  if (isLoading) return <LoadingState message="Loading team records..."/>;
  if (error) return <ErrorState message={error.message}/>;

  return (
    <div className="flex flex-col gap-4 animate-fade-in mb-8">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-2">
        <h2 className="text-2xl font-bold text-white flex items-center gap-3">
          <svg className="w-6 h-6 text-brand-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
          </svg>
          Team Records
        </h2>
        <div className="flex bg-slate-900/80 rounded-xl p-1 border border-white/5 shadow-inner">
          <button onClick={() => setSortField('played')} className={`px-4 py-1.5 rounded-lg text-sm font-bold transition-all ${sortField === 'played' ? 'bg-brand-500 text-white shadow-md' : 'text-slate-400 hover:text-white'}`}>Most Played</button>
          <button onClick={() => setSortField('won')} className={`px-4 py-1.5 rounded-lg text-sm font-bold transition-all ${sortField === 'won' ? 'bg-brand-500 text-white shadow-md' : 'text-slate-400 hover:text-white'}`}>Most Wins</button>
          <button onClick={() => setSortField('winrate')} className={`px-4 py-1.5 rounded-lg text-sm font-bold transition-all ${sortField === 'winrate' ? 'bg-brand-500 text-white shadow-md' : 'text-slate-400 hover:text-white'}`}>Win Rate</button>
        </div>
      </div>
      
      <div className="glass-panel rounded-[2rem] overflow-hidden shadow-2xl relative">
        <div className="absolute inset-0 bg-gradient-to-b from-slate-800/50 to-transparent pointer-events-none"></div>
        <div className="overflow-x-auto relative z-10">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-dark-card/50 border-b border-white/5 text-slate-400 text-xs font-bold uppercase tracking-widest">
                <th className="py-4 px-6">Teammates</th>
                <th className="py-4 px-6 text-right">Rounds Played</th>
                <th className="py-4 px-6 text-right">Wins</th>
                <th className="py-4 px-6 text-right">Losses</th>
                <th className="py-4 px-6 text-right">Win %</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5">
              {sortedRecords.map((rec, i) => {
                const total = rec.roundsWon + rec.roundsLost;
                const winRate = total > 0 ? (rec.roundsWon / total) * 100 : 0;
                
                return (
                  <tr key={i} className="hover:bg-slate-800/30 transition-colors">
                    <td className="py-4 px-6">
                      <div className="flex flex-wrap gap-2">
                        {rec.teamMembers.map((name, j) => (
                          <span key={j} className="px-3 py-1 bg-white/5 rounded text-sm text-slate-200 border border-white/10">
                            {name}
                          </span>
                        ))}
                      </div>
                    </td>
                    <td className="py-4 px-6 text-right font-mono text-slate-300 font-bold">{total}</td>
                    <td className="py-4 px-6 text-right font-mono text-green-400 font-bold">{rec.roundsWon}</td>
                    <td className="py-4 px-6 text-right font-mono text-red-400 font-bold">{rec.roundsLost}</td>
                    <td className="py-4 px-6 text-right">
                      <span className={`inline-flex px-2.5 py-1 rounded-lg text-sm font-bold shadow-inner ${winRate >= 50 ? 'bg-green-500/10 text-green-400 border border-green-500/20' : 'bg-red-500/10 text-red-400 border border-red-500/20'}`}>
                        {winRate.toFixed(1)}%
                      </span>
                    </td>
                  </tr>
                );
              })}
              {sortedRecords.length === 0 && (
                <tr>
                  <td colSpan={5} className="py-12 text-center text-slate-400">No team records found.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
