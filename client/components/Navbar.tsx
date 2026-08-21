import {Link} from "react-router-dom";
import {useSuspenseQuery} from "@tanstack/react-query";
import {brandQueryOptions} from "client/api/brand.js";
import {availableSeasonsQueryOptions, getLatestSeasonPath} from "client/api/seasons.js";
import {useTransport} from "@connectrpc/connect-query";

export function Navbar() {
  const transport = useTransport();
  const {data: brandData} = useSuspenseQuery(brandQueryOptions(transport));
  const { data: {availableSeasons} } = useSuspenseQuery(availableSeasonsQueryOptions(transport));
  const seasonPath = getLatestSeasonPath(availableSeasons);

  return (
      <nav className="max-w-7xl mx-auto mb-10 border-b border-dark-border/50 pb-4">
        <div className="flex flex-col sm:flex-row justify-between items-center gap-4">
          <Link to="/" className="text-3xl heading-gradient hover:opacity-80 transition-opacity">
            {brandData.siteName}
          </Link>
          <div className="flex space-x-2 sm:space-x-6">
            <Link to={`/leaderboard${seasonPath}`}
                  className="text-slate-400 hover:text-brand-500 font-medium transition-colors">Leaderboard</Link>
            <Link to={`/matchmaking${seasonPath}`}
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
