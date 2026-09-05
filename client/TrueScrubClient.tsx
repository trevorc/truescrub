import {createRoute, createRouter, RouterProvider,} from "@tanstack/react-router";
import {TransportProvider} from "@connectrpc/connect-query";
import {QueryClientProvider} from "@tanstack/react-query";
import {queryClient, transport} from "client/api/truescrub.js";
import {matchmakingRoute, matchmakingLatestRoute, matchmakingSeasonRoute} from "client/pages/MatchmakingPage.js";
import {accoladesRoute} from "client/pages/AccoladesPage.js";
import {indexRoute} from "client/pages/HomePage.js";
import {leaderboardRoute, leaderboardSeasonRoute} from "client/pages/LeaderboardPage.js";
import {profileRoute, profileOverviewRoute, profileMatchesRoute, profileTeamRecordsRoute} from "client/pages/ProfilePage.js";
import {skillGroupsRoute} from "client/pages/SkillGroupsPage.js";
import {rootRoute} from "client/RootRoute.js";


export const routeTree = rootRoute.addChildren([
  indexRoute,
  matchmakingRoute,
  matchmakingLatestRoute,
  matchmakingSeasonRoute,
  accoladesRoute,
  leaderboardRoute,
  leaderboardSeasonRoute,
  profileRoute.addChildren([
    profileOverviewRoute,
    profileMatchesRoute,
    profileTeamRecordsRoute,
  ]),
  skillGroupsRoute,
]);

export const router = createRouter({
  routeTree,
  context: {
    queryClient,
    transport,
  },
});

declare module '@tanstack/react-router' {
  interface Register {
    router: typeof router;
  }
}

export function TrueScrubClient() {
  return (
      <TransportProvider transport={transport}>
        <QueryClientProvider client={queryClient}>
          <RouterProvider router={router}/>
        </QueryClientProvider>
      </TransportProvider>
  );
}
