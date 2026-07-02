import React from 'react';
import {fromJson} from '@bufbuild/protobuf';
import {SkillGroupConfigurationSchema} from 'truescrub/proto/profile_pb.js';
import skillGroupsJson from 'truescrub/proto/skill_groups.json';

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

export function SkillGroupsPage() {
  const config = React.useMemo(() => fromJson(SkillGroupConfigurationSchema, skillGroupsJson), []);

  return (
      <div className="flex flex-col">
        <div className="mb-8">
          <h1 className="text-4xl font-bold text-white mb-2">Skill Groups</h1>
          <p className="text-slate-400">The distribution and MMR boundaries for player skill tiers.</p>
        </div>

        <div className="glass-panel rounded-2xl overflow-hidden shadow-2xl">
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
              <tr className="bg-dark-card border-b border-dark-border text-slate-300">
                <th className="py-4 px-6 font-semibold uppercase tracking-wider text-sm">Name</th>
                <th className="py-4 px-6 font-semibold uppercase tracking-wider text-sm">MMR Range</th>
              </tr>
              </thead>
              <tbody className="divide-y divide-dark-border/50 bg-dark-bg/30">
              {config.skillGroups.map((group, index) => {
                const nextGroup = config.skillGroups[index + 1];
                const lowerBound = group.lowerBound === Number.NEGATIVE_INFINITY ? '-∞' : group.lowerBound;
                const upperBound = nextGroup ? nextGroup.lowerBound : '∞';
                
                return (
                    <tr key={group.name} className="hover:bg-slate-800/50 transition-colors group">
                      <td className="py-4 px-6 font-medium text-white group-hover:text-brand-400 transition-colors">
                        <div className="flex items-center gap-4">
                          <div className="w-14 h-14 flex items-center justify-center relative">
                            <div className="absolute inset-0 bg-brand-500/10 rounded-full blur-md opacity-0 group-hover:opacity-100 transition-opacity duration-300"></div>
                            <img src={RANKS[group.name] || ""} alt={group.name} className="w-full h-full object-contain filter drop-shadow-xl group-hover:scale-110 transition-transform duration-300 relative z-10" />
                          </div>
                          <span className="text-lg tracking-wide">{group.name}</span>
                        </div>
                      </td>
                      <td className="py-4 px-6 text-slate-300 font-mono text-sm">
                        <span className="bg-dark-card border border-dark-border px-2 py-1 rounded">{lowerBound}</span>
                        <span className="mx-2 text-slate-500">&ndash;</span>
                        <span className="bg-dark-card border border-dark-border px-2 py-1 rounded">{upperBound}</span>
                      </td>
                    </tr>
                );
              })}
              </tbody>
            </table>
          </div>
        </div>
      </div>
  );
}
