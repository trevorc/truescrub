import React, {Suspense} from 'react';
import {render, screen} from '@testing-library/react';
import {MemoryRouter, Route, Routes} from 'react-router-dom';
import {QueryClient, QueryClientProvider} from '@tanstack/react-query';
import {TransportProvider} from '@connectrpc/connect-query';
import {createRouterTransport} from '@connectrpc/connect';
import {ConfigService} from 'proto/config_service_pb.js';
import {SeasonService} from 'proto/season_service_pb.js';
import {RootLayout} from 'client/layouts/RootLayout.js';

describe('RootLayout', () => {
  it('renders the layout with Navbar, Footer, and Outlet content', async () => {
    const testTransport = createRouterTransport(({service}) => {
      service(ConfigService, {
        getBrandConfig: () => ({siteName: "MockedScrub"}),
      });
      service(SeasonService, {
        getAvailableSeasons: () => ({availableSeasons: []}),
      });
    });

    const testQueryClient = new QueryClient({
      defaultOptions: {queries: {retry: false}},
    });

    render(
        <TransportProvider transport={testTransport}>
          <QueryClientProvider client={testQueryClient}>
            <MemoryRouter initialEntries={['/']}>
              <Suspense fallback={<div>Loading...</div>}>
                <Routes>
                  <Route element={<RootLayout/>}>
                    <Route path="/" element={<div data-testid="content">Page Content</div>}/>
                  </Route>
                </Routes>
              </Suspense>
            </MemoryRouter>
          </QueryClientProvider>
        </TransportProvider>
    );

    const titles = await screen.findAllByText(/MockedScrub/i);
    expect(titles.length).toBeGreaterThan(0);
    expect(screen.getByTestId('content').textContent).toBe('Page Content');
  });
});
