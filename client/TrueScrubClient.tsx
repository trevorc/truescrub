import {createElement} from "react";
import {createRoot} from "react-dom/client";
import {BrowserRouter, Route, Routes} from "react-router-dom";
import {TransportProvider} from "@connectrpc/connect-query";
import {QueryClientProvider} from "@tanstack/react-query";
import {queryClient, transport} from "client/api/truescrub.js";
import {MatchmakingPage} from "client/pages/MatchmakingPage.js";
import {AccoladesPage} from "client/pages/AccoladesPage.js";
import {HomePage} from "client/pages/HomePage.js";
import {LeaderboardPage} from "client/pages/LeaderboardPage.js";
import {ProfilePage} from "client/pages/ProfilePage.js";
import {SkillGroupsPage} from "client/pages/SkillGroupsPage.js";
import {NotFoundPage} from "client/pages/NotFoundPage.js";
import {Navbar} from "client/components/Navbar.js";
import {Footer} from "client/components/Footer.js";

export function TrueScrubClient() {
  return (
      <TransportProvider transport={transport}>
        <QueryClientProvider client={queryClient}>
          <BrowserRouter>
            <div className="flex flex-col min-h-screen w-full pt-6 pb-12 px-4 sm:px-6 lg:px-8">
              <Navbar />
              <main className="max-w-7xl mx-auto w-full animate-fade-in flex-grow">
                <Routes>
                  <Route path="/" element={<HomePage/>}/>
                  <Route path="/matchmaking">
                    <Route index element={<MatchmakingPage/>}/>
                    <Route path="latest" element={<MatchmakingPage isLatest={true}/>}/>
                    <Route path="season/:seasonId" element={<MatchmakingPage/>}/>
                  </Route>
                  <Route path="/accolades" element={<AccoladesPage/>}/>
                  <Route path="/leaderboard">
                    <Route index element={<LeaderboardPage/>}/>
                    <Route path="season/:seasonId" element={<LeaderboardPage/>}/>
                  </Route>
                  <Route path="/profiles/:playerId/*" element={<ProfilePage/>}/>
                  <Route path="/skill_groups" element={<SkillGroupsPage/>}/>
                  <Route path="*" element={<NotFoundPage/>}/>
                </Routes>
              </main>
              <Footer />
            </div>
          </BrowserRouter>
        </QueryClientProvider>
      </TransportProvider>
  );
}

const root = document.getElementById("react-root");
if (root) {
  createRoot(root).render(createElement(TrueScrubClient));
}
