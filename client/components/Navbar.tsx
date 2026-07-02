import {Link} from "react-router-dom";

export function Navbar() {
  return (
      <nav className="max-w-7xl mx-auto mb-10 border-b border-dark-border/50 pb-4">
        <div className="flex flex-col sm:flex-row justify-between items-center gap-4">
          <Link to="/" className="text-3xl heading-gradient hover:opacity-80 transition-opacity">
            TrueScrub
          </Link>
          <div className="flex space-x-2 sm:space-x-6">
            <Link to="/leaderboard"
               className="text-slate-400 hover:text-brand-500 font-medium transition-colors">Leaderboard</Link>
            <Link to="/matchmaking"
                  className="text-slate-400 hover:text-brand-500 font-medium transition-colors">Matchmaking</Link>
            <Link to="/accolades"
                  className="text-slate-400 hover:text-brand-500 font-medium transition-colors">Accolades</Link>
            <Link to="/skill_groups"
               className="text-slate-400 hover:text-brand-500 font-medium transition-colors">Skill
              Groups</Link>
          </div>
        </div>
      </nav>
  );
}
