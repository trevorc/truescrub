import { useState } from "react";
import {Accolade} from "proto/highlights_service_pb.js";

function getImageName(accoladeName: string): string {
  return `${accoladeName.toLowerCase().replace(/ /g, '_')}.png`;
}

export function AccoladeCard({accolade}: { accolade: Accolade }) {
  const [imgError, setImgError] = useState(false);
  const imgSrc = imgError ? '/htdocs/img/chicken.png' : `/htdocs/img/accolades/${getImageName(accolade.accolade)}`;

  return (
      <div
          className="glass-panel rounded-[2rem] p-8 interactive-card border-t border-t-white/10 border-brand-500/20 shadow-2xl flex flex-col items-center text-center group hover:-translate-y-3 hover:shadow-brand-500/30 transition-all duration-500 relative overflow-hidden bg-gradient-to-b from-slate-800 to-dark-bg">
        <div
            className="absolute -top-32 -inset-x-20 h-64 bg-gradient-to-b from-brand-500/20 via-purple-500/10 to-transparent opacity-0 group-hover:opacity-100 blur-3xl transition-opacity duration-700 pointer-events-none rounded-full"/>
        <div
            className="absolute inset-0 rounded-[2rem] border border-white/5 pointer-events-none group-hover:border-white/10 transition-colors duration-500"/>

        <div className="relative z-10 w-full flex flex-col items-center h-full">
          <h3 className="text-3xl font-black text-white mb-8 drop-shadow-md tracking-tight uppercase">
            {accolade.playerName}
          </h3>

          <div
              className="h-56 w-56 mb-8 group-hover:scale-110 group-hover:rotate-6 transition-transform duration-700 ease-out flex flex-col items-center justify-center relative">
            <div
                className="absolute inset-4 bg-brand-400 rounded-full opacity-10 group-hover:opacity-40 blur-2xl transition-opacity duration-500"/>
            <img
                src={imgSrc}
                alt={accolade.accolade}
                onError={() => setImgError(true)}
                className="w-full h-full object-contain relative z-10 drop-shadow-[0_20px_30px_rgba(0,0,0,0.9)] filter group-hover:drop-shadow-[0_0_40px_rgba(14,165,233,0.9)] transition-all duration-500"
            />
          </div>

          <h2 className="text-4xl font-extrabold text-transparent bg-clip-text bg-gradient-to-br from-white via-brand-200 to-brand-500 mb-8 leading-tight group-hover:from-white group-hover:via-brand-300 group-hover:to-brand-400 transition-colors drop-shadow-sm flex items-center justify-center min-h-[5.5rem]">
            {accolade.accolade}
          </h2>

          <div className="flex-grow"/>

          <div
              className="w-12 h-1 rounded-full bg-brand-500/50 mb-6 group-hover:w-24 group-hover:bg-brand-400 transition-all duration-500"/>

          <div className="w-full flex flex-col gap-3">
            {accolade.details.map((detail, idx) => (
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
