import {Link} from "react-router-dom";
import {useQuery} from "@connectrpc/connect-query";
import {getAvailableSeasons} from "proto/season_service-SeasonService_connectquery.js";
import chicken_png from "client/components/img/chicken.png";

export function HomePage() {
  const seasonsQuery = useQuery(getAvailableSeasons);
  const seasons = seasonsQuery.data?.availableSeasons ?? [];
  const seasonPath = seasons.length > 1 ? `/season/${seasons.length}` : "";

  return (
      <div
          className="flex flex-col items-center justify-center min-h-[60vh] text-center space-y-12">
        <div className="space-y-4 animate-slide-up">
          <div
              className="h-48 w-48 md:h-64 md:w-64 mx-auto bg-dark-bg border-4 border-dark-border rounded-full shadow-[0_0_60px_rgba(236,72,153,0.4)] flex items-center justify-center mb-6 transform hover:scale-105 transition-transform p-3 group overflow-hidden">
            <img src={chicken_png} alt="Mascot"
                 className="w-full h-full object-cover rounded-full group-hover:brightness-110 transition-all"/>
          </div>
          <h1 className="text-5xl md:text-7xl font-extrabold tracking-tight text-white mb-4">
            Welcome to <br/>
            <span className="heading-gradient">TrueScrub™</span>
          </h1>
          <p className="text-xl text-slate-400 max-w-2xl mx-auto leading-relaxed">
            The ultimate competitive matchmaking and rating engine. Analyze performance, discover
            your true skill, and find perfectly balanced matches.
          </p>
        </div>

        <div className="grid md:grid-cols-3 gap-6 w-full max-w-6xl mt-12">
          <a href={`/leaderboard${seasonPath}`}
             className="block p-8 glass-panel rounded-2xl interactive-card relative overflow-hidden group border-brand-500/20 hover:border-brand-500/50">
            <div
                className="absolute inset-0 bg-gradient-to-br from-brand-500/10 to-transparent opacity-0 group-hover:opacity-100 transition-opacity"></div>
            <div className="relative z-10 flex flex-col items-center text-center">
              <div
                  className="h-32 w-32 mb-6 group-hover:scale-110 transition-transform flex items-center justify-center relative">
                <div
                    className="absolute inset-0 bg-brand-500 rounded-full opacity-0 group-hover:opacity-20 blur-xl transition-opacity duration-300"></div>
                <img src="/htdocs/img/karambit.png" alt="Leaderboard Icon"
                     className="w-full h-full object-contain relative z-10 transition-all drop-shadow-[0_10px_15px_rgba(0,0,0,0.8)] filter group-hover:drop-shadow-[0_0_25px_rgba(14,165,233,0.8)]"/>
              </div>
              <h2 className="text-2xl font-bold text-white mb-2 group-hover:text-brand-400 transition-colors">Leaderboard</h2>
              <p className="text-slate-400">View rankings, seasonal MMR performance, and detailed
                impact stats for top players.</p>
            </div>
          </a>

          <Link to={`/matchmaking${seasonPath}`}
                className="block p-8 glass-panel rounded-2xl interactive-card relative overflow-hidden group border-purple-500/20 hover:border-purple-500/50">
            <div
                className="absolute inset-0 bg-gradient-to-br from-purple-500/10 to-transparent opacity-0 group-hover:opacity-100 transition-opacity"></div>
            <div className="relative z-10 flex flex-col items-center text-center">
              <div
                  className="h-32 w-32 mb-6 group-hover:scale-110 transition-transform flex items-center justify-center relative">
                <div
                    className="absolute inset-0 bg-purple-500 rounded-full opacity-0 group-hover:opacity-20 blur-xl transition-opacity duration-300"></div>
                <img src="/htdocs/img/c4.png" alt="Matchmaking Icon"
                     className="w-full h-full object-contain relative z-10 transition-all drop-shadow-[0_10px_15px_rgba(0,0,0,0.8)] filter group-hover:drop-shadow-[0_0_25px_rgba(168,85,247,0.8)]"/>
              </div>
              <h2 className="text-2xl font-bold text-white mb-2 group-hover:text-purple-400 transition-colors">Matchmaking</h2>
              <p className="text-slate-400">Generate perfectly balanced, fair team compositions
                based on the latest player ratings.</p>
            </div>
          </Link>

          <Link to="/accolades"
                className="block p-8 glass-panel rounded-2xl interactive-card relative overflow-hidden group border-amber-500/20 hover:border-amber-500/50">
            <div
                className="absolute inset-0 bg-gradient-to-br from-amber-500/10 to-transparent opacity-0 group-hover:opacity-100 transition-opacity"></div>
            <div className="relative z-10 flex flex-col items-center text-center">
              <div
                  className="h-32 w-32 mb-6 group-hover:scale-110 transition-transform flex items-center justify-center relative">
                <div
                    className="absolute inset-0 bg-amber-500 rounded-full opacity-0 group-hover:opacity-20 blur-xl transition-opacity duration-300"></div>
                <img src="/htdocs/img/accolades_icon.png" alt="Accolades Icon"
                     className="w-full h-full object-contain relative z-10 transition-all drop-shadow-[0_10px_15px_rgba(0,0,0,0.8)] filter group-hover:drop-shadow-[0_0_25px_rgba(245,158,11,0.8)]"/>
              </div>
              <h2 className="text-2xl font-bold text-white mb-2 group-hover:text-amber-400 transition-colors">Accolades</h2>
              <p className="text-slate-400">View daily match highlights, funniest moments, and
                quirky awards from recent games.</p>
            </div>
          </Link>
        </div>

        <div className="mt-8">
          <Link to="/matchmaking/latest"
                className="inline-flex items-center text-sm font-medium text-slate-400 hover:text-white transition-colors bg-dark-card border border-dark-border px-4 py-2 rounded-full">
            <span className="w-2 h-2 rounded-full bg-green-500 mr-2 animate-pulse"></span>
            Quick Match: Last Round Players
          </Link>
        </div>
      </div>
  );
}
