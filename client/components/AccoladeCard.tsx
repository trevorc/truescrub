import {useState} from "react";
import {Accolade} from "proto/highlights_service_pb.js";

import acc_grand_slamma_jamma from "client/components/accolades/grand_slamma_jamma.png";
import acc_moral_support from "client/components/accolades/moral_support.png";
import acc_winner_winner_chicken_dinner
  from "client/components/accolades/winner_winner_chicken_dinner.png";
import acc_glass_cannon from "client/components/accolades/glass_cannon.png";
import acc_decoy from "client/components/accolades/decoy.png";
import acc_just_uninstall from "client/components/accolades/just_uninstall.png";
import acc_untouchable from "client/components/accolades/untouchable.png";
import acc_stealthy_strategist from "client/components/accolades/stealthy_strategist.png";
import acc_blind_fire from "client/components/accolades/blind_fire.png";
import acc_bench_warmer from "client/components/accolades/bench_warmer.png";
import acc_efficiency_expert from "client/components/accolades/efficiency_expert.png";
import acc_headshot_hunter from "client/components/accolades/headshot_hunter.png";
import acc_high_roller from "client/components/accolades/high_roller.png";
import acc_un_mvp from "client/components/accolades/un_mvp.png";
import acc_hard_carry from "client/components/accolades/hard_carry.png";
import acc_top_frag from "client/components/accolades/top_frag.png";
import acc_team_player from "client/components/accolades/team_player.png";
import acc_cannon_fodder from "client/components/accolades/cannon_fodder.png";
import acc_pacifist from "client/components/accolades/pacifist.png";
import acc_big_oofs from "client/components/accolades/big_oofs.png";
import acc_wallflower from "client/components/accolades/wallflower.png";
import acc_participation_award from "client/components/accolades/participation_award.png";
import acc_brick from "client/components/accolades/brick.png";
import chicken_png from "client/components/img/chicken.png";

const ACCOLADES: Record<string, string> = {
  "Grand Slamma Jamma": acc_grand_slamma_jamma,
  "Moral Support": acc_moral_support,
  "Winner Winner Chicken Dinner": acc_winner_winner_chicken_dinner,
  "Glass Cannon": acc_glass_cannon,
  "Decoy": acc_decoy,
  "Just Uninstall": acc_just_uninstall,
  "Untouchable": acc_untouchable,
  "Stealthy Strategist": acc_stealthy_strategist,
  "Blind Fire": acc_blind_fire,
  "Bench Warmer": acc_bench_warmer,
  "Efficiency Expert": acc_efficiency_expert,
  "Headshot Hunter": acc_headshot_hunter,
  "High Roller": acc_high_roller,
  "Un MVP": acc_un_mvp,
  "Hard Carry": acc_hard_carry,
  "Top Frag": acc_top_frag,
  "Team Player": acc_team_player,
  "Cannon Fodder": acc_cannon_fodder,
  "Pacifist": acc_pacifist,
  "Big Oofs": acc_big_oofs,
  "Wallflower": acc_wallflower,
  "Participation Award": acc_participation_award,
  "Brick": acc_brick,
};

export function AccoladeCard({accolade, playerName}: { accolade: Accolade, playerName: string }) {
  const [imgError, setImgError] = useState(false);
  const imgSrc = imgError ? chicken_png : ACCOLADES[accolade.name];

  return (
      <div
          className="glass-panel rounded-[2rem] p-8 interactive-card border-t border-t-white/10 border-brand-500/20 shadow-2xl flex flex-col items-center text-center group hover:-translate-y-3 hover:shadow-brand-500/30 transition-all duration-500 relative overflow-hidden bg-gradient-to-b from-slate-800 to-dark-bg">
        <div
            className="absolute -top-32 -inset-x-20 h-64 bg-gradient-to-b from-brand-500/20 via-purple-500/10 to-transparent opacity-0 group-hover:opacity-100 blur-3xl transition-opacity duration-700 pointer-events-none rounded-full"/>
        <div
            className="absolute inset-0 rounded-[2rem] border border-white/5 pointer-events-none group-hover:border-white/10 transition-colors duration-500"/>

        <div className="relative z-10 w-full flex flex-col items-center h-full">
          <h3 className="text-3xl font-black text-white mb-8 drop-shadow-md tracking-tight uppercase">
            {playerName}
          </h3>

          <div
              className="h-56 w-56 mb-8 group-hover:scale-110 group-hover:rotate-6 transition-transform duration-700 ease-out flex flex-col items-center justify-center relative">
            <div
                className="absolute inset-4 bg-brand-400 rounded-full opacity-10 group-hover:opacity-40 blur-2xl transition-opacity duration-500"/>
            <img
                src={imgSrc}
                alt={accolade.name}
                onError={() => setImgError(true)}
                className="w-full h-full object-contain relative z-10 drop-shadow-[0_20px_30px_rgba(0,0,0,0.9)] filter group-hover:drop-shadow-[0_0_40px_rgba(14,165,233,0.9)] transition-all duration-500"
            />
          </div>

          <h2 className="text-4xl font-extrabold text-transparent bg-clip-text bg-gradient-to-br from-white via-brand-200 to-brand-500 mb-8 leading-tight group-hover:from-white group-hover:via-brand-300 group-hover:to-brand-400 transition-colors drop-shadow-sm flex items-center justify-center min-h-[5.5rem]">
            {accolade.name}
          </h2>

          <div className="flex-grow"/>

          <div
              className="w-12 h-1 rounded-full bg-brand-500/50 mb-6 group-hover:w-24 group-hover:bg-brand-400 transition-all duration-500"/>

          <div className="w-full flex flex-col gap-3">
            {accolade.details.map((detail: string, idx: number) => (
                <div key={idx}
                     className="bg-slate-900/80 px-5 py-3.5 rounded-2xl text-sm font-semibold text-slate-300 border border-brand-500/20 shadow-[inset_0_1px_0_rgba(255,255,255,0.05)] backdrop-blur-md group-hover:border-brand-500/40 group-hover:text-white transition-all transform group-hover:-translate-y-1">
                  {detail}
                </div>
            ))}
          </div>
        </div>
      </div>
  );
}
