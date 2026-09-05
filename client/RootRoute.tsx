import {createRootRouteWithContext,} from "@tanstack/react-router";
import {QueryClient} from "@tanstack/react-query";
import type {Transport} from "@connectrpc/connect";
import {RootLayout} from "client/layouts/RootLayout.js";
import {brandQueryOptions} from "client/api/brand.js";
import {availableSeasonsQueryOptions} from "client/api/seasons.js";
import {LoadingState} from "client/components/LoadingState.js";
import {NotFoundPage} from "client/pages/NotFoundPage.js";

export interface RouterContext {
  queryClient: QueryClient;
  transport: Transport;
}

export const rootRoute = createRootRouteWithContext<RouterContext>()({
  component: RootLayout,
  pendingComponent: () => <LoadingState message="Initializing App..."/>,
  loader: async ({context: {queryClient, transport}}) => {
    await Promise.all([
      queryClient.ensureQueryData(brandQueryOptions(transport)),
      queryClient.ensureQueryData(availableSeasonsQueryOptions(transport))
    ]);
  },
  notFoundComponent: NotFoundPage,
});
