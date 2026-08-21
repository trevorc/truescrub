import React from 'react';
import {render, screen} from '@testing-library/react';
import {createMemoryRouter, RouterProvider} from 'react-router-dom';
import {QueryClient, QueryClientProvider} from '@tanstack/react-query';
import {TransportProvider} from '@connectrpc/connect-query';
import {createRouterTransport} from '@connectrpc/connect';
import {SeasonService} from 'proto/season_service_pb.js';
import {ConfigService} from 'proto/config_service_pb.js';

import {getRoutes} from 'client/TrueScrubClient.js';

describe('TrueScrubClient', () => {
  it('renders and maps root route to HomePage', async () => {
    const testTransport = createRouterTransport(({service}) => {
      service(ConfigService, {
        getBrandConfig: () => ({
          siteName: "MockedScrub",
        }),
      });
      service(SeasonService, {
        getAvailableSeasons: () => ({
          availableSeasons: [],
        }),
      });
    });

    const testQueryClient = new QueryClient({
      defaultOptions: {
        queries: {
          retry: false,
        },
      },
    });

    const router = createMemoryRouter(
        getRoutes(testQueryClient, testTransport), {initialEntries: ['/']});
    render(
        <TransportProvider transport={testTransport}>
          <QueryClientProvider client={testQueryClient}>
            <RouterProvider router={router}/>
          </QueryClientProvider>
        </TransportProvider>
    );
    expect(await screen.findByText(/MockedScrub™/i)).toBeTruthy();
    const titles = await screen.findAllByText(/Leaderboard/i);
    expect(titles.length).toBeGreaterThan(0);
  });
});
