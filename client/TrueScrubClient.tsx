import {createBrowserRouter, RouterProvider} from "react-router-dom";
import {TransportProvider} from "@connectrpc/connect-query";
import {QueryClientProvider} from "@tanstack/react-query";
import {queryClient, transport} from "client/api/truescrub.js";
import {matchmakingLoader, MatchmakingPage} from "client/pages/MatchmakingPage.js";
import {accoladesLoader, AccoladesPage} from "client/pages/AccoladesPage.js";
import {homeLoader, HomePage} from "client/pages/HomePage.js";
import {leaderboardLoader, LeaderboardPage} from "client/pages/LeaderboardPage.js";
import {profileLoader, ProfilePage} from "client/pages/ProfilePage.js";
import {SkillGroupsPage} from "client/pages/SkillGroupsPage.js";
import {NotFoundPage} from "client/pages/NotFoundPage.js";
import {RootLayout} from "client/layouts/RootLayout.js";

import {QueryClient} from "@tanstack/react-query";
import {RouteObject} from "react-router-dom";
import type {Transport} from "@connectrpc/connect";

export const getRoutes = (queryClient: QueryClient, transport: Transport): RouteObject[] => [
  {
    element: <RootLayout/>,
    children: [
      {
        path: "/",
        element: <HomePage/>,
        loader: homeLoader(queryClient, transport),
      },
      {
        path: "/matchmaking",
        children: [
          {
            index: true,
            element: <MatchmakingPage/>,
            loader: matchmakingLoader(queryClient, transport),
          },
          {
            path: "latest",
            element: <MatchmakingPage isLatest={true}/>,
            loader: matchmakingLoader(queryClient, transport, true),
          },
          {
            path: "season/:seasonId",
            element: <MatchmakingPage/>,
            loader: matchmakingLoader(queryClient, transport),
          }
        ]
      },
      {
        path: "/accolades",
        element: <AccoladesPage/>,
        loader: accoladesLoader(queryClient, transport),
      },
      {
        path: "/leaderboard",
        children: [
          {
            index: true,
            element: <LeaderboardPage/>,
            loader: leaderboardLoader(queryClient, transport),
          },
          {
            path: "season/:seasonId",
            element: <LeaderboardPage/>,
            loader: leaderboardLoader(queryClient, transport),
          }
        ]
      },
      {
        path: "/profiles/:playerId/*",
        element: <ProfilePage/>,
        loader: profileLoader(queryClient, transport),
      },
      {
        path: "/skill_groups",
        element: <SkillGroupsPage/>,
      },
      {
        path: "*",
        element: <NotFoundPage/>,
      }
    ]
  }
];

const router = createBrowserRouter(getRoutes(queryClient, transport));

export function TrueScrubClient() {
  return (
      <TransportProvider transport={transport}>
        <QueryClientProvider client={queryClient}>
          <RouterProvider router={router}/>
        </QueryClientProvider>
      </TransportProvider>
  );
}
