import {createBrowserRouter, RouteObject, RouterProvider} from "react-router-dom";
import {TransportProvider} from "@connectrpc/connect-query";
import {QueryClient, QueryClientProvider} from "@tanstack/react-query";
import {queryClient, transport} from "client/api/truescrub.js";
import {matchmakingLoader, MatchmakingPage} from "client/pages/MatchmakingPage.js";
import {accoladesLoader, AccoladesPage} from "client/pages/AccoladesPage.js";
import {HomePage} from "client/pages/HomePage.js";
import {leaderboardLoader, LeaderboardPage} from "client/pages/LeaderboardPage.js";
import {profileLoader, ProfilePage} from "client/pages/ProfilePage.js";
import {SkillGroupsPage} from "client/pages/SkillGroupsPage.js";
import {NotFoundPage} from "client/pages/NotFoundPage.js";
import {RootLayout} from "client/layouts/RootLayout.js";
import {brandQueryOptions} from "client/api/brand.js";
import {availableSeasonsQueryOptions} from "client/api/seasons.js";
import {LoadingState} from "client/components/LoadingState.js";
import type {Transport} from "@connectrpc/connect";

export const getRoutes = (queryClient: QueryClient, transport: Transport): RouteObject[] => [
  {
    element: <RootLayout/>,
    HydrateFallback: () => <LoadingState message="Initializing App..."/>,
    loader: async () => {
      await Promise.all([
        queryClient.ensureQueryData(brandQueryOptions(transport)),
        queryClient.ensureQueryData(availableSeasonsQueryOptions(transport))
      ]);
      return null;
    },
    children: [
      {
        path: "/",
        element: <HomePage/>,
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
